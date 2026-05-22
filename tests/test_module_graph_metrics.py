from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import repo_map  # noqa: E402


def test_module_graph_metrics_counts_fan_and_detects_two_cycle() -> None:
    edges = [
        {"from": "pkg.a", "to": "pkg.b", "import": "pkg.b"},
        {"from": "pkg.b", "to": "pkg.a", "import": "pkg.a"},
        {"from": "pkg.a", "to": "pkg.util", "import": "pkg.util"},
    ]
    metrics = repo_map.module_graph_metrics(["pkg.a", "pkg.b", "pkg.util"], edges)
    assert metrics["fan_out"]["pkg.a"] == 2
    assert metrics["fan_in"]["pkg.a"] == 1
    assert metrics["fan_in"]["pkg.util"] == 1
    assert ["pkg.a", "pkg.b"] in metrics["cycles"]


def test_module_graph_metrics_detects_three_cycle_and_ignores_acyclic() -> None:
    cyclic = repo_map.module_graph_metrics(
        ["a", "b", "c"],
        [
            {"from": "a", "to": "b", "import": "b"},
            {"from": "b", "to": "c", "import": "c"},
            {"from": "c", "to": "a", "import": "a"},
        ],
    )
    assert ["a", "b", "c"] in cyclic["cycles"]

    acyclic = repo_map.module_graph_metrics(
        ["a", "b", "c"],
        [
            {"from": "a", "to": "b", "import": "b"},
            {"from": "b", "to": "c", "import": "c"},
        ],
    )
    assert acyclic["cycles"] == []
