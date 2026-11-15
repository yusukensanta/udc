# ADR-0009: CLI and Job Configuration

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** The CLI surface, the user configuration format and versioning, configuration precedence, and how effective configuration is rendered.

## 1. Context

UDC is initially a CLI and library. Job configuration must be reproducible, portable, reviewable, and safe to store in source control. The CLI must support local use as well as large migrations whose options cannot reasonably be expressed only as shell flags.

## 2. Decision drivers

1. Good help, validation, subcommands, and shell completion.
2. Config files that can be version-controlled and reproduced.
3. Clear precedence between CLI flags, environment variables, and config files.
4. Secret references without embedding credentials in config or logs.
5. Forward-compatible configuration evolution.
6. A shared, checked-in configuration that an individual run or deployment can override without editing the file.

## 3. Options considered

| Concern | Options | Trade-offs |
|---|---|---|
| CLI parser | `clap`, `argh`, custom parser | `clap` is feature-rich; alternatives can reduce dependency/API surface; custom parsing increases maintenance |
| Config serialization | Serde with YAML/TOML/JSON | YAML is readable but has complex implicit typing; TOML is suitable for human-edited config; JSON is broadly interoperable |
| CLI-only configuration | Flags only | Convenient for simple jobs; unwieldy and hard to reproduce for complex mappings and policies |
| Precedence order | (a) flags, environment, file, defaults; (b) flags, file, environment, defaults | (a) lets a deployment override a shared file without editing it and matches the order operators know from other CLIs, but the file alone no longer determines a run. (b) makes the file authoritative, but an environment cannot override it and the order surprises operators |

## 4. Proposed decision

Use **clap** as the initial CLI parser candidate and Serde for typed configuration serialization. Evaluate TOML for human-authored job files and JSON for machine-generated/interchange output. The exact external config format and compatibility policy remain open until a sample job schema is implemented.

Resolve every setting in this order, highest precedence first:

1. Explicit CLI flags.
2. Documented, `UDC_`-prefixed environment variables.
3. The configuration file.
4. Built-in safe defaults.

## 5. Rationale

A parser should provide standard CLI behavior rather than become a custom project. Serde separates typed configuration models from textual formats. Configuration needs explicit versioning and must not serialize resolved secret values.

The configuration file is the shared, reviewed baseline. Environment variables are how one environment or one invocation deviates from it, so they must rank above the file; otherwise a deployment has to edit a checked-in file to change a setting. This is also the order that widely used CLIs document, including [Cargo](https://doc.rust-lang.org/cargo/reference/config.html) and the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html), so operators are not surprised.

Reproducibility does not come from ranking the file above the environment. It comes from recording what was actually used: see §8.

## 6. Initial command concepts

- `udc inspect` — report the schema, metadata, and adapter capabilities of a dataset. It reads and never writes.
- `udc convert` — plan and run a conversion job: schema classification, conversion, the validation levels the job selects, and publication. A plan-only form stops after planning and prints the schema compatibility classification and the effective plan, without reading row data for conversion or writing output.
- `udc validate` — compare two datasets that already exist; see §6.1.
- `udc job status`
- `udc job resume` — explicitly resume a failed or cancelled job; the contract is defined by ADR-0013 §9.
- `udc job abandon` — give up a failed or cancelled job: reconcile or withdraw its publication and release its retained staging, as ADR-0013 and ADR-0017 define.

The CLI also reports the build's version, target, source commit, and compiled-in adapters, as ADR-0019 requires. Exact flags are settled with the first implementation.

### 6.1 `udc validate`

`udc validate` compares a source dataset and a target dataset at the selected validation levels, under a declared schema mapping and the normalization rules of ADR-0006. It converts nothing and publishes nothing, and it reads both sides without writing to either.

It is a separate command, not a step of `udc convert`, for three reasons. A conversion performed by another tool can be checked with it. It is the command behind the option of narrowing UDC to validation ([PRD §13.3](../PRD.md#133-value-hypotheses-and-evidence-gates)). And dataset-to-snapshot validation (ADR-0015) is the same comparison with a table snapshot as the target.

- It runs as a job, so that it is bounded in memory and resumable like a conversion. The job is validation-only: it has no staged output and no publication step (ADR-0013).
- The two sides need not share a file layout. Evidence is computed for each side and compared for the whole dataset, and for each partition where both sides declare the same partitioning. A mismatch is therefore narrowed to fields and, at best, to partitions.
- The schema mapping is declared by the user; the default is the identity mapping. The result states its coverage as ADR-0006 requires. UDC does not know how another tool coerced values: a field whose mapping is lossy is compared after UDC's own coercion of the source, and a different coercion by the other tool appears as a mismatch.
- The validation performed inside `udc convert` and by `udc validate` use the same rules and produce the same evidence records.
- Exit status separates three outcomes: evidence agrees at every selected level; a mismatch (the Validation category of ADR-0008); and any other error. `udc convert` uses the same status for a job that fails on a validation mismatch.

The plain-file-to-table operations of ADR-0015 §9 use these commands when they are built: the compatibility check before registration is the plan-only form of a job whose target is a table, dataset-to-snapshot validation is `udc validate` with a table snapshot as the target, and validated ingestion is `udc convert` with a table target.

## 7. Configuration rules

- Apply the precedence order in §4 to every setting, and document each supported environment variable.
- Environment variables read by a cloud provider's own credential chain are not UDC configuration. They are consumed by identity resolution under ADR-0016 and do not take part in this precedence.
- Validate the full job plan before starting remote writes.
- Include a config schema/version and reject unknown critical settings rather than silently ignoring them.
- Accept only credential references or profile selectors, never secret values, in flags and config files by default. How a reference is resolved is defined by ADR-0016.
- Redact secret-like values from rendered plans, logs, and error messages.
- Keep execution tuning (memory, concurrency, batch size, retry and timeout policy) distinct from data semantics (schema mapping, validation, partition and output layout policy, publication target and mode).

## 8. Effective configuration

- UDC can render the effective configuration before execution, showing for each non-secret setting its value and where it came from: flag, environment variable, file, or default.
- The effective non-secret configuration is persisted with the job and covered by the job specification digest (ADR-0013). The digest, not the config file, identifies what a job ran with.
- A job that is recovered after a restart or explicitly resumed uses its persisted effective configuration. It does not re-read the current environment or config file.
- Data-semantics settings are inputs to the plan digest and cannot change once a plan is sealed. Execution-tuning settings may be overridden when a job is resumed; the overrides are recorded with the new execution generation (ADR-0013).
- A strict mode that rejects environment overrides is a candidate for CI and other runs that must be determined by the file alone.

## 9. Trade-offs and consequences

- Supporting multiple config formats increases documentation and compatibility burden; start with one human-authored format and JSON output if needed.
- CLI compatibility becomes a user-facing API and needs deprecation policy.
- Because environment variables rank above the file, a checked-in file alone does not determine a run. Rendering and persisting the effective configuration is therefore required, not optional.

## 10. Validation plan

Add golden tests for CLI help and config parsing; test precedence across all four sources, schema-version handling, secret redaction, malformed values, and deterministic rendering of effective job plans. Test that a resumed job ignores a changed environment for data-semantics settings and accepts an execution-tuning override. Test the three exit statuses of `udc validate`, and that it leaves both datasets unchanged.

## 11. Ownership boundary

**Owns:** commands and flags, the config file format and its versioning, configuration precedence, and rendering of effective configuration.

**Does not own:**
- The persisted job records that store the effective configuration — ADR-0013.
- Credential sources and their resolution order — ADR-0016.
- The meaning of an individual setting. That belongs to the ADR for its concern, for example ADR-0006 for validation levels, ADR-0012 for resource budgets, and ADR-0017 for the publication mode.
- The resume contract behind `udc job resume` — ADR-0013.
- What `udc validate` compares and what a result may claim — ADR-0006. How a mismatch is classified — ADR-0008.
- What abandoning a job does to its publication and staging — ADR-0013 and ADR-0017.

## 12. Revisit conditions

Revisit after the first stable CLI release or if SDK-first use cases become dominant.

## 13. Related ADRs

- [ADR-0006: Validation Semantics](ADR-0006-validation-semantics.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0015: Table Format Integration Boundary](ADR-0015-table-format-integration-boundary.md)
- [ADR-0016: Cloud Authentication and Credential Resolution](ADR-0016-cloud-authentication.md)
- [ADR-0017: Output Publication Protocol](ADR-0017-output-publication-protocol.md)
- [ADR-0019: Packaging, Release, and Distribution](ADR-0019-packaging-and-distribution.md)
