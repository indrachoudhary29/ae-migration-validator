"""Source-to-target reconciliation: record counts + field-level SHA-256 checksums.

Both sides are passed through the same canonical form (canon) so legitimate type
changes (text '250' -> DECIMAL 250.00) do not cause false alarms, while any real
change in value, any lost row, or any extra row changes the checksum.
"""
import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from .config import FIELD_KINDS, LEGACY_COLUMNS

TARGET_SQL = """
SELECT c.case_id, c.receive_date,
       p.initials AS patient_initials, p.dob AS patient_dob, p.sex AS patient_sex,
       p.weight_kg AS patient_weight_kg,
       d.drug_code, d.drug_name, d.dose_mg, d.therapy_start, d.therapy_end,
       e.event_code, e.event_term, e.onset_date AS event_onset,
       c.seriousness, c.outcome,
       r.name AS reporter_name, r.reporter_type, r.country AS reporter_country
FROM cases c
JOIN patients p  ON p.patient_id  = c.patient_id
JOIN reporters r ON r.reporter_id = c.reporter_id
JOIN drugs d     ON d.case_id     = c.case_id
JOIN events e    ON e.case_id     = c.case_id
"""
TABLES = ("cases", "patients", "drugs", "events", "reporters")


def canon(kind, v) -> str:
    if v is None or v is pd.NaT or (isinstance(v, float) and math.isnan(v)):
        return ""
    if kind == "date":
        return v.isoformat()[:10] if isinstance(v, (date, datetime)) else str(v).strip()[:10]
    if kind in ("dec1", "dec2"):
        if str(v).strip() == "":
            return ""
        return f"{float(v):.{1 if kind == 'dec1' else 2}f}"
    return str(v).strip()


def _canon_map(df, field):
    kind = FIELD_KINDS[field]
    return {str(c).strip(): canon(kind, v) for c, v in zip(df["case_id"], df[field])}


def _sha(lines):
    return hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def field_checksum(df, field) -> str:
    return _sha(f"{cid}|{val}" for cid, val in _canon_map(df, field).items())


def record_checksum(df) -> str:
    maps = {f: _canon_map(df, f) for f in LEGACY_COLUMNS}
    return _sha(f"{cid}|" + "|".join(maps[f][cid] for f in LEGACY_COLUMNS) for cid in maps["case_id"])


def reconcile(clean_df, source_total, rejected_rows, engine) -> dict:
    expected = source_total - rejected_rows
    with engine.connect() as conn:
        actual = {t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in TABLES}
        tgt = pd.read_sql(text(TARGET_SQL), conn)

    rep_cols = ["reporter_name", "reporter_type", "reporter_country"]
    exp_reporters = len(clean_df[rep_cols].apply(lambda s: s.str.strip()).drop_duplicates())
    exp = {"cases": expected, "patients": expected, "drugs": expected, "events": expected,
           "reporters": exp_reporters}
    counts = [{"object": t, "expected": exp[t], "actual": int(actual[t]), "match": exp[t] == actual[t]}
              for t in TABLES]

    fields = []
    for f in LEGACY_COLUMNS:
        s, t = field_checksum(clean_df, f), field_checksum(tgt, f)
        row = {"field": f, "source_checksum": s, "target_checksum": t, "match": s == t, "examples": []}
        if s != t:
            sm, tm = _canon_map(clean_df, f), _canon_map(tgt, f)
            for cid in sorted(set(sm) | set(tm)):
                if sm.get(cid) != tm.get(cid):
                    row["examples"].append({"case_id": cid, "source": sm.get(cid), "target": tm.get(cid)})
                if len(row["examples"]) >= 5:
                    break
        fields.append(row)

    rs, rt = record_checksum(clean_df), record_checksum(tgt)
    counts_ok = all(c["match"] for c in counts)
    fields_ok = all(f["match"] for f in fields)
    return {
        "source_records_read": int(source_total), "records_rejected": int(rejected_rows),
        "records_expected_in_target": int(expected),
        "counts": counts, "fields": fields,
        "record_checksum": {"source": rs, "target": rt, "match": rs == rt},
        "counts_match": counts_ok, "fields_match": fields_ok,
        "all_match": counts_ok and fields_ok and rs == rt,
    }


def write_report(recon, out_dir):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    (out / "reconciliation_report.json").write_text(json.dumps(recon, indent=2), encoding="utf-8")
    pd.DataFrame([{k: v for k, v in f.items() if k != "examples"} for f in recon["fields"]]) \
        .to_csv(out / "reconciliation_fields.csv", index=False)
    L = ["# Source-to-Target Reconciliation Report", "",
         f"**Overall result: {'PASS' if recon['all_match'] else 'FAIL'}**", "",
         f"- Source records read: {recon['source_records_read']}",
         f"- Rejected by validation: {recon['records_rejected']}",
         f"- Expected in target: {recon['records_expected_in_target']}", "",
         "## Record counts", "", "| Object | Expected | Actual | Result |", "|---|---|---|---|"]
    L += [f"| {c['object']} | {c['expected']} | {c['actual']} | {'PASS' if c['match'] else 'FAIL'} |"
          for c in recon["counts"]]
    L += ["", "## Field-level checksums (SHA-256)", "",
          "| Field | Source | Target | Result |", "|---|---|---|---|"]
    L += [f"| {f['field']} | `{f['source_checksum'][:16]}…` | `{f['target_checksum'][:16]}…` | "
          f"{'PASS' if f['match'] else 'FAIL'} |" for f in recon["fields"]]
    rc = recon["record_checksum"]
    L += ["", f"Whole-record checksum: {'PASS' if rc['match'] else 'FAIL'}", ""]
    (out / "reconciliation_report.md").write_text("\n".join(L), encoding="utf-8")
