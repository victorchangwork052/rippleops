"""Supplier-notice understanding: text extraction, Gemini parsing, validation.

Gemini reads the notice; the extracted part is then validated against the
product data. A rule-based parser is the fallback when Gemini is unavailable,
so the demo never depends on an external call succeeding.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import date, datetime
from xml.etree import ElementTree

from app.ai import prompts
from app.ai.gemini import GeminiUnavailable, generate_structured
from app.config import get_settings
from app.models.notice import ExtractedFields, NoticeExtraction, NoticeValidation, ParsedNotice
from app.services.index import DataIndex

log = logging.getLogger("rippleops.notice")

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}
PART_PATTERN = re.compile(r"\b[A-Z]{2,5}-[A-Z0-9]{2,8}(?:-[A-Z0-9]{1,6})?\b")
DATE_FORMATS = ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%m/%d/%Y")


class NoticeReadError(ValueError):
    """The document could not be read; the message is safe to show."""


# -- document text -----------------------------------------------------------


def sanitize_filename(name: str | None) -> str:
    base = (name or "notice").replace("\\", "/").split("/")[-1]
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" .") or "notice"
    return base[:120]


def extract_text(filename: str, data: bytes) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise NoticeReadError("Please upload a PDF, TXT, or DOCX file.")
    try:
        if ext == ".txt":
            text = data.decode("utf-8", errors="replace")
        elif ext == ".docx":
            text = _docx_text(data)
        else:
            text = _pdf_text(data)
    except NoticeReadError:
        raise
    except Exception as exc:  # noqa: BLE001 - malformed files of any kind
        log.warning("notice_read_failed", extra={"error_category": type(exc).__name__, "ext": ext})
        raise NoticeReadError("This file could not be read. It may be damaged or password-protected.") from exc
    text = text.replace("\x00", "").strip()
    if len(text) < 20:
        raise NoticeReadError("We couldn't find readable text in this file. Scanned images are not supported yet.")
    return text[:50_000]


def _docx_text(data: bytes) -> str:
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        info = zf.getinfo("word/document.xml")
        if info.file_size > 5_000_000:
            raise NoticeReadError("This document is too large to read.")
        root = ElementTree.fromstring(zf.read(info))
    paragraphs = []
    for p in root.iter(f"{ns}p"):
        paragraphs.append("".join(t.text or "" for t in p.iter(f"{ns}t")))
    return "\n".join(paragraphs)


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise NoticeReadError("This PDF is password-protected.")
    return "\n".join((page.extract_text() or "") for page in reader.pages[:20])


# -- parsing -------------------------------------------------------------------


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip().rstrip(".")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _field(text: str, *labels: str) -> str | None:
    for label in labels:
        m = re.search(rf"^\s*{label}\s*[:\-]\s*(.+?)\s*$", text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def parse_with_rules(text: str) -> NoticeExtraction:
    """Deterministic fallback for well-structured notices."""
    upper = text.upper()
    if any(k in upper for k in ("DISCONTINU", "END-OF-LIFE", "END OF LIFE", "LAST TIME BUY", "EOL")):
        event_type = "COMPONENT_EOL"
    elif "PRICE INCREASE" in upper or "PRICE ADJUSTMENT" in upper:
        event_type = "SUPPLIER_PRICE_INCREASE"
    else:
        event_type = "OTHER"
    part = _field(text, "Affected Part", "Part Number", "Affected Part Number", "Part")
    part_match = PART_PATTERN.search(part.upper()) if part else PART_PATTERN.search(upper)
    alt = _field(text, "Recommended Replacement", "Replacement Part", "Recommended Alternative")
    alt_match = PART_PATTERN.search(alt.upper()) if alt else None
    ltb = parse_date(_field(text, "Last Time Buy Date", "Last Time Buy", "LTB Date", "LTB"))
    lsd = parse_date(_field(text, "Last Ship Date", "Last Shipment Date", "LSD"))
    reason = _field(text, "Reason")
    return NoticeExtraction(
        event_type=event_type,
        supplier_name=_field(text, "Supplier", "Manufacturer"),
        part_id=part_match.group(0) if part_match else None,
        last_time_buy_date=ltb.isoformat() if ltb else None,
        last_ship_date=lsd.isoformat() if lsd else None,
        recommended_alternative_part_id=alt_match.group(0) if alt_match else None,
        reason=reason,
        confidence=0.0,
    )


def parse_with_gemini(text: str) -> NoticeExtraction:
    return generate_structured(prompts.NOTICE_EXTRACTION, [f"SUPPLIER NOTICE:\n\n{text}"], NoticeExtraction,
                               purpose="parse_change_notice", prompt_version=prompts.NOTICE_EXTRACTION_VERSION)


def _norm_part(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", "", value).upper() or None


def validate(index: DataIndex, text: str, ex: NoticeExtraction) -> NoticeValidation:
    warnings: list[str] = []
    part_id = _norm_part(ex.part_id)
    item = index.items.get(part_id or "")
    part_found = item is not None and item.item_type == "COMPONENT"
    on_record = index.supplier_name_for_part(part_id) if part_found and part_id else None
    named = (ex.supplier_name or "").lower()
    supplier_matches = bool(on_record and named and (on_record.lower() in named or named in on_record.lower()))
    if part_id and part_id not in re.sub(r"\s+", "", text.upper()):
        # Guardrail: the extracted part must literally appear in the source document.
        warnings.append(f"{part_id} does not appear in the notice text; please confirm the part number.")
    if part_found and ex.supplier_name and on_record and not supplier_matches:
        warnings.append(f"The notice names {ex.supplier_name}, but {part_id} is sourced from {on_record}.")
    alt_id = _norm_part(ex.recommended_alternative_part_id)
    alt_item = index.items.get(alt_id or "")
    if alt_id and alt_item is None:
        warnings.append(f"Recommended replacement {alt_id} is not in the product data yet.")
    elif alt_id and part_id and alt_id not in index.alternative_ids(part_id):
        warnings.append(f"{alt_id} is not yet listed as an alternative for {part_id}.")
    ltb = parse_date(ex.last_time_buy_date)
    if ltb and ltb < index.as_of:
        warnings.append("The last-time-buy date has already passed.")
    return NoticeValidation(
        part_found=part_found, part_name=item.item_name if part_found and item else None,
        part_status=item.status if part_found and item else None, supplier_name=on_record,
        supplier_matches=supplier_matches, alternative_found=alt_item is not None,
        alternative_name=alt_item.item_name if alt_item else None, warnings=warnings,
    )


def parse_notice(index: DataIndex, text: str, document_name: str | None, source: str) -> ParsedNotice:
    settings = get_settings()
    method, model, fallback_reason = "rules", None, None
    try:
        ex = parse_with_gemini(text)
        method, model = "gemini", settings.gemini_model
    except GeminiUnavailable as exc:
        fallback_reason = str(exc)
        ex = parse_with_rules(text)
    validation = validate(index, text, ex)
    part_id = _norm_part(ex.part_id) or ""
    fields = ExtractedFields(
        event_type=ex.event_type if ex.event_type != "OTHER" else "COMPONENT_EOL",
        supplier_name=validation.supplier_name if validation.supplier_matches else ex.supplier_name,
        part_id=part_id,
        last_time_buy_date=parse_date(ex.last_time_buy_date),
        last_ship_date=parse_date(ex.last_ship_date),
        recommended_alternative_part_id=_norm_part(ex.recommended_alternative_part_id),
        source=source, source_document_name=document_name, extraction_method=method,
    )
    log.info("notice_parsed", extra={"method": method, "part_found": validation.part_found,
                                     "warnings": len(validation.warnings)})
    return ParsedNotice(
        fields=fields, reason=ex.reason, confidence=ex.confidence if method == "gemini" else None,
        extraction_method=method, model=model, fallback_reason=fallback_reason,
        document_name=document_name, validation=validation,
    )
