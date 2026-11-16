# Contributing to UDC

Thank you for your interest in UDC.

UDC is an OSS-first project focused on data integrity and reliable execution of data-format conversion jobs. Contributions of all sizes are welcome, including bug reports, documentation improvements, tests, and code.

## Current status

UDC is in the product-definition and architecture stage. The implementation and contribution workflow may evolve as the initial architecture is validated.

## Before contributing

1. Read [the PRD](docs/PRD.md).
2. Check existing issues and discussions before starting significant work.
3. For architectural changes, propose an Architecture Decision Record (ADR) that follows the [ADR conventions](#adr-conventions).
4. For new format or storage integrations, describe the capability and compatibility boundaries.

## Design principles

- Keep file formats, table formats, storage, catalogs, execution engines, and orchestration as separate concerns.
- Prefer established format implementations over reimplementing specifications.
- Make unsupported capabilities explicit.
- Never silently perform lossy schema conversions.
- Treat validation and safe publication as first-class features.
- Do not log credentials or sensitive configuration.

## ADR conventions

ADRs live in [docs/adr](docs/adr/). They stay consistent only if each concern has exactly one owner.

- **One concern, one ADR.** [ADR-0001](docs/adr/ADR-0001-initial-architecture.md) holds the responsibility map, the ADR scope map, and the shared vocabulary. A new ADR, or a change to an ADR's scope, must update ADR-0001 in the same pull request.
- **Reference, do not restate.** An ADR that depends on another concern points to the owning ADR instead of redefining its contract. If two ADRs disagree, the owner in the scope map wins and the other is amended.
- **Header.** Every ADR starts with Status, Date, Decision owners, and Scope. ADRs carry no priority labels; capability priority (P0–P3) and roadmap phases (Phase 0–8) are defined only in the [PRD](docs/PRD.md).
- **Sections.** Sections are numbered and follow this order: Context, Decision drivers, Options considered, Decision (or Proposed decision), Rationale, topic-specific sections, Trade-offs and consequences, Validation plan, Ownership boundary, Revisit conditions, References, Related ADRs. All of them are required and none may be empty, except topic-specific sections and References. Options considered lists at least two options. References is expected where the ADR names an external library, product, or specification.
- **Ownership boundary.** State what the ADR owns and, for each neighbouring concern it does not own, the ADR that does.
- **Shared terms.** Use the vocabulary in ADR-0001, the validation level names (L1–L5) from ADR-0006, and the error categories from ADR-0008. Define a new term instead of giving an existing one a second meaning.
- **Status.** The status in the ADR header is authoritative. Update the status table in the PRD and any mention in the README in the same pull request.
- **Section references.** Sections are referred to by number, so adding or moving a section can break references elsewhere. Write a new reference as `§{Section title}` and let the normalizer number it.
- **Checks.** Run the scripts in [tools/docs](tools/docs/README.md) before opening a pull request: `normalize_adrs.py` puts an ADR into the standard shape, and `check_docs.py` reports missing fields, broken references, and terms used inconsistently. CI runs both.

## Proposed contribution workflow

1. Open or find an issue describing the problem.
2. Discuss scope and design for non-trivial changes.
3. Submit a focused pull request.
4. Include tests and documentation.
5. Describe compatibility implications and known limitations.

## Using AI tools

AI-assisted development tools (including code completion, chat assistants, and coding agents) are permitted. Their use does not change the standards expected of a contribution: the human contributor remains responsible for the submitted work.

When using AI tools, contributors must:

- **Understand and own the changes.** Review generated or modified code line by line. Be prepared to explain its behavior, design choices, edge cases, and trade-offs. Do not submit code you do not understand.
- **Verify claims and outputs.** Treat generated explanations, APIs, dependency recommendations, benchmark results, and security advice as untrusted until checked against authoritative documentation, source code, or reproducible tests.
- **Run appropriate checks.** Run relevant formatting, linting, unit, integration, and compatibility tests. Clearly state which checks were run and which were not; never claim that an AI agent ran or passed checks unless you verified the result.
- **Review the complete diff.** Check for unrelated edits, placeholder implementations, dead code, accidental generated files, weakened tests, broad exception handling, unsafe defaults, and changes outside the intended scope.
- **Check dependencies and licensing.** Verify the origin, license, maintenance status, and security implications of generated or suggested dependencies and copied code. Do not assume AI-generated code is original or correctly attributed.
- **Protect confidential information.** Do not provide secrets, access tokens, private keys, credentials, private customer data, or non-public datasets to AI services. Follow any applicable service, organization, and data-handling policies.
- **Keep changes transparent.** If AI tools materially generated or substantially modified code, tests, documentation, or design content, disclose that use in the pull request description. A brief statement naming the tool (if known) and the kind of assistance is sufficient. Routine autocomplete, spelling correction, or brainstorming that did not materially shape the contribution does not need to be reported.
- **Do not delegate project decisions to an agent.** AI tools may help explore options or prepare a proposal, but architectural decisions, compatibility claims, security-sensitive changes, and acceptance of trade-offs must be reviewed and owned by the contributor and maintainers.

AI-generated tests do not replace independent test design. In particular, tests should include boundary conditions and failure cases and should not merely encode the implementation's assumptions.

A suggested disclosure in a pull request is:

> **AI assistance:** [Tool name, if applicable] was used to [briefly describe the contribution, such as drafting tests, refactoring, or preparing documentation]. I reviewed the resulting changes and verified them with [tests/checks, or state that no automated checks were run].

There is no blanket requirement to avoid AI tools or to disclose every minor use. The goal is accountable, reviewable contributions—not tool policing.

## Pull request expectations

A pull request should help reviewers understand both the change and its evidence. Include, as applicable:

- **Purpose:** the problem being solved and relevant issue/discussion.
- **Scope:** what changed and what intentionally did not change.
- **Design:** important decisions, alternatives, and compatibility implications.
- **Validation:** commands and tests actually executed, plus any untested areas.
- **Operational impact:** performance, memory, retry, recovery, security, and publication implications where relevant.
- **AI assistance:** a short disclosure when AI materially contributed, as described above.

Keep pull requests focused. Large generated changes should be split into reviewable units where practical. Do not use AI to manufacture reviews, test evidence, benchmark results, citations, or contributor identity.

## Reporting bugs

Include:

- UDC version or commit.
- Operating system and Rust toolchain.
- Source and target format.
- Storage provider and authentication method (never include secrets).
- Minimal reproduction steps.
- Expected and actual behavior.
- Relevant sanitized logs.

## License

UDC is licensed under the [Apache License 2.0](LICENSE). Unless you state otherwise, a contribution you submit is licensed under the same terms, as section 5 of the license provides.
