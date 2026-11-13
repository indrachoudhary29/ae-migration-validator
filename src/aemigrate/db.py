"""Normalized schema (single source of truth) + engine helpers.

Default engine is SQLite so tests run anywhere; set AE_DB_URL to a MySQL URL, e.g.
mysql+pymysql://user:pass@localhost:3306/ae_migration, for the real target.
"""
import os
import warnings
from pathlib import Path

from sqlalchemy import (Column, Date, ForeignKey, Integer, MetaData, Numeric, String, Table,
                        UniqueConstraint, create_engine, event)
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

warnings.filterwarnings("ignore", message=".*does \\*not\\* support Decimal.*")

metadata = MetaData()
_MY = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

patients = Table(
    "patients", metadata,
    Column("patient_id", String(10), primary_key=True),
    Column("initials", String(5)),
    Column("dob", Date),
    Column("sex", String(1)),
    Column("weight_kg", Numeric(5, 1)),
    **_MY)

reporters = Table(
    "reporters", metadata,
    Column("reporter_id", String(10), primary_key=True),
    Column("name", String(100)),
    Column("reporter_type", String(20)),
    Column("country", String(2)),
    UniqueConstraint("name", "reporter_type", "country", name="uq_reporter"),
    **_MY)

cases = Table(
    "cases", metadata,
    Column("case_id", String(10), primary_key=True),
    Column("receive_date", Date, nullable=False),
    Column("seriousness", String(12), nullable=False),
    Column("outcome", String(20)),
    Column("patient_id", String(10), ForeignKey("patients.patient_id"), nullable=False),
    Column("reporter_id", String(10), ForeignKey("reporters.reporter_id"), nullable=False),
    **_MY)

drugs = Table(
    "drugs", metadata,
    Column("drug_row_id", Integer, primary_key=True, autoincrement=True),
    Column("case_id", String(10), ForeignKey("cases.case_id"), nullable=False),
    Column("drug_code", String(10), nullable=False),
    Column("drug_name", String(60)),
    Column("dose_mg", Numeric(8, 2)),
    Column("therapy_start", Date),
    Column("therapy_end", Date),
    **_MY)

events = Table(
    "events", metadata,
    Column("event_row_id", Integer, primary_key=True, autoincrement=True),
    Column("case_id", String(10), ForeignKey("cases.case_id"), nullable=False),
    Column("event_code", String(10), nullable=False),
    Column("event_term", String(60)),
    Column("onset_date", Date),
    **_MY)


def get_engine(url=None):
    url = url or os.getenv("AE_DB_URL") or "sqlite:///ae_migration.db"
    engine = create_engine(url)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_con, _):
            dbapi_con.execute("PRAGMA foreign_keys=ON")
    return engine


def create_schema(engine, drop=True):
    if drop:
        metadata.drop_all(engine)
    metadata.create_all(engine)


def export_mysql_ddl(path):
    dialect = mysql.dialect()
    stmts = [str(CreateTable(t).compile(dialect=dialect)).strip() + ";" for t in metadata.sorted_tables]
    text = "-- MySQL DDL generated from aemigrate.db (single source of truth)\n\n" + "\n\n".join(stmts) + "\n"
    Path(path).write_text(text, encoding="utf-8")
    return text
