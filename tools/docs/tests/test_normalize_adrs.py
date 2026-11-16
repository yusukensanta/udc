from __future__ import annotations

import pathlib
import re

import pytest
from conftest import ADRS, edit

import normalize_adrs

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
A8 = "docs/adr/ADR-0008-errors.md"
A13 = "docs/adr/ADR-0013-state.md"


def test_repository_adrs_are_normalized():
    assert normalize_adrs.normalize(REPO_ROOT) == {}


def test_sections_are_numbered_and_related_adrs_are_built(tree):
    text = (tree / A13).read_text(encoding="utf-8")
    assert "## 1. Context" in text
    assert "### 6.1 Job state" in text
    assert text.rstrip().endswith("- [ADR-0008: Errors](ADR-0008-errors.md)")


def test_placeholders_are_resolved(tree):
    assert "See §6.1 and PRD §2.1." in (tree / A13).read_text(encoding="utf-8")
    assert "(ADR-0013 §6.1)" in (tree / A8).read_text(encoding="utf-8")


def test_normalize_is_idempotent(tree):
    assert normalize_adrs.normalize(tree) == {}


def test_tail_sections_are_reordered_and_references_follow(tree):
    path = tree / A8
    text = path.read_text(encoding="utf-8")
    moved = "## References\n\n- [x](https://example.com)\n\n## Late addition\n\nBody.\n"
    path.write_text(text.replace("## 1. Context", moved + "\n## 1. Context"), encoding="utf-8")
    new = normalize_adrs.normalize(tree)[path]
    titles = [line for line in new.splitlines() if line.startswith("## ")]
    assert titles[0] == "## 1. Late addition"
    assert titles[-2:] == ["## 12. References", "## 13. Related ADRs"]


def test_placeholders_in_other_documents_need_an_explicit_adr(tree):
    edit(tree, "README.md", "See the", "As ADR-0013 §{Job state} says, see the")
    changed = normalize_adrs.normalize(tree)
    assert "As ADR-0013 §6.1 says" in changed[tree / "README.md"]


@pytest.mark.parametrize(
    ("relative", "old", "new", "message"),
    [
        (A8, "Because of reasons.", "See §{No such section}.", "unresolved placeholder"),
        (A8, "## 5. Rationale", "## 5. Context", "duplicate sections ['Context']"),
        (A8, "# ADR-0008: Errors", "# Errors", "first line must be"),
        (A8, "Because of reasons.", "See ADR-0099.", "ADR-0099, which does not exist"),
        ("README.md", "See the", "See §{Context} and the", "unresolved placeholder"),
    ],
)
def test_problems_that_need_a_human(tree, relative, old, new, message):
    edit(tree, relative, old, new)
    with pytest.raises(normalize_adrs.NormalizeError, match=re.escape(message)):
        normalize_adrs.normalize(tree)


def test_headings_inside_code_fences_are_left_alone(tree):
    edit(tree, A8, "Because of reasons.", "```\n## Not a section\n### Nor this\n```")
    changed = normalize_adrs.normalize(tree)
    assert changed == {}


def test_placeholders_shown_as_code_are_left_alone(tree):
    edit(
        tree,
        "CONTRIBUTING.md",
        "Roadmap",
        "Write `§{Section title}` or `ADR-0013 §{Title}`. Roadmap",
    )
    edit(tree, A8, "Because of reasons.", "```\nSee §{Section title}.\n```")
    assert normalize_adrs.normalize(tree) == {}


def test_check_mode_reports_without_writing(tree, capsys):
    path = tree / A8
    edit(tree, A8, "## 5. Rationale", "## Rationale")
    before = path.read_text(encoding="utf-8")
    assert normalize_adrs.main([str(tree), "--check"]) == 1
    assert "would change: docs/adr/ADR-0008-errors.md" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == before


def test_write_mode_fixes_the_files(tree, capsys):
    edit(tree, A8, "## 5. Rationale", "## Rationale")
    assert normalize_adrs.main([str(tree)]) == 0
    assert "1 file(s) changed" in capsys.readouterr().out
    assert normalize_adrs.main([str(tree), "--check"]) == 0
    assert "ADRs are normalized" in capsys.readouterr().out


def test_main_returns_two_when_it_cannot_normalize(tree, capsys):
    edit(tree, A8, "# ADR-0008: Errors", "# Errors")
    assert normalize_adrs.main([str(tree)]) == 2
    assert "error:" in capsys.readouterr().out


def test_fixture_sources_are_unnumbered():
    # The fixture relies on the normalizer to number sections; guard that assumption.
    assert "## Context" in ADRS["ADR-0008-errors.md"]
