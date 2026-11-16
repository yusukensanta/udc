# Documentation checks

Two scripts keep the README, the PRD, and the ADRs consistent with each other. CI runs them on every push and pull request ([workflow](../../.github/workflows/docs.yml)).

| Script | What it does |
|---|---|
| `check_docs.py` | Reports problems and changes nothing. Exit status 1 if any check fails. |
| `normalize_adrs.py` | Rewrites ADRs into the standard shape: tail sections in order, sections renumbered, `Related ADRs` rebuilt, `§{Title}` placeholders resolved. `--check` only reports. |

## Running them

The scripts use only the Python standard library. [uv](https://docs.astral.sh/uv/) provides the test and lint tools.

```sh
cd tools/docs
uv run python normalize_adrs.py ../..          # fix what can be fixed mechanically
uv run python check_docs.py ../..              # report everything else
uv run python check_docs.py ../.. --list-refs  # also list every section reference and its target
uv run pytest                                  # tests for the scripts; coverage must stay at 80% or more
uv run ruff format . && uv run ruff check .
```

## What `check_docs.py` checks

- **Links.** Relative links and their anchors resolve.
- **ADR header.** The title is `# ADR-NNNN: Title` and matches the file name. Status, Date, Decision owners, and Scope are present and not empty; the status is a known one and the date is `YYYY-MM-DD`.
- **ADR sections.** Sections and subsections are numbered in order. Context, Decision drivers, Options considered, a decision section, Rationale, Trade-offs and consequences, Validation plan, Ownership boundary, Revisit conditions, and Related ADRs each appear once and are not empty. Options considered lists at least two options. The tail sections are in the standard order.
- **Ownership boundary.** It states what the ADR owns, and every item it does not own names the ADR or the PRD that does.
- **Related ADRs.** The list is exactly the set of ADRs mentioned in the body, and each exists.
- **Section references.** `ADR-NNNN §x.y`, a bare `§x.y` inside an ADR, `PRD §x.y`, and requirement ids such as `FR-05` resolve.
- **Status table.** The PRD status table agrees with every ADR header.
- **ADR-0001.** Its scope map has a row for every ADR, and the PRD repeats its ownership table row for row.
- **Shared terms.** State names exist in the state tables of ADR-0013, error categories in the table of ADR-0008, validation levels are L1 to L5, and roadmap phases exist in the PRD roadmap.
- **Retired wording.** Terms that an earlier revision replaced have not come back.
- **README.** The stated ADR range matches the files.

## Adding or moving a section

Section numbers change when a section is added or moved, and other documents refer to sections by number. Write a new reference as `§{Section title}`, or `ADR-0013 §{Section title}` from another document, and run `normalize_adrs.py`; it replaces the placeholder with the current number. Before moving existing sections, check the output of `--list-refs` before and after: every reference must still point at the same title.
