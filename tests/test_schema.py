import pytest
from sqlalchemy import inspect

from aemigrate.db import export_mysql_ddl


@pytest.mark.req("REQ-04", "The target schema shall be normalized into cases, patients, drugs, events and reporters tables.",
                 "Exactly these five tables exist after schema creation.")
def test_five_tables(engine, record_property):
    """Schema creates the five normalized tables"""
    names = set(inspect(engine).get_table_names())
    record_property("actual", f"tables={sorted(names)}")
    assert names == {"cases", "patients", "drugs", "events", "reporters"}


@pytest.mark.req("REQ-05", "Relationships shall be enforced with foreign keys.",
                 "cases->patients,reporters; drugs->cases; events->cases.")
def test_foreign_keys(engine, record_property):
    """Foreign keys defined between tables"""
    insp = inspect(engine)
    fk = {t: {f["referred_table"] for f in insp.get_foreign_keys(t)} for t in ("cases", "drugs", "events")}
    record_property("actual", str(fk))
    assert fk["cases"] == {"patients", "reporters"}
    assert fk["drugs"] == {"cases"} and fk["events"] == {"cases"}


@pytest.mark.req("REQ-06", "The schema shall be deployable to MySQL (InnoDB).",
                 "Generated DDL contains CREATE TABLE for each table, FOREIGN KEY and ENGINE=InnoDB.")
def test_mysql_ddl(tmp_path, record_property):
    """MySQL DDL export"""
    ddl = export_mysql_ddl(tmp_path / "schema.sql")
    record_property("actual", f"{ddl.count('CREATE TABLE')} CREATE TABLE statements; InnoDB={'InnoDB' in ddl}")
    assert ddl.count("CREATE TABLE") == 5 and "FOREIGN KEY" in ddl and "InnoDB" in ddl
