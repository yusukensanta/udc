# UDC — Universal Data Converter

**One interface. Any format. Any cloud.**

UDC is an OSS-first, cloud-agnostic data format conversion and migration platform.

Its goal is to make data portable, verifiable, and reliable across file formats, table formats, storage systems, and execution engines.

> **Status:** Concept / Early design. The repository does not yet contain a released implementation. Product requirements are documented in [docs/PRD.md](docs/PRD.md).

## Product pillars

- **Layered format support:** Distinguishes serialization formats, columnar file formats, interchange formats, table formats, and catalogs. Parquet, ORC, Avro, CSV, JSON, Arrow IPC / Feather, Lance, Vortex, Iceberg, Delta Lake, and Hudi.
- **Cloud-agnostic storage:** Amazon S3, Google Cloud Storage, and Azure Blob Storage.
- **Reliable migration:** staged output, retry, checkpointing, and safe publication.
- **Data integrity:** schema compatibility and logical data validation.

## MVP direction

The initial MVP focuses on local and cross-cloud file conversion using a streaming reader-to-writer pipeline with Apache Arrow as the in-memory interchange layer, plus schema and row-count validation. The execution backend remains under evaluation; see [ADR-0004](docs/adr/ADR-0004-execution-engine-selection.md).

See the [PRD](docs/PRD.md) for scope, requirements, acceptance criteria, proposed architecture, and roadmap.

## Proposed technology

- Rust
- Apache Arrow
- Native Arrow pipeline (MVP reference path)
- Apache DataFusion / DuckDB (execution candidates under evaluation)
- Rust object_store ecosystem (storage candidate under evaluation)
- Tokio (async runtime candidate; bounded concurrency required)
- clap / Serde (CLI and configuration candidates)
- tracing / OpenTelemetry (observability candidates)
- thiserror / anyhow (typed and application error handling candidates)

UDC is designed for datasets larger than process memory: bounded streaming, byte-aware backpressure, partitionable work units, independent I/O and CPU limits, and recoverable staging are architectural requirements. The MVP remains single-node; the work plan is designed to preserve a future scale-out path.

See [docs/adr](docs/adr/) for decision rationale, alternatives, trade-offs, and validation plans. Proposed decisions are not finalized.

## Repository layout

```text
crates/          Core, adapters, CLI, SDK, validation
integrations/    External engine and interoperability integrations
docs/            Product, architecture, and format specifications
examples/        Reproducible usage examples
tests/           Compatibility, integration, and benchmark tests
```

## Project status

UDC is in the product-definition and architecture stage. No format or cloud integration should be considered supported until implemented and covered by tests.

## License

The project intends to use Apache License 2.0. The license file will be added after dependency and licensing review.
