"""The 12 validation rules. Each rule returns an error message or None.

Rules are written so a single defect normally trips exactly one rule: date-comparison
rules are skipped when a date is blank/unparseable (that is R01/R04's job).
"""
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Optional

import pandas as pd

from .config import (CASE_ID_RE, DATE_FIELDS, DRUG_CODES, EVENT_CODES, LEGACY_COLUMNS,
                     MANDATORY_FIELDS, OUTCOMES, SERIOUSNESS, SEX)

_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def _s(row, field) -> str:
    v = row.get(field, "")
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return str(v).strip()


def parse_date(s) -> Optional[date]:
    s = (s or "").strip()
    if not _ISO.fullmatch(s):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _d(row, field):
    return parse_date(_s(row, field))


def r01(row, ctx):
    missing = [f for f in MANDATORY_FIELDS if not _s(row, f)]
    return f"Missing mandatory field(s): {', '.join(missing)}" if missing else None


def r02(row, ctx):
    cid = _s(row, "case_id")
    if cid and not CASE_ID_RE.fullmatch(cid):
        return f"case_id '{cid}' does not match AE-###### format"


def r03(row, ctx):
    if row["__idx__"] in ctx["dup_idx"]:
        return f"Duplicate case_id '{_s(row, 'case_id')}' (first occurrence retained)"


def r04(row, ctx):
    bad = [f for f in DATE_FIELDS if _s(row, f) and parse_date(_s(row, f)) is None]
    if bad:
        return "Invalid date in: " + ", ".join(f"{f}='{_s(row, f)}'" for f in bad)


def r05(row, ctx):
    rd = _d(row, "receive_date")
    if rd and rd > ctx["as_of"]:
        return f"receive_date {rd} is in the future (as of {ctx['as_of']})"


def r06(row, ctx):
    dob, rd = _d(row, "patient_dob"), _d(row, "receive_date")
    if dob and rd and dob > rd:
        return f"patient_dob {dob} is after receive_date {rd}"


def r07(row, ctx):
    ts, te = _d(row, "therapy_start"), _d(row, "therapy_end")
    if ts and te and te < ts:
        return f"therapy_end {te} is before therapy_start {ts}"


def r08(row, ctx):
    on, ts = _d(row, "event_onset"), _d(row, "therapy_start")
    if on and ts and on < ts:
        return f"event_onset {on} is before therapy_start {ts}"


def r09(row, ctx):
    on, rd = _d(row, "event_onset"), _d(row, "receive_date")
    if on and rd and on > rd:
        return f"event_onset {on} is after receive_date {rd}"


def r10(row, ctx):
    c = _s(row, "drug_code")
    if c and c not in DRUG_CODES:
        return f"Unknown drug_code '{c}'"


def r11(row, ctx):
    c = _s(row, "event_code")
    if c and c not in EVENT_CODES:
        return f"Unknown event_code '{c}'"


def r12(row, ctx):
    problems = []
    for f, allowed in (("seriousness", SERIOUSNESS), ("outcome", OUTCOMES), ("patient_sex", SEX)):
        v = _s(row, f)
        if v and v not in allowed:
            problems.append(f"{f}='{v}'")
    if problems:
        return "Value not in controlled list: " + ", ".join(problems)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    name: str
    description: str
    check: Callable


RULES = [
    Rule("R01", "Mandatory fields", "case_id, receive_date, drug_code, event_code and seriousness must be populated.", r01),
    Rule("R02", "Case ID format", "case_id must match the pattern AE-###### (six digits).", r02),
    Rule("R03", "Duplicate case ID", "case_id must be unique; first occurrence is kept, later ones are rejected.", r03),
    Rule("R04", "Valid date format", "Every populated date field must be a real calendar date in YYYY-MM-DD.", r04),
    Rule("R05", "Receive date not in future", "receive_date must not be later than the run date.", r05),
    Rule("R06", "DOB before receive date", "patient_dob must not be later than receive_date.", r06),
    Rule("R07", "Therapy dates ordered", "therapy_end must not be earlier than therapy_start.", r07),
    Rule("R08", "Onset after therapy start", "event_onset must not be earlier than therapy_start.", r08),
    Rule("R09", "Onset before receipt", "event_onset must not be later than receive_date.", r09),
    Rule("R10", "Valid drug code", "drug_code must exist in the drug reference list.", r10),
    Rule("R11", "Valid event code", "event_code must exist in the event reference list.", r11),
    Rule("R12", "Controlled terms", "seriousness, outcome and patient_sex must come from their allowed value lists.", r12),
]
RULE_IDS = [r.rule_id for r in RULES]
RULE_BY_ID = {r.rule_id: r for r in RULES}
REJECTION_COLUMNS = ["source_row", "case_id", "rule_id", "rule_name", "reason"]


def validate(df: pd.DataFrame, as_of: Optional[date] = None):
    """Return (clean_df, rejections_df). source_row is the CSV line number (header = 1)."""
    missing_cols = set(LEGACY_COLUMNS) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Legacy file is missing columns: {sorted(missing_cols)}")
    as_of = as_of or date.today()
    rows = df.to_dict("records")

    seen, dup_idx = set(), set()
    for i, r in enumerate(rows):
        cid = _s(r, "case_id")
        if cid:
            (dup_idx.add(i) if cid in seen else seen.add(cid))
    ctx = {"as_of": as_of, "dup_idx": dup_idx}

    rejections, bad = [], set()
    for i, r in enumerate(rows):
        r = {**r, "__idx__": i}
        for rule in RULES:
            msg = rule.check(r, ctx)
            if msg:
                bad.add(i)
                rejections.append({"source_row": i + 2, "case_id": _s(r, "case_id"),
                                   "rule_id": rule.rule_id, "rule_name": rule.name, "reason": msg})
    keep = [i not in bad for i in range(len(df))]
    clean = df[keep].reset_index(drop=True)
    return clean, pd.DataFrame(rejections, columns=REJECTION_COLUMNS)
