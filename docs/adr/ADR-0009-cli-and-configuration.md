# ADR-0009: CLI and Job Configuration

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers

## Context

UDC is initially a CLI and library. Job configuration must be reproducible, portable, reviewable, and safe to store in source control. The CLI must support local use as well as large migrations whose options cannot reasonably be expressed only as shell flags.

## Decision drivers

1. Good help, validation, subcommands, and shell completion.
2. Config files that can be version-controlled and reproduced.
3. Clear precedence between CLI flags, config files, and environment variables.
4. Secret references without embedding credentials in config or logs.
5. Forward-compatible configuration evolution.

## Options considered

| Concern | Options | Trade-offs |
|---|---|---|
| CLI parser | `clap`, `argh`, custom parser | `clap` is feature-rich; alternatives can reduce dependency/API surface; custom parsing increases maintenance |
| Config serialization | Serde with YAML/TOML/JSON | YAML is readable but has complex implicit typing; TOML is suitable for human-edited config; JSON is broadly interoperable |
| CLI-only configuration | Flags only | Convenient for simple jobs; unwieldy and hard to reproduce for complex mappings and policies |

## Proposed decision

Use **clap** as the initial CLI parser candidate and Serde for typed configuration serialization. Evaluate TOML for human-authored job files and JSON for machine-generated/interchange output. The exact external config format and compatibility policy remain open until a sample job schema is implemented.

## Rationale

A parser should provide standard CLI behavior rather than become a custom project. Serde separates typed configuration models from textual formats. Configuration needs explicit versioning and must not serialize resolved secret values.

## Configuration rules

- Define and document precedence: explicit CLI overrides, then config file, then documented environment variables, then safe defaults.
- Validate the full job plan before starting remote writes.
- Include a config schema/version and reject unknown critical settings rather than silently ignoring them.
- Resolve credentials through provider-native chains or secret references; never accept secrets in command-line arguments by default.
- Redact secret-like values from rendered plans, logs, and error messages.
- Keep execution tuning (memory, concurrency, batch size) distinct from data semantics (schema mapping, validation, partition policy).

## Trade-offs and consequences

- Supporting multiple config formats increases documentation and compatibility burden; start with one human-authored format and JSON output if needed.
- CLI compatibility becomes a user-facing API and needs deprecation policy.
- Environment variable precedence can make runs less reproducible; report effective non-secret settings in the plan.

## Validation plan

Add golden tests for CLI help and config parsing; test precedence, schema-version handling, secret redaction, malformed values, and deterministic rendering of effective job plans.

## Revisit conditions

Revisit after the first stable CLI release or if SDK-first use cases become dominant.
