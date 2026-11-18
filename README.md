# UDC — Universal Data Converter

**Verified, resumable conversion jobs for plain-file datasets.**

UDC is an open-source command-line tool and library that runs data-format conversions as jobs whose result can be checked.

Its goal is to make a conversion trustworthy: the schema mapping is classified before data moves, the output is validated against the source under published rules, an interrupted job resumes from completed work, and only validated output is published.

> **Status:** Product definition and architecture design. This repository currently contains documentation, the scripts that check it, evidence tooling, and an empty Rust workspace. There is no product logic or released implementation yet, and no format or cloud integration should be considered supported until it is implemented here and covered by tests.

## What is in this repository

```text
README.md          Project overview (this file)
CONTRIBUTING.md    Contribution guidelines, ADR conventions, and AI-assistance policy
SECURITY.md        How to report a vulnerability privately
Cargo.toml         Rust workspace; rust-toolchain.toml pins the toolchain (ADR-0002)
deny.toml          Dependency license, advisory, and source rules (ADR-0011)
crates/
  udc-core/        Core library (empty)
  udc-cli/         The `udc` command (empty)
docs/
  PRD.md           Product Requirements Document (draft)
  adr/             Architecture Decision Records, ADR-0001 to ADR-0019
tools/
  docs/            Consistency checks for the documentation, run in CI
  s3/              S3 behaviour tests and a disposable local S3 store (RustFS), run in CI
tests/
  benchmarks/reference-config/  The reference configuration and the H2 interruption tests (PRD §13.3)
```

The planned crate and directory organization is illustrated in [PRD §11.2](docs/PRD.md#112-illustrative-repository-organization). Those directories do not exist yet; each will be added when the functionality it holds is implemented.

## Product pillars

These describe the intended product, not current capabilities.

- **Data integrity:** schema compatibility classified before data moves, and validation of the output against the source under published rules, with the guarantee of each result stated.
- **Reliable job execution:** bounded resource use, staged output, retry, durable work-unit completion, resume, and publication of validated output only.
- **Format coverage:** Parquet, CSV, and JSON first; Avro, ORC, and Arrow IPC later; Apache Iceberg as the first table format. Formats are added where the job layer is needed, and the full list with priorities is in [PRD §5](docs/PRD.md#5-product-scope-and-capability-taxonomy).
- **Storage reach:** local filesystem, Amazon S3, Google Cloud Storage, and Azure Blob Storage.

The first two pillars are where UDC intends to differ from existing tools. The last two are prerequisites, built on existing libraries, and are not what UDC competes on.

## MVP direction

The initial MVP is a single-node CLI and library for local and cross-cloud file conversion of Parquet, CSV, and JSON. It uses a streaming reader-to-writer pipeline with Apache Arrow as the in-memory interchange layer, plus schema, row-count, and logical-fingerprint validation under published normalization rules, restart recovery, and safe publication of validated output. The execution backend remains under evaluation; see [ADR-0004](docs/adr/ADR-0004-execution-engine-selection.md).

UDC is designed for datasets larger than process memory: bounded streaming, byte-aware backpressure, partitionable work units, independent I/O and CPU limits, and recoverable staging are architectural requirements. The work plan is designed to preserve a future scale-out path.

See the [PRD](docs/PRD.md) for scope, requirements, acceptance criteria, proposed architecture, and roadmap.

## Relation to existing tools

Format conversion and access to these storage systems are already well served by tools such as DuckDB, clickhouse-local, and rclone. UDC does not aim to compete on those, and it does not offer a plain copy of objects between stores: a job may read from one provider and write to another, but it always converts and checks the data.

Its intended contribution is the job layer around a conversion: schema compatibility classified before data moves, validation evidence under published rules, resume from completed work, and publication of validated output only. It targets datasets stored as plain files rather than in a table format, and delivers this as a single binary.

Plain files have no transaction log, so UDC does not claim an atomic commit for readers that list a prefix. Its default guarantee is narrower: nothing appears in the destination before the whole output has passed validation, and a job that fails before publication leaves the destination unchanged.

After the MVP, the same job layer is planned for the path from plain files to an Iceberg table: checking files against a table schema before they are registered, validating a table against the files it came from, and loading files that need a rewrite with validation before the commit. Registering or translating existing files without reading them is left to the table formats' own tooling.

UDC is primarily a personal project. Whether others need that combination has not been established, and the project does not wait for that answer. The comparison is in [PRD §2.5](docs/PRD.md#25-existing-tools-and-where-udc-fits), and the technical hypotheses that are tested are in [PRD §13.3](docs/PRD.md#133-value-hypotheses-and-evidence-gates).

## Architecture decisions

Architecture is recorded as ADRs in [docs/adr](docs/adr/). [ADR-0001](docs/adr/ADR-0001-initial-architecture.md) is the entry point: it maps every concern to the one ADR that owns it and defines the shared vocabulary.

| Status | ADRs |
|---|---|
| Accepted | [ADR-0001](docs/adr/ADR-0001-initial-architecture.md) architecture principles, [ADR-0002](docs/adr/ADR-0002-rust-implementation-language.md) Rust as the implementation language |
| Proposed | ADR-0003 to ADR-0017, and [ADR-0019](docs/adr/ADR-0019-packaging-and-distribution.md) packaging and distribution |
| Proposed and deferred | [ADR-0018](docs/adr/ADR-0018-distributed-job-state-store.md) distributed job state store |

Proposed decisions are not finalized. The per-ADR status table is in [PRD §17](docs/PRD.md#17-open-architecture-decisions).

## Proposed technology

Only Rust is decided. Everything else is a candidate that must be validated before it becomes a dependency.

- Rust (accepted, ADR-0002)
- Apache Arrow as the in-memory interchange representation
- Native Arrow pipeline (MVP reference path)
- Apache DataFusion / DuckDB (execution candidates under evaluation)
- Rust `object_store` ecosystem (storage candidate under evaluation)
- Tokio (async runtime candidate; bounded concurrency required)
- clap / Serde (CLI and configuration candidates)
- tracing / OpenTelemetry (observability candidates)
- thiserror / anyhow (typed and application error handling candidates)
- SQLite or an append-only journal (local job state store candidates)

## Installation

There is nothing to install yet. The planned distribution is prebuilt binaries plus crates.io packages, starting at the first MVP release; see [ADR-0019](docs/adr/ADR-0019-packaging-and-distribution.md).

The repository has been public since 2026-11-18, as public development: interfaces may change without notice, nothing is packaged, and there is no support commitment. To report a vulnerability, see [SECURITY.md](SECURITY.md).

The packages named `udc` on crates.io, PyPI, and npm are unrelated projects. UDC's CLI is proposed to be published as `udc-cli`.

## Future deployment direction

The MVP is a standalone CLI/library. Self-hosted service deployment (for example, running UDC within an organization's AWS, GCP, or Azure environment) is a potential future direction, not a current requirement or selected architecture. A single-node service may be evaluated before any distributed control-plane/worker deployment. See [Future Considerations in the PRD](docs/PRD.md#14-future-considerations-non-mvp).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

UDC is licensed under the [Apache License 2.0](LICENSE). Each dependency's license is reviewed before it is added ([ADR-0011](docs/adr/ADR-0011-dependency-and-feature-management.md)).
