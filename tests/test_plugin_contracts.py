from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_claude_manifest_is_valid_json_with_required_fields() -> None:
    payload = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert payload["name"] == "reverse-engineering"
    assert payload["description"]
    assert payload["author"]["name"]


def test_codex_manifest_mentions_repo_analysis_and_security_category() -> None:
    payload = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert payload["name"] == "reverse-engineering"
    assert payload["interface"]["category"] == "Security"
    assert "repo" in payload["description"].lower()
    assert "binary" in payload["description"].lower()
    assert "ioc" in payload["description"].lower()


def test_repo_skill_has_static_first_pause_and_outputs() -> None:
    text = (ROOT / "skills" / "repo-reverse-engineering" / "SKILL.md").read_text(encoding="utf-8")
    assert "static-first" in text.lower()
    assert "PAUSE" in text
    assert "Markdown report" in text
    assert "repo_corpus.jsonl" in text


def test_shipped_files_do_not_contain_local_absolute_paths_or_powershell_only_commands() -> None:
    shipped_roots = [ROOT / "README.md", ROOT / "references", ROOT / "skills", ROOT / "scripts"]
    files: list[Path] = []
    for root in shipped_roots:
        if root.is_file():
            files.append(root)
        else:
            files.extend(
                path
                for path in root.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts
            )

    forbidden = ["C:\\Users\\Test-User", "Select-String", "Get-Content", "powershell"]
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in forbidden:
            assert marker not in text, f"{marker} found in {path}"


def test_required_skill_frontmatter_exists() -> None:
    for name in (
        "reverse-engineering",
        "repo-reverse-engineering",
        "binary-triage",
        "ioc-extraction",
        "unpacking-analysis",
        "android-reverse-engineering",
        "ghidra-headless",
        "re-parity-review",
    ):
        path = ROOT / "skills" / name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert f"name: {name}" in text
        assert "description:" in text


def test_router_mentions_all_domain_skills() -> None:
    text = (ROOT / "skills" / "reverse-engineering" / "SKILL.md").read_text(encoding="utf-8")
    for name in (
        "repo-reverse-engineering",
        "binary-triage",
        "ioc-extraction",
        "unpacking-analysis",
        "android-reverse-engineering",
        "ghidra-headless",
        "re-parity-review",
    ):
        assert name in text


def test_safety_gate_present_in_dynamic_risk_skills() -> None:
    for name in ("binary-triage", "unpacking-analysis", "repo-reverse-engineering", "ghidra-headless"):
        text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "PAUSE" in text


def test_parity_skill_states_anti_false_positive_signals() -> None:
    text = (ROOT / "skills" / "re-parity-review" / "SKILL.md").read_text(encoding="utf-8")
    for needle in ("negative evidence", "checker", "not_match", "source-backed"):
        assert needle in text, needle


def test_unpacking_skill_states_static_first_tree_and_upx() -> None:
    text = (ROOT / "skills" / "unpacking-analysis" / "SKILL.md").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "static-first" in lowered
    assert "upx" in lowered
    assert "PAUSE" in text


def test_ioc_skill_requires_evidence_snippet() -> None:
    text = (ROOT / "skills" / "ioc-extraction" / "SKILL.md").read_text(encoding="utf-8")
    assert "evidence_snippet" in text
