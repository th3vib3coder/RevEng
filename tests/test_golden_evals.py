from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_golden_evals_emit_labeled_metrics_and_json_summary(tmp_path: Path) -> None:
    summary_out = tmp_path / "golden-summary.json"

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_golden_evals.py"), "--json-out", str(summary_out)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    summary = json.loads(summary_out.read_text(encoding="utf-8"))
    assert summary["schema"] == "reveng.golden_evals.v1"
    assert summary["metrics"] == {
        "assertions": summary["metrics"]["assertions"],
        "false_positives": 0,
        "false_negatives": 0,
        "missing_evidence": 0,
        "unsafe_actions": 0,
    }
    assert summary["metrics"]["assertions"] > 0

    cases = {case["name"]: case for case in summary["cases"]}
    assert "ghidra_fake_graph_export" in cases
    for case in cases.values():
        assert case["status"] == "passed"
        assert case["capability"]
        assert set(case["metrics"]) == {
            "assertions",
            "false_positives",
            "false_negatives",
            "missing_evidence",
            "unsafe_actions",
        }
        assert case["metrics"]["unsafe_actions"] == 0
