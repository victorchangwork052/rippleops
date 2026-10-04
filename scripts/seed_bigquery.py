"""Seed (or reseed) the RippleOps demo dataset in BigQuery and create the BOM graph.

Usage (from the repo root, with the API virtualenv):

    apps/api/.venv/Scripts/python scripts/seed_bigquery.py --project MY_PROJECT
    apps/api/.venv/Scripts/python scripts/seed_bigquery.py --csv-only      # just write data/seed/*.csv

The same deterministic generator feeds the local backend, so BigQuery and
local runs produce identical results. After loading, the script traces
MCU-X100 through BigQuery Graph and checks it against the in-memory trace.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.db.schema import TABLES, bq_schema  # noqa: E402
from app.seed.generator import AS_OF, generate  # noqa: E402

SEED_DIR = ROOT / "data" / "seed"


def _json_value(v):
    return v.isoformat() if isinstance(v, date) else v


def write_csvs(snapshot) -> None:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    for name, row_type in TABLES.items():
        cols = list(row_type.__dataclass_fields__)
        with open(SEED_DIR / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for row in snapshot.table(name):
                d = asdict(row)
                w.writerow(["" if d[c] is None else _json_value(d[c]) for c in cols])
    print(f"Wrote {len(TABLES)} CSV files to {SEED_DIR.relative_to(ROOT)}")


def load_bigquery(snapshot, project: str, dataset: str, location: str) -> None:
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    ds_ref = bigquery.Dataset(f"{project}.{dataset}")
    ds_ref.location = location
    client.create_dataset(ds_ref, exists_ok=True)
    for name, row_type in TABLES.items():
        schema = [bigquery.SchemaField(n, t, mode=m) for n, t, m in bq_schema(row_type)]
        rows = [{k: _json_value(v) for k, v in asdict(r).items()} for r in snapshot.table(name)]
        job = client.load_table_from_json(
            rows, f"{project}.{dataset}.{name}",
            job_config=bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_TRUNCATE"))
        job.result()
        print(f"  loaded {name:<18} {len(rows):>5} rows")

    ddl = (ROOT / "apps/api/app/db/sql/bom_graph.sql").read_text(encoding="utf-8").replace(
        "{dataset}", f"{project}.{dataset}")
    client.query(ddl).result()
    print("  created property graph bom_graph")


def verify(project: str, dataset: str) -> bool:
    import os

    os.environ.update({"GOOGLE_CLOUD_PROJECT": project, "BIGQUERY_DATASET": dataset, "DATA_BACKEND": "bigquery"})
    from app.config import get_settings
    from app.db.bigquery_repo import BigQueryRepository
    from app.db.repository import LocalRepository

    bq = BigQueryRepository(get_settings())
    local = LocalRepository(AS_OF)
    got, want = bq.trace("MCU-X100"), local.trace("MCU-X100")
    same = got.products == want.products and [p.nodes for p in got.paths] == [p.nodes for p in want.paths]
    print(f"Trace method: {got.trace_method}; affected products: {got.affected_product_count}; "
          f"matches local seed: {same}")
    return same


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", help="Google Cloud project ID")
    ap.add_argument("--dataset", default="rippleops")
    ap.add_argument("--location", default="US")
    ap.add_argument("--csv-only", action="store_true", help="Only write data/seed/*.csv")
    args = ap.parse_args()

    snapshot = generate()
    write_csvs(snapshot)
    if args.csv_only:
        return 0
    if not args.project:
        ap.error("--project is required unless --csv-only is given")
    print(f"Seeding {args.project}.{args.dataset} ({args.location})")
    load_bigquery(snapshot, args.project, args.dataset, args.location)
    return 0 if verify(args.project, args.dataset) else 1


if __name__ == "__main__":
    raise SystemExit(main())
