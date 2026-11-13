# Validation Document - Adverse Event Case Data Migration & Validation Tool

| | |
|---|---|
| Execution date | 2026-11-11 18:15 |
| Environment | Python 3.10.0, Windows 10 |
| Test data | Synthetic only (no real patient data) |
| Result | **30/30 passed, 0 failed** |

## 1. Purpose

Provide documented evidence that the migration tool (a) rejects invalid legacy records with a logged reason, (b) loads valid records into the normalized schema, and (c) preserves every value, proven by source-to-target reconciliation.

## 2. Test execution record

| Req ID | Requirement | Test ID | Test | Expected Result | Actual Result | Pass/Fail |
|---|---|---|---|---|---|---|
| REQ-01 | The generator shall create a 5,000-record legacy CSV. | TC-001 | test_row_count - Legacy file contains 5,000 records | legacy_cases.csv has exactly 5,000 data rows. | 5000 data rows | PASS |
| REQ-02 | The generator shall inject 200 known defects covering all 12 rules and record them in a manifest. | TC-002 | test_defect_manifest - Manifest has 200 defects across all 12 rules | Manifest lists 200 distinct rows and every rule R01-R12 appears. | 200 defects, 200 distinct rows, rules=['R01', 'R02', 'R03', 'R04', 'R05', 'R06', 'R07', 'R08', 'R09', 'R10', 'R11', 'R12'] | PASS |
| REQ-03 | Data generation shall be reproducible for a given seed. | TC-003 | test_deterministic - Same seed gives identical output | Two runs with the same seed produce byte-identical files. | identical=True | PASS |
| REQ-09 | Only validated records shall be loaded: loaded = read - rejected. | TC-004 | test_loaded_counts - Loaded counts equal source minus rejected | cases/patients/drugs/events each contain 4,800 rows. | {'reporters': 150, 'patients': 4800, 'cases': 4800, 'drugs': 4800, 'events': 4800} | PASS |
| REQ-10 | Reporters shall be de-duplicated. | TC-005 | test_reporters_deduplicated - Reporters de-duplicated | Reporter rows equal distinct (name,type,country) values and are fewer than cases. | reporters=150, distinct=150 | PASS |
| REQ-11 | The target shall have referential integrity (no orphan rows). | TC-006 | test_referential_integrity - No orphan rows | Zero orphan drugs, events, cases->patients, cases->reporters. | {'drugs': 0, 'events': 0, 'patients': 0, 'reporters': 0} | PASS |
| REQ-12 | Reconciliation shall prove no data was lost or altered (counts, field checksums, record checksum). | TC-007 | test_reconciliation_passes - Clean migration reconciles | All 5 count checks, all 19 field checksums and the record checksum match. | counts=True, fields matched=19/19, record checksum=True | PASS |
| REQ-13 | Reconciliation shall detect an altered value in the target. | TC-008 | test_reconciliation_detects_tamper - Altered value detected | Changing one dose_mg in the target makes dose_mg checksum fail and names the case. | failed fields=['dose_mg'], example={'case_id': 'AE-000001', 'source': '10.00', 'target': '11.00'} | PASS |
| REQ-14 | Reconciliation shall detect a lost record in the target. | TC-009 | test_reconciliation_detects_loss - Lost record detected | Deleting one event row makes the events count check fail. | events expected=376, actual=375 | PASS |
| REQ-15 | Type changes during load (text to DECIMAL/DATE) shall not cause false reconciliation failures. | TC-010 | test_canonical_form - Canonicalisation is type-agnostic | '250' equals 250.00, '72.5' equals 72.50->72.5, date object equals ISO string, blank equals NULL. | checks=[True, True, True, True] | PASS |
| REQ-16 | The pipeline shall produce rejection log, reconciliation report and detection summary. | TC-011 | test_pipeline_artifacts - Pipeline writes all artefacts | rejections.csv, reconciliation_report.md/.json/fields.csv and detection_summary.json all exist. | {'rejections.csv': True, 'reconciliation_report.md': True, 'reconciliation_report.json': True, 'reconciliation_fields.csv': True, 'detection_summary.json': True} | PASS |
| REQ-04 | The target schema shall be normalized into cases, patients, drugs, events and reporters tables. | TC-012 | test_five_tables - Schema creates the five normalized tables | Exactly these five tables exist after schema creation. | tables=['cases', 'drugs', 'events', 'patients', 'reporters'] | PASS |
| REQ-05 | Relationships shall be enforced with foreign keys. | TC-013 | test_foreign_keys - Foreign keys defined between tables | cases->patients,reporters; drugs->cases; events->cases. | {'cases': {'reporters', 'patients'}, 'drugs': {'cases'}, 'events': {'cases'}} | PASS |
| REQ-06 | The schema shall be deployable to MySQL (InnoDB). | TC-014 | test_mysql_ddl - MySQL DDL export | Generated DDL contains CREATE TABLE for each table, FOREIGN KEY and ENGINE=InnoDB. | 5 CREATE TABLE statements; InnoDB=True | PASS |
| REQ-VAL-01 | R01 Mandatory fields: case_id, receive_date, drug_code, event_code and seriousness must be populated. | TC-015 | test_rule_rejects_violation[R01] - Rule rejects a record that violates it (and only that rule fires) | Record rejected by R01 only; reason logged. | Rules fired: ['R01']; reason: Missing mandatory field(s): drug_code | PASS |
| REQ-VAL-02 | R02 Case ID format: case_id must match the pattern AE-###### (six digits). | TC-016 | test_rule_rejects_violation[R02] - Rule rejects a record that violates it (and only that rule fires) | Record rejected by R02 only; reason logged. | Rules fired: ['R02']; reason: case_id 'AE-12' does not match AE-###### format | PASS |
| REQ-VAL-03 | R03 Duplicate case ID: case_id must be unique; first occurrence is kept, later ones are rejected. | TC-017 | test_rule_rejects_violation[R03] - Rule rejects a record that violates it (and only that rule fires) | Record rejected by R03 only; reason logged. | Rules fired: ['R03']; reason: Duplicate case_id 'AE-000001' (first occurrence retained) | PASS |
| REQ-VAL-04 | R04 Valid date format: Every populated date field must be a real calendar date in YYYY-MM-DD. | TC-018 | test_rule_rejects_violation[R04] - Rule rejects a record that violates it (and only that rule fires) | Record rejected by R04 only; reason logged. | Rules fired: ['R04']; reason: Invalid date in: receive_date='2024-02-30' | PASS |
| REQ-VAL-05 | R05 Receive date not in future: receive_date must not be later than the run date. | TC-019 | test_rule_rejects_violation[R05] - Rule rejects a record that violates it (and only that rule fires) | Record rejected by R05 only; reason logged. | Rules fired: ['R05']; reason: receive_date 2035-06-15 is in the future (as of 2026-11-11) | PASS |
| REQ-VAL-06 | R06 DOB before receive date: patient_dob must not be later than receive_date. | TC-020 | test_rule_rejects_violation[R06] - Rule rejects a record that violates it (and only that rule fires) | Record rejected by R06 only; reason logged. | Rules fired: ['R06']; reason: patient_dob 2024-07-01 is after receive_date 2024-06-01 | PASS |
| REQ-VAL-07 | R07 Therapy dates ordered: therapy_end must not be earlier than therapy_start. | TC-021 | test_rule_rejects_violation[R07] - Rule rejects a record that violates it (and only that rule fires) | Record rejected by R07 only; reason logged. | Rules fired: ['R07']; reason: therapy_end 2024-02-01 is before therapy_start 2024-03-01 | PASS |
| REQ-VAL-08 | R08 Onset after therapy start: event_onset must not be earlier than therapy_start. | TC-022 | test_rule_rejects_violation[R08] - Rule rejects a record that violates it (and only that rule fires) | Record rejected by R08 only; reason logged. | Rules fired: ['R08']; reason: event_onset 2024-02-01 is before therapy_start 2024-03-01 | PASS |
| REQ-VAL-09 | R09 Onset before receipt: event_onset must not be later than receive_date. | TC-023 | test_rule_rejects_violation[R09] - Rule rejects a record that violates it (and only that rule fires) | Record rejected by R09 only; reason logged. | Rules fired: ['R09']; reason: event_onset 2024-07-01 is after receive_date 2024-06-01 | PASS |
| REQ-VAL-10 | R10 Valid drug code: drug_code must exist in the drug reference list. | TC-024 | test_rule_rejects_violation[R10] - Rule rejects a record that violates it (and only that rule fires) | Record rejected by R10 only; reason logged. | Rules fired: ['R10']; reason: Unknown drug_code 'DRG999' | PASS |
| REQ-VAL-11 | R11 Valid event code: event_code must exist in the event reference list. | TC-025 | test_rule_rejects_violation[R11] - Rule rejects a record that violates it (and only that rule fires) | Record rejected by R11 only; reason logged. | Rules fired: ['R11']; reason: Unknown event_code 'EVT999' | PASS |
| REQ-VAL-12 | R12 Controlled terms: seriousness, outcome and patient_sex must come from their allowed value lists. | TC-026 | test_rule_rejects_violation[R12] - Rule rejects a record that violates it (and only that rule fires) | Record rejected by R12 only; reason logged. | Rules fired: ['R12']; reason: Value not in controlled list: seriousness='Maybe' | PASS |
| REQ-VAL-00 | A fully valid record shall pass all 12 rules. | TC-027 | test_valid_record_passes - Valid record accepted | No rejections; record present in clean output. | clean=1, rejections=0 | PASS |
| REQ-VAL-03 | On duplicate case IDs the first occurrence shall be retained. | TC-028 | test_duplicate_keeps_first - First duplicate kept, later one rejected | Row 2 kept, row 3 rejected. | clean rows=1, rejected source_row=[3] | PASS |
| REQ-07 | The validator shall detect every injected defect with no false positives. | TC-029 | test_detects_all_injected_defects - All 200 injected defects detected | 200/200 injected defects rejected under the intended rule; 0 false positives. | detected 200/200, missed=0, false_positives=0, wrong_rule=0 | PASS |
| REQ-08 | Each rejection shall be logged with source row, case ID, rule and reason. | TC-030 | test_rejection_log - Rejection log complete | rejections.csv exists; every entry has a non-empty rule_id and reason. | 200 entries; blank reasons=0 | PASS |

## 3. Deviations

None. All executed tests passed.

## 4. Approval

| Role | Name | Signature | Date |
|---|---|---|---|
| Author | | | |
| Reviewer | | | |
