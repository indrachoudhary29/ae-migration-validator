"""Load validated legacy rows into the normalized schema in ONE transaction."""
from datetime import date
from decimal import Decimal

import pandas as pd

from . import db


def load_legacy(path) -> pd.DataFrame:
    # dtype=str + keep_default_na=False: nothing is silently coerced on read.
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _txt(s):
    s = (s or "").strip()
    return s or None


def _date(s):
    s = (s or "").strip()
    return date.fromisoformat(s) if s else None


def _dec(s):
    s = (s or "").strip()
    return Decimal(s) if s else None


def _chunks(rows, n=1000):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


def migrate(clean_df: pd.DataFrame, engine) -> dict:
    reporter_ids, reporter_rows = {}, []
    patient_rows, case_rows, drug_rows, event_rows = [], [], [], []

    for n, r in enumerate(clean_df.to_dict("records"), start=1):
        rkey = (r["reporter_name"].strip(), r["reporter_type"].strip(), r["reporter_country"].strip())
        if rkey not in reporter_ids:
            rid = f"RPT{len(reporter_ids) + 1:06d}"
            reporter_ids[rkey] = rid
            reporter_rows.append({"reporter_id": rid, "name": _txt(rkey[0]),
                                  "reporter_type": _txt(rkey[1]), "country": _txt(rkey[2])})
        pid = f"PAT{n:06d}"
        patient_rows.append({"patient_id": pid, "initials": _txt(r["patient_initials"]),
                             "dob": _date(r["patient_dob"]), "sex": _txt(r["patient_sex"]),
                             "weight_kg": _dec(r["patient_weight_kg"])})
        case_rows.append({"case_id": r["case_id"].strip(), "receive_date": _date(r["receive_date"]),
                          "seriousness": r["seriousness"].strip(), "outcome": _txt(r["outcome"]),
                          "patient_id": pid, "reporter_id": reporter_ids[rkey]})
        drug_rows.append({"case_id": r["case_id"].strip(), "drug_code": r["drug_code"].strip(),
                          "drug_name": _txt(r["drug_name"]), "dose_mg": _dec(r["dose_mg"]),
                          "therapy_start": _date(r["therapy_start"]), "therapy_end": _date(r["therapy_end"])})
        event_rows.append({"case_id": r["case_id"].strip(), "event_code": r["event_code"].strip(),
                           "event_term": _txt(r["event_term"]), "onset_date": _date(r["event_onset"])})

    plan = [(db.reporters, reporter_rows), (db.patients, patient_rows), (db.cases, case_rows),
            (db.drugs, drug_rows), (db.events, event_rows)]
    with engine.begin() as conn:  # all-or-nothing
        for table, rows in plan:
            for chunk in _chunks(rows):
                conn.execute(table.insert(), chunk)
    return {t.name: len(rows) for t, rows in plan}
