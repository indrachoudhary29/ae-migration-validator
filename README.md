# Adverse Event Case Data Migration & Validation Tool

Migrates legacy pharmacovigilance case data (flat CSV) into a normalized MySQL schema, with
rule-based validation, rejection logging, source-to-target reconciliation, and a pytest suite
that produces a validation document in the style of GxP / CSV (computer system validation).

> All data is **synthetic**. Drug/event codes are invented and are not MedDRA or WHODrug.

## Quick start
```bash
pip install -r requirements.txt
python run_pipeline.py --out output          # SQLite by default
pytest                                       # 30 tests -> validation/validation_document.md
```
Run against MySQL:
```bash
docker run -d --name aemysql -e MYSQL_ROOT_PASSWORD=pw -e MYSQL_DATABASE=ae_migration -p 3306:3306 mysql:8
python run_pipeline.py --out output --db-url "mysql+pymysql://root:pw@localhost:3306/ae_migration"
```

## Pipeline
`generate_data` -> `validators` (12 rules) -> `migrate` (single transaction) -> `reconcile` -> `evaluate`

| Step | Module | Output |
|---|---|---|
| Synthetic legacy CSV + 200 injected defects + ground-truth manifest | `generate_data.py` | `data/legacy_cases.csv`, `data/injected_defects.csv` |
| 12 validation rules | `validators.py` | `rejections.csv` (row, case ID, rule, reason) |
| Normalized load (cases, patients, drugs, events, reporters) | `db.py`, `migrate.py` | SQLite/MySQL database |
| Record counts + per-field SHA-256 + whole-record checksum | `reconcile.py` | `reconciliation_report.md/.json` |
| Detected vs injected defects | `evaluate.py` | `detection_summary.json` |

## Validation rules
R01 mandatory fields · R02 case ID format · R03 duplicate case ID · R04 valid dates ·
R05 receive date not in future · R06 DOB <= receive date · R07 therapy end >= start ·
R08 onset >= therapy start · R09 onset <= receive date · R10 valid drug code ·
R11 valid event code · R12 controlled terms (seriousness / outcome / sex)

## Design notes
- Legacy file is read with `dtype=str`, so pandas never silently coerces a value.
- Load is one transaction: all-or-nothing, no half-migrated state.
- Reconciliation canonicalises both sides (`'250'` == `DECIMAL 250.00`) so type conversion
  doesn't cause false alarms, but any changed/lost/extra value does. Tests prove this by tampering with the target.
- The 200 defects are generated with a manifest, so "detected all 200" is measured, not asserted.
- Rules are designed so one defect trips one rule; tests assert that exactly.

## Limitations (be upfront about these)
- Legacy rows are 1 drug + 1 event per case; real safety data is many-to-many.
- Reference lists are tiny and synthetic; real systems use MedDRA / WHODrug dictionaries.
- Validation document is auto-generated from pytest; real CSV adds signed protocols, IQ/OQ/PQ, traceability matrix reviews.
