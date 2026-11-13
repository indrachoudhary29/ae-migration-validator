"""Generate a synthetic legacy CSV and deliberately inject known defects.

Every injected defect is written to a manifest (ground truth) so the validator's
detection rate can be measured, not just claimed.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

from .config import (COUNTRIES, DATE_FIELDS, DRUG_CODES, EVENT_CODES, LEGACY_COLUMNS,
                     MANDATORY_FIELDS, OUTCOMES, REPORTER_TYPES, SERIOUSNESS, SEX)
from .validators import RULE_IDS

FIRST = ["Asha", "Ravi", "Meera", "John", "Emily", "Hans", "Sofia", "Kenji", "Priya", "Liam",
         "Aarav", "Nora", "Pierre", "Yuki", "Omar", "Anika", "Carlos", "Ingrid", "Dev", "Maya"]
LAST = ["Rao", "Sharma", "Iyer", "Smith", "Brown", "Muller", "Rossi", "Tanaka", "Nair", "Walsh",
        "Gupta", "Khan", "Dubois", "Sato", "Patel", "Bose", "Lopez", "Berg", "Menon", "Reddy"]
LETTERS = "ABCDEFGHJKLMNPRSTVW"


def _reporter_pool(rng, size=150):
    pool = set()
    while len(pool) < size:
        pool.add((f"{rng.choice(FIRST)} {rng.choice(LAST)}", rng.choice(REPORTER_TYPES),
                  rng.choice(COUNTRIES)))
    return sorted(pool)


def _clean_row(i, rng, reporters):
    receive = date(2019, 1, 1) + timedelta(days=rng.randint(0, 2555))
    start = receive - timedelta(days=rng.randint(30, 400))
    end = start + timedelta(days=rng.randint(1, 150)) if rng.random() < 0.7 else None
    onset = start + timedelta(days=rng.randint(0, (receive - start).days))
    dob = receive - timedelta(days=rng.randint(18 * 365, 90 * 365)) if rng.random() > 0.05 else None
    drug = rng.choice(sorted(DRUG_CODES))
    event = rng.choice(sorted(EVENT_CODES))
    rep = rng.choice(reporters)
    return {
        "case_id": f"AE-{i + 1:06d}",
        "receive_date": receive.isoformat(),
        "patient_initials": "".join(rng.choice(LETTERS) for _ in range(rng.choice((2, 3)))),
        "patient_dob": dob.isoformat() if dob else "",
        "patient_sex": rng.choices(SEX, weights=[48, 48, 4])[0],
        "patient_weight_kg": f"{rng.uniform(40, 120):.1f}" if rng.random() > 0.08 else "",
        "drug_code": drug,
        "drug_name": DRUG_CODES[drug],
        "dose_mg": str(rng.choice([5, 10, 20, 25, 50, 100, 250, 500])),
        "therapy_start": start.isoformat(),
        "therapy_end": end.isoformat() if end else "",
        "event_code": event,
        "event_term": EVENT_CODES[event],
        "event_onset": onset.isoformat(),
        "seriousness": rng.choices(SERIOUSNESS, weights=[25, 75])[0],
        "outcome": rng.choice(OUTCOMES),
        "reporter_name": rep[0], "reporter_type": rep[1], "reporter_country": rep[2],
    }


def _inject(rule_id, row, rows, idx, defect_set, rng):
    """Mutate `row` so it violates exactly `rule_id`. Returns (field, injected_value)."""
    d = date.fromisoformat
    if rule_id == "R01":
        f = rng.choice(MANDATORY_FIELDS); row[f] = ""; return f, ""
    if rule_id == "R02":
        n = idx + 1  # unique per row so it does not also look like a duplicate
        v = rng.choice([f"AE{n:06d}", f"ae-{n:06d}", f"CASE-{n}", f"AE-{n:03d}"]); row["case_id"] = v; return "case_id", v
    if rule_id == "R03":
        src = rng.choice([j for j in range(idx) if j not in defect_set])
        row["case_id"] = rows[src]["case_id"]; return "case_id", row["case_id"]
    if rule_id == "R04":
        f = rng.choice([x for x in DATE_FIELDS if row[x]])
        v = rng.choice(["2024-02-30", "2023-13-01", "31/12/2022", "not a date"]); row[f] = v; return f, v
    if rule_id == "R05":
        row["receive_date"] = "2035-06-15"; return "receive_date", "2035-06-15"
    if rule_id == "R06":
        v = (d(row["receive_date"]) + timedelta(days=30)).isoformat(); row["patient_dob"] = v; return "patient_dob", v
    if rule_id == "R07":
        v = (d(row["therapy_start"]) - timedelta(days=5)).isoformat(); row["therapy_end"] = v; return "therapy_end", v
    if rule_id == "R08":
        v = (d(row["therapy_start"]) - timedelta(days=10)).isoformat(); row["event_onset"] = v; return "event_onset", v
    if rule_id == "R09":
        v = (d(row["receive_date"]) + timedelta(days=20)).isoformat(); row["event_onset"] = v; return "event_onset", v
    if rule_id == "R10":
        row["drug_code"] = "DRG999"; return "drug_code", "DRG999"
    if rule_id == "R11":
        row["event_code"] = "EVT999"; return "event_code", "EVT999"
    if rule_id == "R12":
        f, v = rng.choice([("seriousness", "Maybe"), ("outcome", "Better-ish"), ("patient_sex", "X")])
        row[f] = v; return f, v
    raise ValueError(rule_id)


def generate(out_dir, n_rows=5000, n_defects=200, seed=42):
    if n_rows - 100 < n_defects:
        raise ValueError("n_rows must be at least n_defects + 100")
    rng = random.Random(seed)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    reporters = _reporter_pool(rng)
    rows = [_clean_row(i, rng, reporters) for i in range(n_rows)]

    # First 100 rows are never defective, so duplicates always have a clean earlier original.
    idxs = rng.sample(range(100, n_rows), n_defects)
    defect_set = set(idxs)
    manifest = []
    for k, idx in enumerate(idxs):
        rule_id = RULE_IDS[k % len(RULE_IDS)]
        orig_id = rows[idx]["case_id"]
        field, value = _inject(rule_id, rows[idx], rows, idx, defect_set, rng)
        manifest.append({"source_row": idx + 2, "case_id": orig_id, "rule_id": rule_id,
                         "field": field, "injected_value": value})
    manifest.sort(key=lambda m: m["source_row"])

    legacy_csv = out / "legacy_cases.csv"
    with open(legacy_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LEGACY_COLUMNS); w.writeheader(); w.writerows(rows)
    manifest_csv = out / "injected_defects.csv"
    with open(manifest_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["source_row", "case_id", "rule_id", "field", "injected_value"])
        w.writeheader(); w.writerows(manifest)
    return {"legacy_csv": legacy_csv, "manifest_csv": manifest_csv}
