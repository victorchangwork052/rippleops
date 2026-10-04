"""Reset a running RippleOps deployment to its initial demo state.

    python scripts/reset_demo.py                       # local API on :8000
    python scripts/reset_demo.py --api https://rippleops-api-xxxx.a.run.app

Use --reseed to also reload the BigQuery tables from the deterministic seed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--reseed", action="store_true")
    ap.add_argument("--project")
    args = ap.parse_args()
    if args.reseed:
        if not args.project:
            ap.error("--reseed needs --project")
        script = Path(__file__).with_name("seed_bigquery.py")
        subprocess.run([sys.executable, str(script), "--project", args.project], check=True)
    req = urllib.request.Request(f"{args.api.rstrip('/')}/api/demo/reset", method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - operator-supplied URL
        print(json.loads(resp.read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
