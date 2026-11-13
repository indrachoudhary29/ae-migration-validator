# Requirements (traceability for the validation document)
REQ-01..03 data generation · REQ-04..06 schema · REQ-VAL-01..12 validation rules R01..R12 ·
REQ-07 defect detection · REQ-08 rejection log · REQ-09..11 load correctness ·
REQ-12..15 reconciliation · REQ-16 pipeline artefacts. Each test carries its requirement
in a `@pytest.mark.req(...)` marker; see `tests/`.
