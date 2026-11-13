import json

import pytest
from sqlalchemy import text

from aemigrate.reconcile import canon, reconcile


@pytest.mark.req("REQ-09", "Only validated records shall be loaded: loaded = read - rejected.",
                 "cases/patients/drugs/events each contain 4,800 rows.")
def test_loaded_counts(pipeline_result, record_property):
    """Loaded counts equal source minus rejected"""
    ld = pipeline_result["loaded"]
    record_property("actual", str(ld))
    assert all(ld[t] == 4800 for t in ("cases", "patients", "drugs", "events"))


@pytest.mark.req("REQ-10", "Reporters shall be de-duplicated.",
                 "Reporter rows equal distinct (name,type,country) values and are fewer than cases.")
def test_reporters_deduplicated(pipeline_result, record_property):
    """Reporters de-duplicated"""
    clean = pipeline_result["clean"]
    distinct = len(clean[["reporter_name", "reporter_type", "reporter_country"]].drop_duplicates())
    record_property("actual", f"reporters={pipeline_result['loaded']['reporters']}, distinct={distinct}")
    assert pipeline_result["loaded"]["reporters"] == distinct < pipeline_result["loaded"]["cases"]


@pytest.mark.req("REQ-11", "The target shall have referential integrity (no orphan rows).",
                 "Zero orphan drugs, events, cases->patients, cases->reporters.")
def test_referential_integrity(pipeline_result, record_property):
    """No orphan rows"""
    q = {"drugs": "SELECT COUNT(*) FROM drugs d LEFT JOIN cases c ON c.case_id=d.case_id WHERE c.case_id IS NULL",
         "events": "SELECT COUNT(*) FROM events e LEFT JOIN cases c ON c.case_id=e.case_id WHERE c.case_id IS NULL",
         "patients": "SELECT COUNT(*) FROM cases c LEFT JOIN patients p ON p.patient_id=c.patient_id WHERE p.patient_id IS NULL",
         "reporters": "SELECT COUNT(*) FROM cases c LEFT JOIN reporters r ON r.reporter_id=c.reporter_id WHERE r.reporter_id IS NULL"}
    with pipeline_result["engine"].connect() as conn:
        res = {k: conn.execute(text(v)).scalar() for k, v in q.items()}
    record_property("actual", str(res))
    assert all(v == 0 for v in res.values())


@pytest.mark.req("REQ-12", "Reconciliation shall prove no data was lost or altered (counts, field checksums, record checksum).",
                 "All 5 count checks, all 19 field checksums and the record checksum match.")
def test_reconciliation_passes(pipeline_result, record_property):
    """Clean migration reconciles"""
    r = pipeline_result["recon"]
    record_property("actual", f"counts={r['counts_match']}, fields matched={sum(f['match'] for f in r['fields'])}/{len(r['fields'])}, "
                              f"record checksum={r['record_checksum']['match']}")
    assert r["all_match"] and len(r["fields"]) == 19


@pytest.mark.req("REQ-13", "Reconciliation shall detect an altered value in the target.",
                 "Changing one dose_mg in the target makes dose_mg checksum fail and names the case.")
def test_reconciliation_detects_tamper(small_run, record_property):
    """Altered value detected"""
    eng = small_run["engine"]
    with eng.begin() as conn:
        conn.execute(text("UPDATE drugs SET dose_mg = dose_mg + 1 WHERE drug_row_id = 1"))
    r = reconcile(small_run["clean"], small_run["source_total"], small_run["rejected_rows"], eng)
    bad = [f for f in r["fields"] if not f["match"]]
    record_property("actual", f"failed fields={[f['field'] for f in bad]}, example={bad[0]['examples'][0] if bad else None}")
    assert not r["all_match"] and [f["field"] for f in bad] == ["dose_mg"]


@pytest.mark.req("REQ-14", "Reconciliation shall detect a lost record in the target.",
                 "Deleting one event row makes the events count check fail.")
def test_reconciliation_detects_loss(small_run, record_property):
    """Lost record detected"""
    eng = small_run["engine"]
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM events WHERE event_row_id = 1"))
    r = reconcile(small_run["clean"], small_run["source_total"], small_run["rejected_rows"], eng)
    ev = next(c for c in r["counts"] if c["object"] == "events")
    record_property("actual", f"events expected={ev['expected']}, actual={ev['actual']}")
    assert not ev["match"] and not r["all_match"]


@pytest.mark.req("REQ-15", "Type changes during load (text to DECIMAL/DATE) shall not cause false reconciliation failures.",
                 "'250' equals 250.00, '72.5' equals 72.50->72.5, date object equals ISO string, blank equals NULL.")
def test_canonical_form(record_property):
    """Canonicalisation is type-agnostic"""
    import datetime as dt
    from decimal import Decimal
    checks = [canon("dec2", "250") == canon("dec2", Decimal("250.00")) == canon("dec2", 250.0),
              canon("dec1", "72.5") == canon("dec1", 72.5),
              canon("date", "2024-06-01") == canon("date", dt.date(2024, 6, 1)),
              canon("text", "") == canon("text", None)]
    record_property("actual", f"checks={checks}")
    assert all(checks)


@pytest.mark.req("REQ-16", "The pipeline shall produce rejection log, reconciliation report and detection summary.",
                 "rejections.csv, reconciliation_report.md/.json/fields.csv and detection_summary.json all exist.")
def test_pipeline_artifacts(pipeline_result, record_property):
    """Pipeline writes all artefacts"""
    out = pipeline_result["out"]
    names = ["rejections.csv", "reconciliation_report.md", "reconciliation_report.json",
             "reconciliation_fields.csv", "detection_summary.json"]
    present = {n: (out / n).exists() for n in names}
    record_property("actual", str(present))
    assert all(present.values())
    assert json.loads((out / "detection_summary.json").read_text())["detection_rate"] == 1.0
