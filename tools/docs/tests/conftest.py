"""A minimal documentation tree that passes every check. Tests break one thing at a time."""

from __future__ import annotations

import pathlib

import pytest

import normalize_adrs

README = """# Project

See the [PRD](docs/PRD.md) and CONTRIBUTING.md. ADRs: ADR-0001 to ADR-0013.
"""

CONTRIBUTING = """# Contributing

Roadmap phases (Phase 0–2) are defined in the PRD.
"""

PRD = """# PRD

## 1. Summary

See §2 and FR-01. The MVP is Phases 0–1.

### FR-01: Convert

Text.

## 2. Roadmap

| Phase | Deliverable |
|---|---|
| Phase 0 | a |
| Phase 1 | b |
| Phase 2 | c |

### 2.1 Ownership

| Concern | Owns | Does not own | ADR |
|---|---|---|---|
| Core | x | y | ADR-0001 |

## 3. Status

| ADR | Topic | Status |
|---|---|---|
| [ADR-0001](adr/ADR-0001-architecture.md) | t | Accepted |
| [ADR-0008](adr/ADR-0008-errors.md) | t | Proposed |
| [ADR-0013](adr/ADR-0013-state.md) | t | Proposed |
"""

ADR_TEMPLATE = """# ADR-{num}: {title}

- **Status:** {status}
- **Date:** 2026-01-01
- **Decision owners:** Maintainers
- **Scope:** {title}.

## Context

Text about context.

## Decision drivers

1. One driver.

## Options considered

| Option | Strengths | Limitations |
|---|---|---|
| A | s | l |
| B | s | l |

## Decision

Do A.

## Rationale

Because of reasons.

{extra}
## Trade-offs and consequences

- A cost.

## Validation plan

Test it.

## Ownership boundary

**Owns:** this concern.

**Does not own:**
{not_owned}

## Revisit conditions

Revisit later.
"""

ADRS = {
    "ADR-0001-architecture.md": ADR_TEMPLATE.format(
        num="0001",
        title="Architecture",
        status="Accepted",
        extra="""## Scope map

| ADR | Owns | Does not own |
|---|---|---|
| 0001 | a | b |
| 0008 | a | b |
| 0013 | a | b |

| Concern | Owns | Must not own | ADR |
|---|---|---|---|
| Core | x | y | ADR-0001 |
""",
        not_owned="- Errors — ADR-0008.\n- State — ADR-0013.",
    ),
    "ADR-0008-errors.md": ADR_TEMPLATE.format(
        num="0008",
        title="Errors",
        status="Proposed",
        extra="""## Error categories

| Category | Examples | Retry |
|---|---|---|
| Transient | timeout | yes |
| Conflict | changed | no |

A unit that exhausts its budget becomes FAILED with a Transient error (ADR-0013 §{Job state}).
""",
        not_owned="- State — ADR-0013.\n- Scope map — ADR-0001.",
    ),
    "ADR-0013-state.md": ADR_TEMPLATE.format(
        num="0013",
        title="State",
        status="Proposed",
        extra="""## State machines and legal transitions

### Job state

| Current state | Allowed next states | Notes |
|---|---|---|
| RUNNING | FAILED, SUCCEEDED, RETRY_WAIT | n |
| RETRY_WAIT | RUNNING | n |

Validation uses L1 and L2. See §{Job state} and PRD §2.1.
""",
        not_owned="- Errors, such as a Conflict error — ADR-0008.",
    ),
}


@pytest.fixture
def tree(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    (tmp_path / "CONTRIBUTING.md").write_text(CONTRIBUTING, encoding="utf-8")
    (tmp_path / "docs" / "PRD.md").write_text(PRD, encoding="utf-8")
    for name, text in ADRS.items():
        (tmp_path / "docs" / "adr" / name).write_text(text, encoding="utf-8")
    for path, text in normalize_adrs.normalize(tmp_path).items():
        path.write_text(text, encoding="utf-8")
    return tmp_path


def edit(root: pathlib.Path, relative: str, old: str, new: str) -> None:
    """Replace exactly one occurrence of old with new in a file of the tree."""
    path = root / relative
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{relative}: expected one {old!r}, found {text.count(old)}"
    path.write_text(text.replace(old, new), encoding="utf-8")
