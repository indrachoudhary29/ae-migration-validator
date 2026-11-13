import pandas as pd
import pytest

from aemigrate.config import LEGACY_COLUMNS
from aemigrate.validators import RULE_BY_ID, validate
from conftest import AS_OF

BASE = dict(
    case_id="AE-000001", receive_date="2024-06-01", patient_initials="AB", patient_dob="1980-01-01",
    patient_sex="F", patient_weight_kg="60.0", drug_code="DRG001", drug_name="Zorvamab", dose_mg="50",
    therapy_start="2024-03-01", therapy_end="2024-04-01", event_code="EVT001", event_term="Nausea",
    event_onset="2024-03-15", seriousness="Serious", outcome="Recovered", reporter_name="Asha Rao",
    reporter_type="Physician", reporter_country="IN")


def run_rows(*rows):
    return validate(pd.DataFrame(list(rows), columns=LEGACY_COLUMNS), as_of=AS_OF)


NEGATIVE = [
    ("R01", {"drug_code": ""}), ("R02", {"case_id": "AE-12"}), ("R03", "dup"),
    ("R04", {"receive_date": "2024-02-30"}), ("R05", {"receive_date": "2035-06-15"}),
    ("R06", {"patient_dob": "2024-07-01"}), ("R07", {"therapy_end": "2024-02-01"}),
    ("R08", {"event_onset": "2024-02-01"}), ("R09", {"event_onset": "2024-07-01"}),
    ("R10", {"drug_code": "DRG999"}), ("R11", {"event_code": "EVT999"}),
    ("R12", {"seriousness": "Maybe"}),
]


@pytest.mark.req("REQ-VAL", "", "")
@pytest.mark.parametrize("rule_id,change", NEGATIVE, ids=[n[0] for n in NEGATIVE])
def test_rule_rejects_violation(rule_id, change, record_property):
    """Rule rejects a record that violates it (and only that rule fires)"""
    rule = RULE_BY_ID[rule_id]
    n = int(rule_id[1:])
    if change == "dup":
        _, rej = run_rows(BASE, dict(BASE))
    else:
        _, rej = run_rows({**BASE, **change})
    fired = set(rej.rule_id)
    record_property("req_id", f"REQ-VAL-{n:02d}")
    record_property("requirement", f"{rule_id} {rule.name}: {rule.description}")
    record_property("expected", f"Record rejected by {rule_id} only; reason logged.")
    record_property("actual", f"Rules fired: {sorted(fired)}; reason: {rej.reason.iloc[0] if len(rej) else 'n/a'}")
    assert fired == {rule_id}


@pytest.mark.req("REQ-VAL-00", "A fully valid record shall pass all 12 rules.",
                 "No rejections; record present in clean output.")
def test_valid_record_passes(record_property):
    """Valid record accepted"""
    clean, rej = run_rows(BASE)
    record_property("actual", f"clean={len(clean)}, rejections={len(rej)}")
    assert len(clean) == 1 and rej.empty


@pytest.mark.req("REQ-VAL-03", "On duplicate case IDs the first occurrence shall be retained.",
                 "Row 2 kept, row 3 rejected.")
def test_duplicate_keeps_first(record_property):
    """First duplicate kept, later one rejected"""
    clean, rej = run_rows(BASE, dict(BASE))
    record_property("actual", f"clean rows={len(clean)}, rejected source_row={list(rej.source_row)}")
    assert len(clean) == 1 and list(rej.source_row) == [3]


@pytest.mark.req("REQ-07", "The validator shall detect every injected defect with no false positives.",
                 "200/200 injected defects rejected under the intended rule; 0 false positives.")
def test_detects_all_injected_defects(pipeline_result, record_property):
    """All 200 injected defects detected"""
    d = pipeline_result["detection"]
    record_property("actual", f"detected {d['detected']}/{d['injected_total']}, missed={len(d['missed_rows'])}, "
                              f"false_positives={len(d['false_positive_rows'])}, wrong_rule={len(d['wrong_rule_rows'])}")
    assert d["detected"] == d["injected_total"] == 200
    assert not d["missed_rows"] and not d["false_positive_rows"] and not d["wrong_rule_rows"]


@pytest.mark.req("REQ-08", "Each rejection shall be logged with source row, case ID, rule and reason.",
                 "rejections.csv exists; every entry has a non-empty rule_id and reason.")
def test_rejection_log(pipeline_result, record_property):
    """Rejection log complete"""
    log = pd.read_csv(pipeline_result["out"] / "rejections.csv", dtype=str, keep_default_na=False)
    record_property("actual", f"{len(log)} entries; blank reasons={int((log.reason == '').sum())}")
    assert len(log) == len(pipeline_result["rejections"]) > 0
    assert (log.reason != "").all() and (log.rule_id != "").all()
