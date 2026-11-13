"""Compare validator output with the injected-defect manifest (ground truth)."""
import pandas as pd


def evaluate_detection(manifest: pd.DataFrame, rejections: pd.DataFrame) -> dict:
    injected = {int(r.source_row): r.rule_id for r in manifest.itertuples()}
    triggered = {}
    for r in rejections.itertuples():
        triggered.setdefault(int(r.source_row), set()).add(r.rule_id)
    detected = [row for row in injected if row in triggered]
    missed = sorted(set(injected) - set(triggered))
    false_pos = sorted(set(triggered) - set(injected))
    wrong_rule = sorted(row for row in detected if injected[row] not in triggered[row])
    total = len(injected)
    return {"injected_total": total, "detected": len(detected), "missed_rows": missed,
            "false_positive_rows": false_pos, "wrong_rule_rows": wrong_rule,
            "detection_rate": (len(detected) / total) if total else 1.0}
