import pandas as pd
import pytest

from aemigrate.generate_data import generate
from aemigrate.validators import RULE_IDS


@pytest.mark.req("REQ-01", "The generator shall create a 5,000-record legacy CSV.",
                 "legacy_cases.csv has exactly 5,000 data rows.")
def test_row_count(generated, record_property):
    """Legacy file contains 5,000 records"""
    df = pd.read_csv(generated["legacy_csv"], dtype=str, keep_default_na=False)
    record_property("actual", f"{len(df)} data rows")
    assert len(df) == 5000


@pytest.mark.req("REQ-02", "The generator shall inject 200 known defects covering all 12 rules and record them in a manifest.",
                 "Manifest lists 200 distinct rows and every rule R01-R12 appears.")
def test_defect_manifest(generated, record_property):
    """Manifest has 200 defects across all 12 rules"""
    m = pd.read_csv(generated["manifest_csv"], dtype=str, keep_default_na=False)
    record_property("actual", f"{len(m)} defects, {m.source_row.nunique()} distinct rows, rules={sorted(m.rule_id.unique())}")
    assert len(m) == 200 and m.source_row.nunique() == 200
    assert set(m.rule_id) == set(RULE_IDS)


@pytest.mark.req("REQ-03", "Data generation shall be reproducible for a given seed.",
                 "Two runs with the same seed produce byte-identical files.")
def test_deterministic(tmp_path, record_property):
    """Same seed gives identical output"""
    a = generate(tmp_path / "a", 300, 12, seed=7)
    b = generate(tmp_path / "b", 300, 12, seed=7)
    same = (a["legacy_csv"].read_bytes() == b["legacy_csv"].read_bytes()
            and a["manifest_csv"].read_bytes() == b["manifest_csv"].read_bytes())
    record_property("actual", f"identical={same}")
    assert same
