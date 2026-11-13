"""End-to-end run: generate -> validate -> migrate -> reconcile -> evaluate."""
import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from .db import create_schema, get_engine
from .evaluate import evaluate_detection
from .generate_data import generate
from .migrate import load_legacy, migrate
from .reconcile import reconcile, write_report
from .validators import validate


def run(out_dir, rows=5000, defects=200, seed=42, db_url=None, as_of=None):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    gen = generate(out / "data", rows, defects, seed)
    legacy = load_legacy(gen["legacy_csv"])
    clean, rej = validate(legacy, as_of)
    rej.to_csv(out / "rejections.csv", index=False)

    engine = get_engine(db_url or f"sqlite:///{(out / 'ae_migration.db').as_posix()}")
    create_schema(engine, drop=True)
    loaded = migrate(clean, engine)

    rejected_rows = int(rej["source_row"].nunique())
    recon = reconcile(clean, len(legacy), rejected_rows, engine)
    write_report(recon, out)

    manifest = pd.read_csv(gen["manifest_csv"], dtype=str, keep_default_na=False)
    detection = evaluate_detection(manifest, rej)
    (out / "detection_summary.json").write_text(json.dumps(detection, indent=2), encoding="utf-8")
    return {"out": out, "engine": engine, "legacy": legacy, "clean": clean, "rejections": rej,
            "loaded": loaded, "recon": recon, "detection": detection,
            "source_total": len(legacy), "rejected_rows": rejected_rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="output")
    ap.add_argument("--rows", type=int, default=5000)
    ap.add_argument("--defects", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--db-url", default=None, help="SQLAlchemy URL (default: $AE_DB_URL or SQLite file)")
    a = ap.parse_args()
    res = run(a.out, a.rows, a.defects, a.seed, a.db_url)
    d, r = res["detection"], res["recon"]
    print(f"Source records : {res['source_total']}")
    print(f"Rejected       : {res['rejected_rows']}  ({len(res['rejections'])} rule violations logged)")
    print(f"Loaded         : {res['loaded']}")
    print(f"Defect detection: {d['detected']}/{d['injected_total']} "
          f"(missed={len(d['missed_rows'])}, false positives={len(d['false_positive_rows'])})")
    print(f"Reconciliation : {'PASS' if r['all_match'] else 'FAIL'}")
    print(f"Artifacts in   : {res['out']}")


if __name__ == "__main__":
    main()
