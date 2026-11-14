# UDC — Universal Data Converter

**One interface. Any format. Any cloud.**

UDC is an OSS-first, cloud-agnostic data format conversion and migration platform.

Its goal is to make data portable, verifiable, and reliable across file formats, table formats, storage systems, and execution engines.

> **Status:** Product definition and architecture design. This repository currently contains documentation only. There is no source code, build configuration, or released implementation yet, and no format or cloud integration should be considered supported until it is implemented here and covered by tests.

## What is in this repository

```text
README.md          Project overview (this file)
CONTRIBUTING.md    Contribution guidelines, ADR conventions, and AI-assistance policy
docs/
  PRD.md           Product Requirements Document (draft)
  adr/             Architecture Decision Records, ADR-0001 to ADR-0019
```

The planned crate and directory organization is illustrated in [PRD §11.2](docs/PRD.md#112-illustrative-repository-organization). Those directories do not exist yet; each will be added when the functionality it holds is implemented.

## Product pillars

These describe the intended product, not current capabilities.

- **Layered format support:** distinguishes serialization formats, columnar file formats, interchange formats, table formats, and catalogs. Targets on the roadmap include Parquet, CSV, JSON, Avro, ORC, Arrow IPC / Feather, Lance, Vortex, Iceberg, Delta Lake, and Hudi.
- **Cloud-agnostic storage:** local filesystem, Amazon S3, Google Cloud Storage, and Azure Blob Storage.
- **Reliable migration:** staged output, retry, durable work-unit completion, resume, and safe publication.
- **Data integrity:** schema compatibility and logical data validation with clearly stated guarantees.

## MVP direction

The initial MVP is a single-node CLI and library for local and cross-cloud file conversion of Parquet, CSV, and JSON. It uses a streaming reader-to-writer pipeline with Apache Arrow as the in-memory interchange layer, plus schema and row-count validation, restart recovery, and safe publication of validated output. The execution backend remains under evaluation; see [ADR-0004](docs/adr/ADR-0004-execution-engine-selection.md).

UDC is designed for datasets larger than process memory: bounded streaming, byte-aware backpressure, partitionable work units, independent I/O and CPU limits, and recoverable staging are architectural requirements. The work plan is designed to preserve a future scale-out path.

See the [PRD](docs/PRD.md) for scope, requirements, acceptance criteria, proposed architecture, and roadmap.

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

The packages named `udc` on crates.io, PyPI, and npm are unrelated projects. UDC's CLI is proposed to be published as `udc-cli`.

## Future deployment direction

The MVP is a standalone CLI/library. Self-hosted service deployment (for example, running UDC within an organization's AWS, GCP, or Azure environment) is a potential future direction, not a current requirement or selected architecture. A single-node service may be evaluated before any distributed control-plane/worker deployment. See [Future Considerations in the PRD](docs/PRD.md#14-future-considerations-non-mvp).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

The project intends to use Apache License 2.0. The license file will be added after dependency and licensing review.
