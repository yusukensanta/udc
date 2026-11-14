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

The initial MVP focuses on local and cross-cloud file conversion using Apache Arrow and Apache DataFusion, with schema and row-count validation.

See the [PRD](docs/PRD.md) for scope, requirements, acceptance criteria, proposed architecture, and roadmap.

## Proposed technology

- Rust
- Apache Arrow
- Apache DataFusion
- object_store ecosystem
- OpenTelemetry

All technology choices remain subject to Architecture Decision Records and implementation feasibility.

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
