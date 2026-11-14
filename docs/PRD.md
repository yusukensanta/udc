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
- Lance Table Format

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

### 5.1 File and Columnar Formats

UDC's scope includes general-purpose row/columnar serialization formats, Arrow-based interchange formats, and newer analytical/ML-oriented columnar formats.

| Format | Read | Write | Priority | Notes |
|---|---|---|---|---|
| Apache Parquet | Yes | Yes | P0 | Primary analytical columnar format |
| CSV | Yes | Yes | P0 | Interchange format |
| JSON / JSONL | Yes | Yes | P0 | Interchange and semi-structured data |
| Apache Avro | Planned | Planned | P1 | Row-oriented serialization with schema evolution |
| Apache ORC | Planned | Planned | P1 | Columnar analytical format |
| Apache Arrow IPC / Feather | Planned | Planned | P1 | Arrow-native interchange and file representation |
| Lance File Format | Planned | Planned | P2 | Cloud-object-store-oriented, random-access columnar container |
| Vortex | Planned | Planned | P2 | Modern columnar format with modular encoding and execution-oriented design |

**Important distinction:** Lance is not only a file format. The broader Lance specification also defines table, index, catalog, and namespace layers. UDC must model Lance File Format and Lance Table Format as separate capabilities. Vortex is included as a columnar data format; its evolving reader/writer and ecosystem support must be validated independently.

Actual support is determined by implemented adapter capabilities, not by inclusion in this roadmap.

### 5.2 Table Formats

| Format | Capability | Priority | Notes |
|---|---|---|---|
| Apache Iceberg | Inspection and metadata reading | P0 | Initial table-format integration |
| Apache Iceberg | Data file rewrite | P1 | Preserve table semantics and commit safely |
| Delta Lake | Integration | P2 | Includes protocol feature compatibility |
| Apache Hudi | Integration | P2 | Includes timeline and table-type semantics |
| Lance Table Format | Inspection and metadata reading | P2 | Separate from Lance file reader/writer |
| Lance Table Format | Migration / rewrite | P3 | Must account for fragments, deletions, indices, manifests, and commits |

Table format migration must preserve logical table semantics.

UDC must explicitly identify unsupported features rather than silently ignoring them. File-format conversion must not be represented as table-format migration when snapshots, deletes, indexes, manifests, or transaction semantics are involved.



### 5.4 Format Taxonomy and Semantic Boundaries

UDC must not treat every supported item as the same kind of format.

| Category | Examples | UDC responsibility |
|---|---|---|
| Row-oriented serialization | Avro, CSV, JSON | Record decoding/encoding and schema mapping |
| Columnar file format | Parquet, ORC, Lance File, Vortex | Column/page decoding, encoding, projection, writing |
| In-memory / interchange | Arrow IPC / Feather | Arrow-compatible batch interchange |
| Table format | Iceberg, Delta, Hudi, Lance Table | Snapshot, manifest, fragment, delete, index, and commit semantics |
| Catalog / namespace | Glue, REST Catalog, Lance Namespace | Discovery, registration, and coordination |

Lance requires special treatment: the Lance ecosystem specifies file, table, index, catalog, and namespace layers independently. A Lance file adapter alone does not imply Lance table interoperability. Vortex is included as a columnar format target, but the project must verify the maturity and feature coverage of the selected Rust libraries before committing to read/write guarantees.

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

### NFR-06: Scalability and Resource Isolation

UDC must scale across dataset size, object count, data skew, and available compute/network resources.

- Dataset size must not determine peak process memory. The default execution path must be streaming and bounded.
- Every producer-consumer queue must have a configured finite capacity.
- Memory admission control must account for bytes, not only batch or task counts.
- Concurrency limits must be independently configurable for source reads, CPU decode/encode, destination writes, multipart parts, and per-provider requests.
- CPU-heavy or blocking operations must not starve async I/O workers.
- Large files and many-small-file workloads must have separately benchmarked execution strategies.
- Work-unit scheduling must support independent progress, failure isolation, and retry.
- The design must preserve a path to multi-process or multi-node execution without requiring it in the MVP.
- Resource limits, queue pressure, active work units, in-flight bytes, and provider throttling must be observable.

### NFR-07: Recovery and Idempotency

- Work units must have stable identities within a job plan.
- Acknowledgement must occur only after the output is durably written and required validation succeeds.
- Retries must use deterministic or attempt-specific staging outputs.
- A failed or abandoned attempt must not be published as complete.
- Recovery must reconcile incomplete multipart uploads and staging artifacts.
- Exactly-once execution is not assumed; safe effects must be achieved through idempotency, staging, validation, and publication boundaries.

### NFR-08: Operational Efficiency

- Effective job settings and resource budgets must be inspectable before execution.
- Jobs must expose progress by work units and bytes, with unknown totals represented honestly.
- Telemetry must work locally without a mandatory collector or hosted control plane.
- High-cardinality values such as object paths must not become metric labels.


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
| Durable local Job Manifest / State Store | Required |
| Durable Work Unit state and restart resume | Required |
| Spark Integration | Deferred |
| ORC / Avro / Arrow IPC | Deferred |
| Full Iceberg / Delta / Hudi / Lance Table Migration | Deferred |

Azure support is a target capability, but its exact inclusion in the first release depends on integration test coverage.

Partial progress inside a Work Unit, distributed leases, shared multi-writer state, remote Workers, and a built-in distributed Coordinator are deferred. The MVP must durably record completed Work Units and safely resume remaining work after process restart. See [ADR-0013](adr/ADR-0013-job-manifest-and-state-management.md).

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
11. Demonstrate bounded memory on an input dataset substantially larger than the configured memory budget.
12. Demonstrate bounded concurrency and backpressure when the destination is slower than the source.
13. Demonstrate isolated retry of a failed work unit without republishing completed outputs.

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

UDC Core must not require a query engine for a pure streaming conversion path.

Reference path for conversion-only workloads:

- Format Reader → Arrow RecordBatch Stream → Format Writer

Execution engine candidates:

- Native Arrow / format reader-writer pipeline (baseline).
- Apache DataFusion.
- DuckDB.
- Apache Spark (later distributed-execution integration candidate).

The MVP must compare Native Arrow, DataFusion, and DuckDB before selecting an engine dependency. See [ADR-0004: Execution Engine Selection](adr/ADR-0004-execution-engine-selection.md).

UDC must not require all execution backends to implement identical capabilities. Capability discovery must determine which operations are supported by each backend.

### 9.4 Table Format Abstraction

Table format integrations must handle:

- Table metadata and snapshots.
- Schema evolution and partition specifications.
- Delete semantics and transactional commits.
- Catalog integration.
- Table-specific structures such as Lance fragments, indices, manifests, and deletion files.
- Explicit capability negotiation for features not shared by all table formats.

Existing implementations should be reused wherever practical.

## 10. Proposed Technology Stack

| Component | Technology |
|---|---|
| Component | Candidate / Direction |
|---|---|
| Core language | Rust (ADR-0002) |
| In-memory interchange | Apache Arrow |
| Execution | Native Arrow baseline; DataFusion and DuckDB under evaluation (ADR-0004) |
| Distributed execution | Apache Spark, deferred integration candidate |
| Cloud storage | Rust object_store ecosystem under evaluation (ADR-0005) |
| Canonical schema | UDC-owned logical model proposed; Arrow for execution representation (ADR-0003) |
| Iceberg integration | Apache Iceberg Rust, subject to capability review |
| Delta integration | Delta Kernel, subject to language/API integration review |
| Observability | OpenTelemetry candidate |
| CLI | Rust CLI ecosystem |
| Configuration | YAML / JSON (to be specified) |
| Documentation | Markdown |

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

Scalability is a cross-cutting acceptance requirement, not a late roadmap phase. The MVP remains single-node, but planning and work-unit boundaries should permit future remote execution. See [ADR-0012: Scalable Data Processing Architecture](adr/ADR-0012-scalable-data-processing.md).

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

The following decisions are tracked in Architecture Decision Records. Items marked Proposed or Under Evaluation are not finalized:

1. Rust implementation language — ADR-0002 (Accepted).
2. Canonical logical schema and Arrow execution boundary — ADR-0003 (Proposed).
3. Execution backend selection — ADR-0004 (Proposed; PoC required).
4. Storage abstraction and provider capabilities — ADR-0005 (Proposed).
5. Validation and logical equality semantics — ADR-0006 (Proposed).
6. Async runtime and concurrency control — ADR-0007 (Proposed).
7. Error taxonomy, retry classification, and failure boundaries — ADR-0008 (Proposed).
8. CLI and job configuration format — ADR-0009 (Proposed).
9. Tracing, metrics, and OpenTelemetry integration — ADR-0010 (Proposed).
10. Workspace, dependency, and Cargo feature strategy — ADR-0011 (Proposed).
11. Scalable processing model and future scale-out boundary — ADR-0012 (Proposed).
12. Cloud authentication abstraction.
13. Local JobStateStore backend selection (SQLite vs append-only journal) and manifest implementation details — ADR-0013.
14. Table format integration boundaries.
15. License compatibility of external dependencies.

## 17. Product Definition of Done

A release is considered production-ready when:

- Supported capabilities are explicitly documented.
- Compatibility tests pass.
- Cloud integration tests pass.
- Failure scenarios are tested.
- Work Unit completion is durably recorded and process restart recovery is tested.
- Performance benchmarks are reproducible.
- Security review is completed.
- CLI documentation is available.
- Example workflows are executable.
- Breaking changes are documented.

---

**Product Statement**

UDC is not another file conversion utility.

It is an open-source interoperability platform designed to make data portable, verifiable, and reliable across modern data infrastructure.
