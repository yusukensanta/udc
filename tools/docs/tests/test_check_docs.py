from __future__ import annotations

import pathlib

import pytest
from conftest import edit

import check_docs

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
A1 = "docs/adr/ADR-0001-architecture.md"
A8 = "docs/adr/ADR-0008-errors.md"
A13 = "docs/adr/ADR-0013-state.md"
PRD = "docs/PRD.md"


def test_minimal_tree_passes(tree):
    assert check_docs.run(tree) == []


def test_repository_docs_pass():
    assert check_docs.run(REPO_ROOT) == []


# (file, old text, new text, text expected in one of the reported problems)
BREAKAGES = [
    ("README.md", "docs/PRD.md", "docs/NOPE.md", "broken link docs/NOPE.md"),
    ("README.md", "(docs/PRD.md)", "(docs/PRD.md#nope)", "broken anchor"),
    (A8, "- **Status:** Proposed\n", "", "header missing Status"),
    (A8, "- **Scope:** Errors.", "- **Scope:**", "header field Scope is empty"),
    (A8, "- **Status:** Proposed", "- **Status:** Draft", "unknown status 'Draft'"),
    (A8, "2026-01-01", "01/01/2026", "is not YYYY-MM-DD"),
    (A8, "- **Scope:**", "- **Priority:** P0\n- **Scope:**", "no Priority header"),
    (A8, "# ADR-0008: Errors", "# Errors", "first line must be"),
    (A8, "# ADR-0008: Errors", "# ADR-0009: Errors", "differs from the file name"),
    (A8, "## 1. Context", "## 7. Context", "section 1 misnumbered"),
    (A13, "### 6.1 Job state", "### 6.9 Job state", "subsection misnumbered"),
    (A8, "## 5. Rationale", "## 5. Reasons", "expected exactly one 'Rationale' section, found 0"),
    (A8, "## 4. Decision\n", "## 4. Outcome\n", "no decision section"),
    (A8, "Text about context.\n", "", "section 'Context' is empty"),
    (A8, "| B | s | l |\n", "", "needs at least two options"),
    (A8, "**Owns:** this concern.", "This concern.", "has no '**Owns:**'"),
    (A8, "**Does not own:**", "Other concerns:", "has no '**Does not own:**'"),
    (A8, "- State — ADR-0013.", "- State.", "names no owner"),
    (
        A13,
        "- [ADR-0008: Errors](ADR-0008-errors.md)\n",
        "",
        "Related ADRs mismatch, missing ['0008']",
    ),
    (A13, "Text about context.", "See ADR-0099.", "refers to ADR-0099, which does not exist"),
    (A8, "Because of reasons.", "See ADR-0013 §99.", "unresolved reference ADR-0013 §99"),
    (A8, "Because of reasons.", "See §{Context}.", "placeholder remains"),
    (A8, "Because of reasons.", "See PRD §42.", "unresolved reference PRD §42"),
    (PRD, "See §2 and", "See §77 and", "unresolved reference PRD §77"),
    (A8, "Because of reasons.", "Required by FR-99.", "unknown requirement FR-99"),
    (PRD, "errors.md) | t | Proposed |", "errors.md) | t | Accepted |", "ADR-0008 is 'Accepted'"),
    (PRD, "| [ADR-0008](adr/ADR-0008-errors.md) | t | Proposed |\n", "", "no row for ADR-0008"),
    (A1, "| 0008 | a | b |\n", "", "scope map: no row for 0008"),
    (PRD, "| Core | x | y | ADR-0001 |", "| Core | x | z | ADR-0001 |", "ownership table differs"),
    (
        PRD,
        "| Concern | Owns | Does not own | ADR |",
        "| Concern | Has | Lacks | ADR |",
        "not found",
    ),
    (A8, "Because of reasons.", "The job is EXPLODING.", "state EXPLODING is not defined"),
    (A8, "Because of reasons.", "It waits in RETRY_LATER.", "state RETRY_LATER is not defined"),
    (A8, "Because of reasons.", "Checked at L9.", "validation level L9 does not exist"),
    (A8, "Because of reasons.", "Fails with a Mismatch error.", "'Mismatch' is not defined"),
    (A8, "Because of reasons.", "Planned for Phase 7.", "Phase 7 is not in the PRD roadmap"),
    ("CONTRIBUTING.md", "Phase 0–2", "Phase 0–1", "'Phase 0–1' but the roadmap ends at 2"),
    (
        A8,
        "Because of reasons.",
        "The Job Coordinator decides.",
        "retired wording 'Job Coordinator'",
    ),
    ("README.md", "ADR-0001 to ADR-0013", "ADR-0001 to ADR-0019", "the last ADR is 0013"),
    (A8, "Because of reasons.", "The number of times a row occurs is", "text ends mid-sentence"),
    (A8, "| A | s | l |", "| A | s | limited by the |", "text ends mid-sentence"),
    (A8, "- A cost.", "- A cost that grows with", "text ends mid-sentence"),
]


@pytest.mark.parametrize(("relative", "old", "new", "expected"), BREAKAGES)
def test_each_breakage_is_reported(tree, relative, old, new, expected):
    edit(tree, relative, old, new)
    problems = check_docs.run(tree)
    assert any(expected in problem for problem in problems), problems


def test_tail_sections_out_of_order(tree):
    path = tree / A8
    text = path.read_text(encoding="utf-8")
    swapped = (
        text.replace("Validation plan\n", "@@\n")
        .replace("Ownership boundary\n", "Validation plan\n")
        .replace("@@\n", "Ownership boundary\n")
    )
    path.write_text(swapped, encoding="utf-8")
    assert any("tail sections out of order" in p for p in check_docs.run(tree))


def test_missing_adr_0001_is_reported(tree):
    (tree / A1).unlink()
    assert any("ADR-0001 is missing" in p for p in check_docs.run(tree))


def test_file_names_ending_in_md_are_not_states(tree):
    # README mentions CONTRIBUTING.md, which looks like a state name but is a file.
    assert "CONTRIBUTING.md" in (tree / "README.md").read_text(encoding="utf-8")
    assert check_docs.run(tree) == []


def test_placeholders_shown_as_code_are_not_reported(tree):
    edit(tree, "CONTRIBUTING.md", "Roadmap", "Write `§{Section title}`. Roadmap")
    edit(tree, A8, "Because of reasons.", "```\nSee §{Section title}.\n```")
    assert check_docs.run(tree) == []


def test_short_cells_are_not_sentences(tree):
    edit(tree, A8, "| B | s | l |", "| B | s | a |")
    assert check_docs.run(tree) == []


def test_table_headers_and_code_may_end_on_any_word(tree):
    edit(tree, A8, "| Option | Strengths | Limitations |", "| Option | Owned by | Defined in |")
    edit(tree, A8, "Because of reasons.", "Because of reasons.\n\n```\nvalue is\n```")
    assert check_docs.run(tree) == []


def test_headings_inside_code_fences_are_ignored():
    text = "# Title\n\n```\n## 1. Not a heading\n```\n\n## 1. Real\n"
    assert check_docs.headings(text) == [(1, "Title"), (2, "1. Real")]


def test_slug_matches_github_anchors():
    assert check_docs.slug("2.5 Existing tools and where UDC fits") == (
        "25-existing-tools-and-where-udc-fits"
    )


def test_main_reports_success_and_lists_references(tree, capsys):
    assert check_docs.main([str(tree), "--list-refs"]) == 0
    out = capsys.readouterr().out
    assert "ADR-0013 §6.1 -> Job state" in out
    assert "all checks passed across 6 files" in out


def test_main_returns_one_and_prints_problems(tree, capsys):
    edit(tree, A8, "- **Status:** Proposed", "- **Status:** Draft")
    assert check_docs.main([str(tree)]) == 1
    assert "unknown status" in capsys.readouterr().out
