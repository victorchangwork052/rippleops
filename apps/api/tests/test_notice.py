import io
import zipfile
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.routes_demo import DOCUMENTS, SAMPLE_NOTICE
from app.main import app
from app.models.notice import NoticeExtraction
from app.services import notice
from app.services.notice import NoticeReadError, extract_text, parse_notice, parse_with_rules, sanitize_filename

SAMPLE = (DOCUMENTS / SAMPLE_NOTICE).read_text(encoding="utf-8")


def test_rule_parser_reads_sample_notice():
    ex = parse_with_rules(SAMPLE)
    assert ex.event_type == "COMPONENT_EOL"
    assert ex.part_id == "MCU-X100"
    assert ex.supplier_name == "NovaChip Technologies"
    assert ex.last_time_buy_date == "2027-01-30"
    assert ex.last_ship_date == "2027-03-31"
    assert ex.recommended_alternative_part_id == "MCU-X200"


def test_parse_falls_back_to_rules_without_gemini(seed_repo):
    parsed = parse_notice(seed_repo.index(), SAMPLE, SAMPLE_NOTICE, "demo")
    assert parsed.extraction_method == "rules"
    assert parsed.fields.part_id == "MCU-X100"
    assert parsed.fields.last_time_buy_date == date(2027, 1, 30)
    assert parsed.validation.part_found
    assert parsed.validation.supplier_matches
    assert parsed.validation.alternative_found
    assert parsed.validation.warnings == []


def test_gemini_path_is_used_and_validated(seed_repo, monkeypatch):
    monkeypatch.setattr(notice, "parse_with_gemini", lambda text: NoticeExtraction(
        event_type="COMPONENT_EOL", supplier_name="NovaChip Technologies", part_id="mcu-x100",
        last_time_buy_date="2027-01-30", last_ship_date="2027-03-31", recommended_alternative_part_id="MCU-X200",
        reason="Product transition.", confidence=0.97))
    parsed = parse_notice(seed_repo.index(), SAMPLE, None, "demo")
    assert parsed.extraction_method == "gemini"
    assert parsed.confidence == 0.97
    assert parsed.fields.part_id == "MCU-X100"  # normalised
    assert parsed.validation.part_found


def test_hallucinated_part_is_flagged(seed_repo, monkeypatch):
    monkeypatch.setattr(notice, "parse_with_gemini", lambda text: NoticeExtraction(
        event_type="COMPONENT_EOL", part_id="MCU-K300", confidence=0.9))
    parsed = parse_notice(seed_repo.index(), SAMPLE, None, "demo")
    assert any("does not appear in the notice" in w for w in parsed.validation.warnings)


def test_unknown_part_is_not_found(seed_repo):
    text = "PRODUCT DISCONTINUATION NOTICE\nSupplier: Nobody Inc\nAffected Part: ZZ-9999\n"
    parsed = parse_notice(seed_repo.index(), text, None, "manual")
    assert parsed.fields.part_id == "ZZ-9999"
    assert not parsed.validation.part_found


def test_docx_and_type_checks():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml",
                    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                    '<w:p><w:r><w:t>Affected Part: MCU-X100</w:t></w:r></w:p>'
                    '<w:p><w:r><w:t>Last Time Buy Date: January 30, 2027</w:t></w:r></w:p></w:body></w:document>')
    assert "MCU-X100" in extract_text("notice.docx", buf.getvalue())
    with pytest.raises(NoticeReadError):
        extract_text("notice.exe", b"MZ....")
    with pytest.raises(NoticeReadError):
        extract_text("broken.pdf", b"not a pdf at all, definitely")


def test_filename_sanitizing():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("C:\\temp\\eol<script>.txt") == "eol_script_.txt"


def test_parse_endpoints():
    c = TestClient(app)
    r = c.post("/api/events/parse", json={"document_text": SAMPLE, "document_name": SAMPLE_NOTICE})
    assert r.status_code == 200 and r.json()["fields"]["part_id"] == "MCU-X100"
    up = c.post("/api/events/parse-upload", files={"file": ("notice.txt", SAMPLE.encode(), "text/plain")})
    assert up.status_code == 200 and up.json()["fields"]["recommended_alternative_part_id"] == "MCU-X200"
    bad = c.post("/api/events/parse-upload", files={"file": ("notice.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 422 and "PDF, TXT, or DOCX" in bad.json()["error"]["message"]
    big = c.post("/api/events/parse-upload", files={"file": ("big.txt", b"a" * (2 * 1024 * 1024 + 10), "text/plain")})
    assert big.status_code == 422
