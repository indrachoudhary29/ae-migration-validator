"""Fixtures + a small pytest plugin that writes the validation document.

Every test carries a @pytest.mark.req(id, requirement, expected) marker and may call
record_property("actual", ...). After the session the plugin emits
validation/validation_document.md and .csv with the columns:
Requirement | Test | Expected result | Actual result | Pass/Fail.
"""
import csv
import platform
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

from aemigrate.db import create_schema, get_engine
from aemigrate.generate_data import generate
from aemigrate.pipeline import run

AS_OF = date(2026, 11, 11)
_RESULTS = []


@pytest.fixture(scope="session")
def generated(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("gen"))


@pytest.fixture(scope="session")
def pipeline_result(tmp_path_factory):
    return run(tmp_path_factory.mktemp("run"), as_of=AS_OF)


@pytest.fixture
def small_run(tmp_path):
    return run(tmp_path, rows=400, defects=24, seed=1, as_of=AS_OF)


@pytest.fixture
def engine(tmp_path):
    eng = get_engine(f"sqlite:///{(tmp_path / 't.db').as_posix()}")
    create_schema(eng)
    return eng


# ---------------- validation-document plugin ----------------
def pytest_configure(config):
    config.addinivalue_line("markers", "req(id, text, expected): requirement traceability")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    m = item.get_closest_marker("req")
    rep.req = m.args if m else ("", "", "")
    rep.test_name = item.name
    rep.test_doc = ((item.function.__doc__ or "").strip().splitlines() or [""])[0]


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and not report.passed):
        props = dict(report.user_properties)
        req_id, req_text, expected = getattr(report, "req", ("", "", ""))
        status = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP"}[report.outcome]
        actual = props.get("actual", "")
        if report.failed:
            msg = getattr(getattr(report.longrepr, "reprcrash", None), "message", str(report.longrepr))
            actual = f"{actual} | FAILED: {msg}".strip(" |")
        elif not actual:
            actual = "Result matched expected result."
        _RESULTS.append({
            "Req ID": props.get("req_id", req_id),
            "Requirement": props.get("requirement", req_text),
            "Test ID": "", "Test": f"{report.test_name} - {getattr(report, 'test_doc', '')}",
            "Expected Result": props.get("expected", expected),
            "Actual Result": actual, "Pass/Fail": status})


def _esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def pytest_sessionfinish(session, exitstatus):
    if not _RESULTS:
        return
    out = Path(session.config.rootpath) / "validation"
    out.mkdir(exist_ok=True)
    for i, r in enumerate(_RESULTS, start=1):
        r["Test ID"] = f"TC-{i:03d}"
    cols = ["Req ID", "Requirement", "Test ID", "Test", "Expected Result", "Actual Result", "Pass/Fail"]
    with open(out / "validation_document.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(_RESULTS)
    n = len(_RESULTS); p = sum(r["Pass/Fail"] == "PASS" for r in _RESULTS); f = n - p
    L = ["# Validation Document - Adverse Event Case Data Migration & Validation Tool", "",
         "| | |", "|---|---|",
         f"| Execution date | {datetime.now():%Y-%m-%d %H:%M} |",
         f"| Environment | Python {sys.version.split()[0]}, {platform.system()} {platform.release()} |",
         "| Test data | Synthetic only (no real patient data) |",
         f"| Result | **{p}/{n} passed, {f} failed** |", "",
         "## 1. Purpose", "",
         "Provide documented evidence that the migration tool (a) rejects invalid legacy records "
         "with a logged reason, (b) loads valid records into the normalized schema, and (c) preserves "
         "every value, proven by source-to-target reconciliation.", "",
         "## 2. Test execution record", "",
         "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    L += ["| " + " | ".join(_esc(r[c]) for c in cols) + " |" for r in _RESULTS]
    L += ["", "## 3. Deviations", ""]
    fails = [r for r in _RESULTS if r["Pass/Fail"] != "PASS"]
    L += ([f"- {r['Test ID']} ({r['Req ID']}): {_esc(r['Actual Result'])}" for r in fails]
          if fails else ["None. All executed tests passed."])
    L += ["", "## 4. Approval", "", "| Role | Name | Signature | Date |", "|---|---|---|---|",
          "| Author | | | |", "| Reviewer | | | |", ""]
    (out / "validation_document.md").write_text("\n".join(L), encoding="utf-8")
