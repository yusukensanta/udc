# UDC — Product Requirements Document

**Universal Data Converter**

| Attribute | Value |
|---|---|
| Project | UDC |
| Full Name | Universal Data Converter |
| Document | Product Requirements Document |
| Version | 0.1.0 |
| Status | Draft |
| License | Apache License 2.0 (proposed) |
| Development Model | OSS-first |
| Primary Language | Rust |
| Target Users | Data Engineers / Data Platform Engineers |

---

## 1. Executive Summary

UDC (Universal Data Converter) is an open-source, cloud-agnostic data format conversion and migration platform.

Its mission is to make data portable across file formats, table formats, storage systems, and execution engines.

UDC aims to provide a unified interface for:

- File format conversion.
- Table format interoperability and migration.
- Cross-cloud data migration.
- Schema mapping and compatibility management.
- Data integrity validation.
- Reliable and resumable conversion jobs.

Rather than reinventing existing execution engines, UDC will integrate established technologies such as Apache Arrow, Apache DataFusion, DuckDB, Apache Spark, and existing table format implementations.

UDC will prioritize interoperability, reliability, extensibility, and operational simplicity.

## 2. Problem Statement

Modern data platforms use multiple file formats, table formats, storage providers, and processing engines. This diversity creates operational complexity.

### 2.1 File Format Fragmentation

Organizations use different formats depending on their workloads and infrastructure:

- Parquet for analytical workloads.
- ORC for Hive-oriented environments.
- Avro for event streaming and schema evolution.
- CSV and JSON for interoperability.

Converting between formats often requires custom scripts, framework-specific configurations, or dedicated ETL pipelines.

### 2.2 Table Format Fragmentation

Modern lakehouse architectures use multiple table formats:

- Apache Iceberg
- Delta Lake
- Apache Hudi

Moving between these formats requires handling more than physical data files. Metadata, snapshots, delete semantics, partition specifications, and catalog state must be considered.

### 2.3 Cloud Fragmentation

Data is distributed across:

- Amazon S3
- Google Cloud Storage
- Azure Blob Storage

Cross-cloud migration introduces additional complexity:

- Authentication and authorization.
- Network transfer.
- Storage API differences.
- Retry and checkpoint management.
- Cost management.
- Data consistency validation.

### 2.4 Data Integrity

Successful execution does not necessarily mean successful migration.

Potential issues include:

- Schema incompatibility.
- Timestamp precision or timezone changes.
- Decimal precision loss.
- Nested type incompatibility.
- NULL and NaN semantic differences.
- Missing or duplicated records.

Existing conversion workflows often require separate validation implementations.

## 3. Product Vision

**One interface. Any format. Any cloud.**

UDC will provide a unified abstraction layer for data conversion and migration across heterogeneous data infrastructure.

The product will consist of four pillars:

1. Format Interoperability
2. Cloud Agnostic Storage Access
3. Reliable Migration Execution
4. Data Integrity Validation

## 4. Target Users

### Data Engineer

Needs to convert, migrate, and validate analytical datasets.

Typical use cases:
- Parquet to ORC conversion.
- Compression optimization.
- Partition restructuring.
- Cross-cloud migration.

### Data Platform Engineer

Needs to provide interoperable data infrastructure.

Typical use cases:
- Lakehouse migration.
- Table format interoperability.
- Catalog migration.
- Standardized data movement.

### Platform / Infrastructure Engineer

Needs reliable execution and operational visibility.

Typical use cases:
- Job orchestration.
- Retry and checkpoint management.
- Monitoring.
- Cloud credential management.

## 5. Product Scope

UDC will support two distinct categories of data representation.

### 5.1 File Formats

| Format | Read | Write | Priority |
|---|---|---|---|
| Apache Parquet | Yes | Yes | P0 |
| CSV | Yes | Yes | P0 |
| JSON | Yes | Yes | P0 |
| Apache ORC | Planned | Planned | P1 |
| Apache Avro | Planned | Planned | P1 |
| Apache Arrow IPC | Planned | Planned | P2 |

Actual support will be determined by implemented adapter capabilities.

### 5.2 Table Formats

| Format | Capability | Priority |
|---|---|---|
| Apache Iceberg | Inspection and metadata reading | P0 |
| Apache Iceberg | Data file rewrite | P1 |
| Delta Lake | Integration | P2 |
| Apache Hudi | Integration | P2 |

Table format migration must preserve logical table semantics.

UDC must explicitly identify unsupported features rather than silently ignoring them.

### 5.3 Cloud Storage

| Provider | Service | Priority |
|---|---|---|
| AWS | Amazon S3 | P0 |
| GCP | Google Cloud Storage | P0 |
| Azure | Azure Blob Storage | P0 |

Authentication must support native workload identity and default credential chains.

Long-lived credentials must not be required.

## 6. Functional Requirements

### FR-01: Source Inspection

UDC must inspect source datasets and retrieve:

- Detected format.
- Schema.
- Physical data types.
- Logical data types where available.
- File count.
- Total size.
- Partition information.
- Compression information.
- Table metadata where applicable.

### FR-02: File Format Conversion

UDC must convert supported source formats into supported destination formats.

Requirements:

- Streaming execution.
- Configurable compression.
- Schema mapping.
- Partition preservation.
- Projection support where available.
- Configurable output file size.
- Configurable writer options.

### FR-03: Cloud Storage Integration

UDC must support reading and writing across supported Cloud Storage providers.

Requirements:

- Native authentication.
- Range reads.
- Multipart or resumable uploads.
- Retry handling.
- Object listing.
- Metadata retrieval.
- Secure credential handling.

### FR-04: Schema Mapping

UDC must provide explicit schema compatibility handling.

Requirements:

- Logical type mapping.
- Physical type mapping.
- Nullability handling.
- Decimal precision and scale validation.
- Timestamp precision and timezone handling.
- Nested type conversion.
- Explicit lossy conversion policies.

### FR-05: Data Validation

UDC must validate conversion results.

| Level | Validation |
|---|---|
| L1 | Schema compatibility |
| L2 | Row count |
| L3 | Column statistics |
| L4 | Column-level hashing |
| L5 | Exact logical row comparison |

Validation policies must explicitly define normalization rules.

### FR-06: Job Management

Conversion must be represented as a job.

Requirements:

- Job configuration.
- Job state.
- Execution progress.
- Retry.
- Checkpoint.
- Cancellation.
- Failure reporting.
- Idempotent execution where supported.

### FR-07: Safe Output Publication

UDC must not expose incomplete output as successful output.

Requirements:

- Temporary output locations.
- Validation before publication.
- Explicit publication step.
- Cleanup of temporary artifacts.
- Protection against accidental source overwrite.

Publication semantics must account for differences between object stores and table format commit protocols.

### FR-08: CLI

UDC must provide a command-line interface.

Initial commands:

- `udc inspect`
- `udc convert`
- `udc validate`
- `udc job status`

### FR-09: Observability

UDC must provide:

- Structured logs.
- Execution metrics.
- Progress reporting.
- Error categorization.
- OpenTelemetry integration.

## 7. Non-Functional Requirements

### NFR-01: Performance

- Streaming processing must be supported.
- Memory consumption must be bounded by configurable execution limits.
- Backpressure must be supported.
- Parallel execution should be supported where appropriate.

### NFR-02: Reliability

- Failed jobs must provide actionable errors.
- Retry operations must avoid duplicate output where supported.
- Partial outputs must not be mistaken for completed datasets.
- Checkpoint state must be recoverable.

### NFR-03: Portability

- Core functionality must run locally.
- Cloud credentials must be provided through native authentication mechanisms.
- Core abstractions must not depend on a specific cloud provider.

### NFR-04: Security

- No credential leakage in logs.
- TLS for remote communication.
- Least-privilege access.
- Secret redaction.
- No mandatory external control plane.

### NFR-05: Extensibility

- Format adapters must be independently implementable.
- Storage providers must be pluggable.
- Execution engines must be replaceable.
- Table format integrations must remain separate from file format implementations.

## 8. MVP Definition

### MVP Goal

Deliver a functional cross-cloud file conversion and validation tool.

Initial demonstration: **Amazon S3 → Google Cloud Storage**

- Read partitioned Parquet data.
- Inspect source schema.
- Convert Parquet data.
- Apply configurable compression.
- Preserve partition structure.
- Validate schema and row counts.
- Publish validated output.

### MVP Feature Matrix

| Feature | MVP |
|---|---|
| Parquet Read / Write | Required |
| CSV Read / Write | Required |
| JSON Read / Write | Required |
| S3 | Required |
| GCS | Required |
| Azure Blob | Required |
| Schema Inspection | Required |
| Schema Mapping | Basic |
| Row Count Validation | Required |
| Schema Validation | Required |
| Checksum Validation | Basic |
| CLI | Required |
| Local Execution | Required |
| Streaming | Required |
| Checkpoint | Deferred |
| Spark Integration | Deferred |
| ORC | Deferred |
| Full Iceberg Migration | Deferred |

Azure support is a target capability, but its exact inclusion in the first release depends on integration test coverage.

### MVP Acceptance Criteria

1. Convert supported Parquet datasets without loading the entire dataset into memory.
2. Convert CSV and JSON datasets into Parquet.
3. Read and write using supported Cloud Storage providers.
4. Preserve supported partition structures.
5. Detect incompatible schema mappings before execution.
6. Validate schema and row counts.
7. Report actionable errors.
8. Avoid exposing incomplete output as successful.
9. Provide reproducible CLI examples.
10. Pass automated unit and integration tests.

## 9. Architecture Principles

### 9.1 Separation of Concerns

The architecture must separate:

- File Format
- Table Format
- Storage
- Catalog
- Execution Engine
- Validation
- Orchestration

### 9.2 Canonical Data Model

UDC will distinguish between:

- Logical schema representation.
- Physical schema representation.
- In-memory execution representation.

Apache Arrow will be the primary in-memory representation.

A separate canonical logical schema model will describe type semantics and conversion compatibility.

### 9.3 Execution Engine Abstraction

Initial engine:

- Apache DataFusion

Potential integrations:

- DuckDB
- Apache Spark

UDC must not require all execution engines to implement identical capabilities.

Capability discovery must determine which operations are supported by each engine.

### 9.4 Table Format Abstraction

Table format integrations must handle:

- Table metadata.
- Snapshots.
- Schema evolution.
- Partition specifications.
- Delete semantics.
- Commit operations.
- Catalog integration.

Existing implementations should be reused wherever practical.

## 10. Proposed Technology Stack

| Component | Technology |
|---|---|
| Core | Rust |
| In-memory Representation | Apache Arrow |
| Query / Execution | Apache DataFusion |
| Local Analytics Integration | DuckDB |
| Distributed Execution | Apache Spark |
| Cloud Storage | object_store ecosystem |
| Iceberg Integration | Apache Iceberg Rust |
| Delta Integration | Delta Kernel |
| Observability | OpenTelemetry |
| CLI | Rust CLI ecosystem |
| Configuration | YAML / JSON |
| Documentation | Markdown |

Technology choices remain subject to technical validation and Architecture Decision Records.

## 11. Repository Structure

```text
udc/
├── crates/
│   ├── udc-core/
│   ├── udc-engine/
│   ├── udc-cli/
│   ├── udc-sdk/
│   ├── udc-validation/
│   ├── udc-observability/
│   ├── udc-format-parquet/
│   ├── udc-format-csv/
│   ├── udc-format-json/
│   ├── udc-storage-s3/
│   ├── udc-storage-gcs/
│   ├── udc-storage-azure/
│   └── udc-table-iceberg/
│
├── integrations/
│   ├── spark/
│   ├── duckdb/
│   └── xtable/
│
├── examples/
├── tests/
│   ├── compatibility/
│   ├── integration/
│   └── benchmarks/
│
├── docs/
│   ├── architecture/
│   ├── specifications/
│   └── guides/
│
├── Cargo.toml
├── README.md
├── LICENSE
└── CONTRIBUTING.md
```

## 12. Roadmap

| Phase | Deliverable |
|---|---|
| P0 | Core abstractions and local Parquet conversion |
| P1 | CSV / JSON adapters |
| P2 | Schema mapping and validation |
| P3 | AWS / GCP / Azure storage integration |
| P4 | Reliable migration execution |
| P5 | Iceberg metadata inspection |
| P6 | ORC and distributed execution |
| P7 | SDK and external integrations |

The roadmap is capability-driven, not strictly time-driven.

## 13. Success Metrics

### Technical Metrics

- Supported format combinations.
- Supported Cloud Storage providers.
- Conversion throughput.
- Peak memory consumption.
- Validation accuracy.
- Successful job completion rate.
- Recovery success rate.

### OSS Adoption Metrics

- Active external contributors.
- External repository dependencies.
- Release downloads.
- CLI adoption.
- Community issue resolution.
- Integration projects.

GitHub Stars are supplementary indicators, not the primary success metric.

## 14. Out of Scope for MVP

- Managed SaaS offering.
- Multi-tenant control plane.
- Full ETL orchestration platform.
- General-purpose SQL transformation engine.
- Full Table Format migration across all formats.
- Continuous synchronization.
- Automatic cost optimization.
- Enterprise governance platform.

## 15. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Existing OSS overlap | Focus on unified migration and validation |
| Format semantic differences | Canonical schema and compatibility policies |
| Cloud API differences | Provider-specific adapters |
| Memory exhaustion | Streaming and backpressure |
| Partial migration failure | Staging and safe publication |
| Table format complexity | Reuse existing implementations |
| Maintenance burden | Capability-based support and modular dependencies |

## 16. Open Questions

The following decisions must be resolved through Architecture Decision Records:

1. Canonical logical type system design.
2. Arrow integration boundaries.
3. DataFusion integration strategy.
4. Storage abstraction and object_store limitations.
5. Cloud authentication abstraction.
6. Conversion job state management.
7. Checksum and logical equality semantics.
8. Table format integration boundaries.
9. Static versus dynamic plugin architecture.
10. License compatibility of external dependencies.

## 17. Product Definition of Done

A release is considered production-ready when:

- Supported capabilities are explicitly documented.
- Compatibility tests pass.
- Cloud integration tests pass.
- Failure scenarios are tested.
- Performance benchmarks are reproducible.
- Security review is completed.
- CLI documentation is available.
- Example workflows are executable.
- Breaking changes are documented.

---

**Product Statement**

UDC is not another file conversion utility.

It is an open-source interoperability platform designed to make data portable, verifiable, and reliable across modern data infrastructure.
