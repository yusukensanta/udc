# Contributing to UDC

Thank you for your interest in UDC.

UDC is an OSS-first project focused on data format interoperability, cross-cloud migration, and data integrity.

## Current status

UDC is in the product-definition and architecture stage. The implementation and contribution workflow may evolve as the initial architecture is validated.

## Before contributing

1. Read [the PRD](docs/PRD.md).
2. Check existing issues and discussions before starting significant work.
3. For architectural changes, propose an Architecture Decision Record (ADR).
4. For new format or storage integrations, describe the capability and compatibility boundaries.

## Design principles

- Keep file formats, table formats, storage, catalogs, execution engines, and orchestration as separate concerns.
- Prefer established format implementations over reimplementing specifications.
- Make unsupported capabilities explicit.
- Never silently perform lossy schema conversions.
- Treat validation and safe publication as first-class features.
- Do not log credentials or sensitive configuration.

## Proposed contribution workflow

1. Open or find an issue describing the problem.
2. Discuss scope and design for non-trivial changes.
3. Submit a focused pull request.
4. Include tests and documentation.
5. Describe compatibility implications and known limitations.

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

By contributing, you agree that your contributions are submitted under the project's license, which is intended to be Apache License 2.0, subject to confirmation in the repository.
