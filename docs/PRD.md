# UDC — Product Requirements Document

**Universal Data Converter**

| Attribute | Value |
|---|---|
| Project | UDC |
| Full Name | Universal Data Converter |
| Document | Product Requirements Document |
| Version | 0.2.0 |
| Status | Draft |
| License | Apache License 2.0 (proposed; subject to dependency/license review) |
| Development Model | OSS-first |
| Primary Language | Rust |
| Target Users | Data Engineers / Data Platform Engineers |

---

## 1. Executive Summary

UDC (Universal Data Converter) is an open-source, cloud-agnostic platform for data-format conversion, dataset migration, and integrity validation.

Its mission is to make data portable, verifiable, and reliable across file formats, table formats, storage systems, and execution environments.

UDC aims to provide a unified product experience for:

- Inspecting source datasets and their schemas.
- Converting between supported file formats.
- Moving data across supported object-storage providers.
- Evaluating and applying explicit schema mappings.
- Validating conversion results with clearly stated guarantees.
- Running recoverable jobs with bounded resource consumption and controlled output publication.
- Integrating with table formats through their native metadata and transaction protocols.

UDC will reuse mature format, storage, table-protocol, and execution libraries where practical. It will not reimplement an entire query engine or table-format protocol merely to provide a common user experience.

**Product principle:** UDC owns interoperability policy, job orchestration, validation policy, and user-facing capability reporting. Specialized libraries remain authoritative for the low-level format, storage, and table-protocol behavior they implement.

The initial product is a local CLI and library backed by a modular Rust codebase. The MVP is single-node. Self-hosted service deployment and distributed workers are possible future directions, not MVP commitments.

## 2. Problem Statement

Modern data platforms combine multiple serialization formats, table formats, object stores, catalogs, and execution engines. Moving data between them is not simply a matter of copying bytes or rewriting files.

### 2.1 File-format fragmentation

Organizations use different formats for different workloads:

- Parquet and ORC for analytical columnar storage.
- Avro for schema-aware record serialization and event data.
- CSV and JSON for interchange.
- Arrow IPC and other formats for in-memory or analytical interoperability.

Conversion often requires custom scripts or framework-specific pipelines. Those pipelines may duplicate schema mapping, storage access, retry, and validation logic.

### 2.2 Table-format fragmentation

Iceberg, Delta Lake, Hudi, and Lance Table provide semantics above the underlying data files. Their metadata, snapshots or timelines, delete representations, partition evolution, indexes, catalogs, and commit protocols affect the logical table.

Rewriting Parquet files alone does not constitute a correct table migration. A tool must understand the table's consistency boundary and use its native commit protocol when publishing table changes.

### 2.3 Storage and cloud fragmentation

Data is distributed across Amazon S3, Google Cloud Storage, Azure Blob Storage, and local filesystems. Moving data between these systems involves provider-specific behavior such as:

- Identity resolution, authorization, and token refresh.
- Range reads, multipart or resumable uploads, and request limits.
- Conditional operations and provider-specific consistency guarantees.
- Transient failures, throttling, retry budgets, and cleanup.
- Network transfer time and cost.

A common interface must not hide meaningful differences between providers or claim guarantees that a provider cannot supply.

### 2.4 Data correctness and integrity

A successful process exit does not prove that a migration preserved the source data's meaning. Common failure modes include:

- Incompatible logical or physical types.
- Decimal precision/scale changes and numeric overflow.
- Timestamp precision, timezone, and interpretation changes.
- Nullability and nested-type incompatibilities.
- NaN, infinity, and signed-zero differences.
- Missing, duplicated, or altered records.
- Partial output becoming visible after a failed job.

UDC must make conversion policy explicit and report what each validation level proves—and what it does not prove.

## 3. Product Vision

**One interface. Any format. Any cloud.**

UDC will provide a common interface over heterogeneous data infrastructure without pretending that all formats, stores, engines, or table protocols have identical capabilities.

The product is organized around four pillars:

1. **Format interoperability:** inspect and convert supported physical representations while preserving or explicitly mapping logical meaning.
2. **Cloud-agnostic data access:** access local and cloud object storage through capability-aware adapters.
3. **Reliable migration execution:** plan work, bound resource use, isolate failures, recover completed work, and publish outputs safely.
4. **Data integrity:** define schema compatibility and validation evidence explicitly.

## 4. Target Users and Primary Use Cases

### 4.1 Data Engineer

Needs to convert, move, and validate datasets without building a bespoke pipeline for each format and storage pair.

Typical use cases:
- Parquet to CSV, JSON, or another supported columnar format.
- Compression or physical-layout changes.
- Partition-preserving dataset conversion.
- Cross-cloud object-storage migration.
- Schema compatibility checks before a large transfer.

### 4.2 Data Platform Engineer

Needs reliable interoperability across lakehouse and storage technologies.

Typical use cases:
- Inspecting table metadata and supported table features.
- Planning a table-format migration.
- Rewriting table data while preserving snapshot and delete semantics.
- Standardizing data movement and validation across platforms.

Table-format migration is a higher-complexity capability and is not implied by file-format conversion support.

### 4.3 Platform / Infrastructure Engineer

Needs operationally predictable execution and enough visibility to support long-running jobs.

Typical use cases:
- Inspecting job progress, resource consumption, and failures.
- Configuring bounded concurrency and memory limits.
- Recovering jobs after process interruption.
- Managing cloud identity and least-privilege access.
- Operating UDC in local or, potentially in the future, self-hosted environments.

## 5. Product Scope and Capability Taxonomy

UDC distinguishes the following layers. Support at one layer does not imply support at another.

| Layer | Examples | UDC responsibility |
|---|---|---|
| Serialization / file format | Parquet, ORC, Avro, CSV, JSON, Arrow IPC, Lance File, Vortex | Physical inspection, decoding, encoding, and format-specific capabilities |
| In-memory interchange | Apache Arrow arrays and RecordBatches | Efficient interchange for compatible readers, writers, and execution backends |
| Table format | Iceberg, Delta Lake, Hudi, Lance Table | Snapshot/timeline, manifests/fragments, deletes, indexes, and native commit semantics |
| Catalog / namespace | Glue, REST Catalog, Lance Namespace | Table discovery, registration, and catalog-specific coordination |
| Storage | Local filesystem, S3, GCS, Azure Blob | Object/byte operations and provider capabilities |
| Execution | Native streaming pipeline, DataFusion, DuckDB, Spark | Batch processing and optional transformations |
| Orchestration | Planner, Scheduler, Worker, Publisher | Job planning, work-unit lifecycle, retries, resource budgets, and publication workflow |

### 5.1 File and columnar formats

The format list below is a capability roadmap, not a claim that these formats are currently implemented or production-ready.

| Format | Intended read/write scope | Priority | Notes |
|---|---|---|---|
| Apache Parquet | Read and write | P0 | Primary analytical columnar format |
| CSV | Read and write | P0 | Interchange format; parsing and type inference policies must be explicit |
| JSON / JSONL | Read and write | P0 | Semi-structured interchange; schema inference and heterogeneous records require explicit policy |
| Apache Avro | Read and write | P1 | Row-oriented serialization and schema evolution |
| Apache ORC | Read and write | P1 | Columnar analytical format |
| Apache Arrow IPC / Feather | Read and write | P1 | Arrow-native interchange and file representation |
| Lance File | Evaluate read/write | P2 | Distinct from Lance Table; library and feature coverage must be verified |
| Vortex | Evaluate read/write | P2 | Evolving columnar ecosystem; maturity and feature coverage require validation |

UDC support is defined by the capabilities implemented and tested in its adapter—not by the format's inclusion in this table. Each adapter must report its actual inspection, split, read, write, and option capabilities. See [ADR-0014: File Format Adapter Contract](adr/ADR-0014-file-format-adapter-contract.md).

**Lance distinction:** Lance File and Lance Table are separate integration targets. A file adapter does not imply table, index, catalog, namespace, or transaction support.

### 5.2 Table formats

| Format | Intended capability | Priority | Boundary |
|---|---|---|---|
| Apache Iceberg | Metadata and snapshot inspection | P0 | Initial table-format integration target; read-only inspection does not imply rewrite |
| Apache Iceberg | Data-file rewrite / migration | P1 | Requires snapshot pinning, delete handling, conflict detection, and native commit |
| Delta Lake | Integration evaluation | P2 | Protocol feature compatibility and available Rust/JVM integration must be assessed |
| Apache Hudi | Integration evaluation | P2 | Timeline and table-type semantics must be assessed |
| Lance Table | Metadata inspection | P2 | Separate from Lance File |
| Lance Table | Migration / rewrite | P3 | Must account for fragments, deletions, indices, manifests, and native commit behavior |

A table-format feature is supported only when its adapter can preserve the relevant table semantics. Unsupported protocol features must be surfaced explicitly; they must not be silently ignored. The authoritative integration boundary and snapshot/commit responsibilities are specified in [ADR-0015](adr/ADR-0015-table-format-integration-boundary.md).

### 5.3 Storage providers

| Provider | Service | Intended priority |
|---|---|---|
| Local | Local filesystem | P0 for development and local execution |
| AWS | Amazon S3 | P0 |
| GCP | Google Cloud Storage | P0 |
| Azure | Azure Blob Storage | P0 target; release inclusion depends on tested capability coverage |

Storage adapters expose object operations and provider-specific capabilities. They must not assume filesystem rename semantics or universal atomic directory publication. The storage abstraction is described in [ADR-0005](adr/ADR-0005-storage-abstraction.md).

Authentication is a separate concern. UDC should prefer native credential chains, short-lived credentials, and workload identity. Credential references—not resolved secrets—may be persisted in job metadata. The proposed identity and refresh boundary is described in [ADR-0016](adr/ADR-0016-cloud-authentication.md).

### 5.4 Catalogs and namespaces

Catalog integration is distinct from storage and table-format integration. A catalog adapter is responsible for discovery, registration, and catalog-specific operations; it does not own job lifecycle or file conversion.

Glue, REST Catalog, and Lance Namespace are examples of ecosystems to evaluate. No catalog implementation or complete catalog-migration capability is committed by this PRD version.

## 6. Functional Requirements

### FR-01: Source and target inspection

UDC must inspect supported inputs and report, where available:

- Detected representation and adapter capability/version.
- Physical schema and logical schema interpretation.
- Format-specific metadata and provenance.
- File/object count and total size, distinguishing exact values, estimates, and unknown values.
- Partition and compression information.
- Table metadata and the consistency point used for table reads, when applicable.

Inspection should use metadata such as file footers where possible and must not imply that every property was discovered through a full data scan.

### FR-02: File-format conversion

UDC must convert between supported source and destination file formats.

Requirements:
- Streaming read-to-write execution; loading the entire dataset into memory must not be required.
- Configurable writer options and compression.
- Explicit schema mapping and coercion policy.
- Partition preservation or an explicit partition transformation policy.
- Projection and split parallelism only where the relevant adapter can guarantee their semantics.
- Configurable output-file sizing where supported.
- Explicit reporting of unsupported source/target capability combinations.

### FR-03: Storage integration

UDC must read and write through supported local and cloud storage adapters.

Requirements:
- Provider-native authentication and refresh behavior.
- Sequential and range reads where supported.
- Multipart or resumable uploads where supported.
- Listing and metadata operations where supported.
- Conditional operations and provider capabilities surfaced explicitly.
- Bounded retries and actionable errors for transient and permanent failures.
- No assumption that object-store rename is atomic.

### FR-04: Schema compatibility and mapping

UDC must evaluate schema compatibility before expensive data movement.

The canonical logical schema is distinct from both source/target physical schemas and the in-memory execution representation. Schema mapping must produce a deterministic, versioned plan describing field identity, coercions, policy decisions, and warnings.

Compatibility outcomes include:
- Exact.
- Safe widening.
- Lossy or narrowing.
- Unsupported.
- Policy-dependent.
- Unknown.

Requirements:
- Explicit field identity and rename policy; positional mapping is not the default.
- Numeric range, signedness, decimal precision, and scale checks.
- Timestamp precision and timezone semantics.
- Nullability and nested struct/list/map compatibility.
- Explicit policies for rounding, truncation, overflow, and other lossy behavior.
- Preservation or explicit treatment of format-specific metadata and provenance.

The canonical model and compatibility decision rules are defined in [ADR-0003](adr/ADR-0003-canonical-data-model.md).

### FR-05: Data validation

UDC must distinguish structural validation, transfer integrity, and logical data equivalence. Each result must state its scope and guarantee.

Candidate validation levels:

| Level | Validation | What it can establish |
|---|---|---|
| L1 | Schema / structural compatibility | Declared schema and structural properties satisfy the selected policy |
| L2 | Row or record count | Counts agree; does not prove values agree |
| L3 | Column statistics | Selected aggregates/statistics agree under defined normalization |
| L4 | Checksums / hashes | Byte-level or normalized-value fingerprints agree according to the selected algorithm |
| L5 | Exact logical comparison | Logical records agree under an explicitly defined equality and normalization policy |

The exact algorithms, normalization rules, and guarantee names are governed by [ADR-0006: Validation Semantics](adr/ADR-0006-validation-semantics.md). A physical file checksum must not be presented as proof of logical equivalence.

### FR-06: Job lifecycle and recovery

Conversion and migration operations must be represented as jobs.

Requirements:
- Versioned job configuration and effective configuration inspection.
- Durable job, plan, work-unit, attempt, and publication state.
- Progress reporting with unknown totals represented honestly.
- Cancellation and graceful process shutdown.
- Classified retry with bounded attempts, backoff, and retry budgets.
- Durable completion acknowledgement for a work unit only after its required output and validation conditions are met.
- Recovery after process restart from durably completed work units.
- No exactly-once execution claim; safe effects are achieved through attempt isolation, acceptance, validation, and publication.

The MVP requires a durable local Job State Store and restart recovery. The persisted state model, legal transitions, and recovery contract are defined in [ADR-0013](adr/ADR-0013-job-manifest-and-state-management.md). Planning, scheduling, worker contracts, and resource budgets are defined in [ADR-0012](adr/ADR-0012-scalable-data-processing.md).

### FR-07: Safe output publication

UDC must not present incomplete or unvalidated output as a successfully published dataset.

For generic file/dataset output, the proposed protocol uses attempt-isolated staging, an immutable output manifest, validation, and a destination-specific publication reference. The publication mechanism must be selected from capabilities actually verified for the destination.

Requirements:
- Stage outputs separately from the published dataset.
- Bind publication to the exact accepted output set.
- Validate before making the output visible through the supported publication reference.
- Use conditional writes, version preconditions, or another verified destination-specific mechanism where available.
- Reconcile ambiguous publication outcomes after process failure.
- Detect conflicting writes to the same logical destination.
- Clean up only unreferenced staging artifacts.
- Document weaker guarantees or reject a safe-publication claim where the destination cannot provide the required primitive.

There is no universal atomic directory rename guarantee across object stores. Generic file/dataset publication is specified in [ADR-0017](adr/ADR-0017-output-publication-protocol.md). Table-format writes must use their native commit protocol as specified in ADR-0015.

### FR-08: CLI

UDC must provide a CLI for local inspection, conversion, validation, and job operations.

Initial command concepts:
- `udc inspect`
- `udc convert`
- `udc validate`
- `udc job status`

Exact flags, configuration precedence, file format, and compatibility policy remain subject to [ADR-0009](adr/ADR-0009-cli-and-configuration.md).

### FR-09: Observability

UDC must provide:
- Structured, contextual logs.
- Job and work-unit progress.
- Execution and resource metrics.
- Error classification and actionable diagnostics.
- Correlation across jobs, work units, attempts, and storage requests.
- Optional telemetry export without requiring a hosted collector or control plane.

Telemetry must not leak credentials or sensitive data. High-cardinality values such as full object paths must not be metric labels. Instrumentation and export are specified in [ADR-0010](adr/ADR-0010-observability.md).

## 7. Non-Functional Requirements

### NFR-01: Performance and bounded execution

- The default conversion path must stream data and bound memory independently of total dataset size.
- Producer/consumer queues must have finite capacity.
- Memory admission must account for bytes, not only batch or task counts.
- I/O and CPU-heavy work must have independently configurable concurrency limits.
- CPU-heavy or blocking work must not starve asynchronous I/O workers.
- Large-file and many-small-file workloads must be benchmarked separately.
- Throughput claims must include workload, hardware, storage, concurrency, and validation configuration.

### NFR-02: Reliability and failure isolation

- Errors must be classified as transient, permanent, configuration, compatibility, resource, or other actionable categories.
- Only eligible transient failures should be retried automatically.
- Retries must be bounded by attempt and time budgets and use backoff with jitter where appropriate.
- A failed attempt must not overwrite or be mistaken for an accepted attempt.
- Partial output must not be considered published.
- Process interruption must not lose acknowledged work-unit completion.
- Exactly-once task execution is not promised.

Retry classification and error semantics are specified in [ADR-0008](adr/ADR-0008-error-handling-and-retry.md).

### NFR-03: Portability

- Core conversion functionality must run locally without a mandatory cloud service or external control plane.
- Core domain contracts must not depend on a specific cloud provider.
- Cloud integration must use provider-native identity where available.
- Provider-specific capabilities and limitations must remain visible to callers.

### NFR-04: Security

- Credentials and tokens must never be persisted in job manifests or emitted in logs, traces, or diagnostics.
- Production usage should prefer short-lived credentials and workload identity over long-lived static keys.
- Access should follow least privilege.
- Static credentials, if supported, must be explicit and opt-in rather than the recommended production path.
- Any future remote API must use authenticated and encrypted communication and define its trust boundary.
- Local execution must not require an external control plane.

### NFR-05: Extensibility and dependency discipline

- Format, table, storage, catalog, and execution integrations must have distinct responsibilities.
- Adapter capabilities must be explicit and versioned where they affect persisted plans.
- Core must not depend on concrete cloud SDKs or optional query engines.
- Optional integrations should not make unrelated formats unusable.
- Mature libraries should be reused where their semantics, feature coverage, and licensing are acceptable.
- Dependency and Cargo feature decisions must be validated against build size, compatibility, and maintenance cost.

Workspace and dependency policy are specified in [ADR-0011](adr/ADR-0011-dependency-and-feature-management.md).

### NFR-06: Scalability and resource isolation

UDC must handle variation in dataset size, object count, skew, and available resources without requiring distributed execution in the MVP.

- Work units must have stable identities within an immutable plan generation.
- Scheduling must support independent progress, failure isolation, and retry.
- Resource budgets must bound in-flight bytes, queues, and per-provider concurrency.
- Jobs must expose resource pressure, active work units, in-flight bytes, and provider throttling.
- Planning and work-unit descriptors should be serializable so that remote execution remains possible as a future extension.
- The MVP remains a single-process, single-node deployment.

The processing architecture and resource-budget ownership are specified in ADR-0012. Distributed coordination and a multi-worker state backend are deferred and separately scoped by ADR-0018.

### NFR-07: Durable state and recovery

- Job, plan, work-unit, attempt, and publication transitions must be durable and validated against legal state transitions.
- The MVP must recover after process restart from completed work units.
- A work unit is acknowledged only after its required output is durable and acceptance conditions are satisfied.
- Mid-work-unit checkpointing is not required for the MVP.
- State-store implementation details must not be confused with bulk dataset storage or artifact storage.

The local durability contract belongs to ADR-0013. A distributed backend must implement the same logical state contract and is deferred to ADR-0018.

### NFR-08: Operational efficiency

- Effective job settings and resource budgets must be inspectable before execution.
- Progress must distinguish completed, running, pending, retrying, and unknown work.
- Local telemetry must function without a mandatory collector.
- Cleanup and recovery operations must be observable and safe to repeat.
- Performance and recovery tests must be reproducible.

## 8. MVP Definition

### 8.1 MVP goal

Deliver a dependable single-node tool for local and cross-cloud **file-format conversion and validation**.

Reference demonstration: **Amazon S3 → Google Cloud Storage**, subject to tested adapter capabilities.

The MVP should demonstrate:
- Reading a partitioned Parquet dataset.
- Inspecting source schema and metadata.
- Converting Parquet to Parquet and supported interchange targets.
- Applying configurable compression and writer options.
- Preserving supported partition structure.
- Applying basic, explicit schema mapping.
- Validating schema and row counts.
- Staging and publishing validated output through a supported destination publication mode.
- Recovering completed work units after process restart.

### 8.2 MVP capability matrix

| Capability | MVP commitment |
|---|---|
| Parquet read/write | Required |
| CSV read/write | Required |
| JSON / JSONL read/write | Required |
| Local filesystem | Required for development and local execution |
| Amazon S3 | Required, subject to integration tests |
| Google Cloud Storage | Required, subject to integration tests |
| Azure Blob Storage | Target capability; release gate depends on tested support |
| Source inspection | Required for supported formats |
| Basic schema compatibility and mapping | Required |
| Schema validation | Required |
| Row-count validation | Required |
| Checksum / transfer-integrity validation | Basic, with guarantee clearly labeled |
| Streaming and bounded memory | Required |
| Bounded concurrency and backpressure | Required |
| CLI | Required |
| Durable local Job State Store | Required |
| Durable work-unit completion and process-restart resume | Required |
| Generic safe publication | Required only for destination modes whose semantics are verified and documented |
| Read-only Iceberg metadata inspection | P0 target; not a prerequisite for the core file-conversion MVP unless explicitly selected as a release milestone |
| DataFusion / DuckDB as mandatory runtime | Not selected; evaluate via ADR-0004 POC |
| Spark integration | Deferred |
| Avro / ORC / Arrow IPC | Deferred from initial MVP |
| Lance File / Vortex | Deferred pending ecosystem and adapter evaluation |
| Full Iceberg / Delta / Hudi / Lance Table migration | Deferred |
| Mid-work-unit resume | Deferred |
| Distributed State Store / multi-worker coordination | Deferred |
| Remote Worker / built-in distributed Coordinator | Deferred |
| Self-hosted API Server / Web UI | Future consideration, not MVP |

The table describes product commitments and deferrals, not the current implementation status. Actual release support must be based on implemented adapters and passing compatibility/integration tests.

### 8.3 MVP recovery and publication boundary

The MVP must durably record completed work units and safely resume remaining work after process restart. It does not require restoring partial progress inside a work unit.

Execution is at-least-once. A retry may repeat computation; correctness depends on attempt-isolated staging, conditional acceptance, validation, and controlled publication. UDC does not claim exactly-once execution.

Generic file/dataset output publication must use a destination mode whose guarantees have been tested. Prefix existence or successful object upload alone is not proof that a complete dataset has been published. Table-format publication is outside the generic file publisher and must use the table's native commit protocol.

See [ADR-0012](adr/ADR-0012-scalable-data-processing.md), [ADR-0013](adr/ADR-0013-job-manifest-and-state-management.md), and [ADR-0017](adr/ADR-0017-output-publication-protocol.md).

### 8.4 MVP acceptance criteria

1. Convert supported Parquet datasets without loading the entire dataset into memory.
2. Convert supported CSV and JSON datasets into Parquet.
3. Read and write through the cloud storage providers included in the release support matrix.
4. Preserve supported partition structures or report unsupported layouts.
5. Detect incompatible schema mappings before data movement begins.
6. Validate schema and row counts, with result semantics clearly reported.
7. Report actionable errors with retry classification.
8. Keep incomplete or unvalidated output out of the supported published view.
9. Resume remaining work after process restart using durable work-unit state.
10. Demonstrate bounded memory on a dataset substantially larger than the configured memory budget.
11. Demonstrate bounded queues and backpressure when the destination is slower than the source.
12. Demonstrate retry isolation after a work-unit failure without accepting stale or partial output.
13. Exercise ambiguous publication outcomes and verify idempotent reconciliation for each supported publication mode.
14. Provide reproducible CLI examples and automated unit/integration tests.

## 9. Architecture Principles

This section summarizes product-level boundaries. The linked ADR is authoritative for each detailed contract. Any technology or protocol marked Proposed or Under Evaluation remains unfinalized.

### 9.1 Modular architecture and ownership

The initial implementation is a modular Rust codebase, not a set of independently deployed microservices.

| Concern | Owns | Does not own |
|---|---|---|
| Canonical logical schema | Logical type semantics and compatibility policy | Physical decoding or batch execution |
| File-format adapter | Physical inspection, decoding/encoding, safe split and streaming capabilities | Global scheduling, retry state, or publication |
| Table-format adapter | Table snapshot, metadata, deletes, indexes, and native commit semantics | Generic file conversion |
| Catalog adapter | Discovery, registration, and catalog protocol | Job lifecycle |
| Storage adapter | Object/byte operations and provider capabilities | Credential policy, durable job state, or dataset-level visibility |
| Credential resolution | Provider identity selection and refresh integration | Object I/O |
| Execution backend | Batch processing and optional transformations | Job/attempt lifecycle or final publication |
| Validation | Meaning and evidence of correctness checks | Scheduling or durable state |
| Runtime | Async runtime and bounded runtime primitives | Global scheduler policy and job state |
| Orchestration | Planning, work-unit scheduling, worker contract, resource budgets, and publication workflow | Storage consistency semantics or table transaction implementation |
| Job State Store | Durable records, legal transitions, atomic acceptance, and recovery | Dataset payload I/O |
| Generic Publisher | File/dataset staging, manifest, and visibility protocol | Table-native transaction semantics |

The authoritative ownership map and conflict-resolution rules are in [ADR-0001](adr/ADR-0001-initial-architecture.md). Focused contracts are in ADR-0012 through ADR-0018.

### 9.2 Canonical data model and schema compatibility

UDC distinguishes:
- Logical meaning represented by a UDC-owned canonical logical schema.
- Physical source/target schema and format-specific metadata.
- In-memory execution representation, primarily Apache Arrow where supported.

Arrow is the primary interchange representation, not the sole canonical schema and not a mandatory requirement for every format library. Adapters may use format-native representations and bridge to Arrow where appropriate. The canonical schema defines type semantics and compatibility; it must not duplicate Arrow's array, buffer, or compute engine functionality.

See [ADR-0003](adr/ADR-0003-canonical-data-model.md).

### 9.3 File-format adapter contract

File-format adapters expose explicit, testable capabilities for inspection, split planning, streaming reads, and writes. Split boundaries must be safe for the underlying format and library; the scheduler cannot invent arbitrary byte or row-group splits. Plans must pin adapter/descriptor compatibility sufficiently to avoid silently reinterpreting persisted work after an upgrade.

Arrow RecordBatch is the initial interchange for compatible adapters, not a universal requirement.

See [ADR-0014](adr/ADR-0014-file-format-adapter-contract.md).

### 9.4 Execution backend

UDC must not require a query engine for pure streaming conversion.

Reference path for compatible conversions:

- Format Reader → bounded batch stream → Format Writer.

Native format pipelines, DataFusion, and DuckDB are candidates to compare through a proof of concept. Spark remains a later integration candidate, not the mandatory MVP execution engine. Backend capability differences must be exposed rather than hidden behind a false common denominator.

The selected MVP baseline and POC criteria are under evaluation in [ADR-0004](adr/ADR-0004-execution-engine-selection.md).

### 9.5 Storage, identity, and publication

Storage operations, cloud identity resolution, generic output publication, and table-native commits are distinct responsibilities:

- ADR-0005: object operations and provider capabilities.
- ADR-0016: identity source, credential resolution, and refresh.
- ADR-0017: generic file/dataset staging, manifest, and visibility protocol.
- ADR-0015: table-format snapshot and native commit protocol.

UDC must not assume object stores provide atomic directory rename or a universal conditional-update primitive. Safe publication guarantees are destination-specific and must be capability-checked and tested.

### 9.6 Job processing, state, and recovery

ADR-0012 owns planning, work-unit granularity, scheduling policy, resource budgets, worker contracts, and publication workflow.

ADR-0013 owns the persisted Job/Plan/Work Unit/Attempt/Publication records, legal state transitions, atomicity, durability, and single-node recovery.

ADR-0018 defines only a future distributed backend and coordination protocol for the ADR-0013 state contract. It does not redefine the state model and is not required for the MVP.

## 10. Proposed Technology and Dependency Direction

The following are candidates or directions, not uniformly finalized dependency selections. ADR status takes precedence over this summary.

| Component | Candidate / Direction | Status / qualification |
|---|---|---|
| Core language | Rust | Accepted; ADR-0002 |
| In-memory interchange | Apache Arrow | Primary interchange direction; not a universal adapter requirement; ADR-0003 / ADR-0014 |
| Canonical schema | UDC-owned logical schema | Proposed; ADR-0003 |
| Conversion execution | Native streaming pipeline | MVP reference path |
| Query execution | DataFusion / DuckDB | Under Evaluation; POC required; ADR-0004 |
| Distributed execution | Spark or remote UDC workers | Deferred; no MVP selection |
| Storage operations | Rust `object_store` behind UDC capability interface | Under evaluation; ADR-0005 |
| Async runtime | Tokio | Candidate subject to ecosystem validation; ADR-0007 |
| Cloud identity | Provider-native SDK chains and workload identity | Proposed; per-SDK validation required; ADR-0016 |
| Local Job State Store | SQLite or append-only journal | Backend selection open; ADR-0013 |
| Distributed Job State Store | PostgreSQL baseline candidate or another transactional/conditional backend | Deferred; ADR-0018 |
| CLI / configuration | clap / Serde; TOML and JSON candidates | Proposed; ADR-0009 |
| Errors | Typed core errors; thiserror / anyhow candidates | Proposed; ADR-0008 |
| Observability | tracing / OpenTelemetry candidates | Proposed; ADR-0010 |
| Workspace / features | Cargo workspace with focused adapter crates | Proposed; ADR-0011 |
| Table-format integrations | Mature protocol libraries where suitable | Per-format capability and licensing review required; ADR-0015 |

No dependency should be considered selected solely because it appears in this table. Concrete versions, feature flags, license compatibility, and supported capabilities must be verified before implementation and release.

## 11. Packaging and Repository Organization

### 11.1 MVP packaging

The MVP is intended to be distributed and run as a local CLI and reusable Rust library. Its runtime does not require an API server, hosted control plane, database service, or Kubernetes.

Container packaging may be useful for reproducible development and deployment, but a containerized service is not an MVP requirement.

### 11.2 Illustrative repository organization

The following is a logical organization guide, not a requirement to create every crate or directory before its functionality is needed.

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
├── integrations/
│   ├── spark/
│   └── duckdb/
├── examples/
├── tests/
│   ├── compatibility/
│   ├── integration/
│   └── benchmarks/
├── docs/
│   ├── adr/
│   ├── architecture/
│   ├── specifications/
│   └── guides/
├── Cargo.toml
├── README.md
└── CONTRIBUTING.md
```

Crates and integration directories should be introduced when they establish a useful ownership or dependency boundary, not pre-created speculatively.

## 12. Roadmap

The roadmap is capability-driven, not strictly time-driven. Priority labels identify sequencing intent and do not override MVP acceptance criteria or actual implementation status.

| Phase | Deliverable |
|---|---|
| P0 | Core contracts, local Parquet inspection/conversion, and reproducible baseline |
| P1 | CSV / JSON adapters and basic schema mapping |
| P2 | Validation semantics and durable local job/work-unit recovery |
| P3 | S3 / GCS integration and verified generic output publication |
| P4 | Azure integration, reliability hardening, and performance benchmarks |
| P5 | Iceberg metadata inspection |
| P6 | Avro / ORC / Arrow IPC and additional format coverage |
| P7 | Table-format rewrites, distributed execution, SDKs, and external integrations as independently validated capabilities |

This is a proposed sequence and may change as implementation evidence is gathered. The MVP remains single-node; bounded resource use and recovery are MVP requirements, not late-stage scale-out features. See [ADR-0012](adr/ADR-0012-scalable-data-processing.md) and [ADR-0013](adr/ADR-0013-job-manifest-and-state-management.md).

## 13. Success Metrics

### 13.1 Technical metrics

- Number of implemented and tested source/target format combinations.
- Number of storage providers with passing integration tests.
- Conversion throughput under a documented workload and environment.
- Peak resident memory and maximum in-flight bytes.
- Validation result coverage and false-assurance prevention tests.
- Successful job completion and restart-recovery rates.
- Retry isolation and publication-reconciliation correctness.
- Unsupported capability detection accuracy.

### 13.2 OSS adoption metrics

- Active external contributors.
- External projects and integrations using UDC.
- Release downloads.
- CLI adoption.
- Community issue resolution.
- Documentation and example usage.

GitHub Stars are supplementary indicators, not the primary success metric.

## 14. Future Considerations (Non-MVP)

The following are potential future directions, not committed requirements, roadmap milestones, or architecture decisions. They should be evaluated against demonstrated user demand, operational cost, security implications, and maintenance burden before being promoted.

### 14.1 Self-hosted deployment

UDC may eventually offer deployment modes beyond the standalone CLI/library so teams can run workloads inside infrastructure they control, including AWS, GCP, and Azure environments.

Potential profiles to evaluate:

- **Standalone / Embedded:** local CLI or library execution. This is the MVP baseline.
- **Self-hosted single-node service:** API and optionally a lightweight UI for submitting and observing jobs, with execution on the same host or container. Potential targets include a VM or container service.
- **Self-hosted distributed deployment:** separately scalable control-plane and worker processes, potentially deployed on Kubernetes or comparable infrastructure. This is a longer-term option.

If pursued, evaluate a clean separation between control-plane responsibilities (API, planning, scheduling, job coordination) and data-plane responsibilities (workers, format adapters, storage adapters), while preserving reuse of the same core processing contracts.

Operational topics include packaging, persistent state and artifact storage, workload identity, secret handling, private-network deployment, authorization, observability, upgrades, graceful shutdown, worker isolation, and backup/restore.

No cloud provider, compute service, orchestration platform, API, UI, or distributed topology is selected here. The MVP's single-node modular-monolith direction remains unchanged. Distributed coordination remains deferred under ADR-0018.

### 14.2 Additional execution and integration modes

Potential future evaluations include remote workers, alternative execution backends, SDK-first integrations, and additional catalog/table-format adapters. These must be justified by concrete workloads and must preserve the ownership boundaries in the ADRs.

## 15. Out of Scope for MVP

- Managed SaaS offering.
- Multi-tenant hosted control plane.
- API server or Web UI as a required MVP interface.
- Multi-host distributed execution and worker coordination.
- Full ETL orchestration platform.
- General-purpose SQL transformation engine.
- Continuous synchronization or replication.
- Automatic cloud-cost optimization.
- Enterprise governance platform.
- Full migration support for every feature of every table format.

## 16. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Existing OSS overlap | Focus on format interoperability, migration reliability, and validation evidence |
| Semantic differences between formats | Canonical logical schema, explicit mapping plans, and adversarial compatibility tests |
| Adapter capability mismatch | Capability descriptors, versioned contracts, and tested support matrices |
| Cloud API differences | Provider-specific capability reporting and integration tests |
| Object-store publication assumptions | Destination-specific commit protocol; never assume atomic directory rename |
| Memory exhaustion or resource starvation | Byte-aware memory admission, bounded queues, backpressure, and separate I/O/CPU limits |
| Partial migration failure | Attempt-isolated staging, durable acceptance, validation, and publication reconciliation |
| Process crash or duplicate work | Durable work-unit state; at-least-once execution with idempotent effects |
| Table-format corruption | Snapshot pinning and native table commit through mature protocol implementations |
| Cloud credential expiry or leakage | Provider-native refresh, short-lived identities, opaque handles, and secret redaction |
| Dependency or protocol maturity | POC, compatibility tests, licensing review, and explicit deferred capabilities |
| Premature distributed architecture | Keep MVP single-node; introduce remote coordination only when independently scaling is justified |

## 17. Open Architecture Decisions

Architecture contracts and decisions are tracked in the ADRs. A Proposed or Under Evaluation status means the decision is not finalized and must not be treated as a fixed implementation dependency.

| ADR | Topic | Status |
|---|---|---|
| [ADR-0001](adr/ADR-0001-initial-architecture.md) | Architecture principles, ownership, and conflict resolution | Accepted |
| [ADR-0002](adr/ADR-0002-rust-implementation-language.md) | Rust implementation language | Accepted |
| [ADR-0003](adr/ADR-0003-canonical-data-model.md) | Canonical logical schema and schema compatibility | Proposed |
| [ADR-0004](adr/ADR-0004-execution-engine-selection.md) | Execution backend selection and POC | Proposed — Under Evaluation |
| [ADR-0005](adr/ADR-0005-storage-abstraction.md) | Storage abstraction and provider capabilities | Proposed |
| [ADR-0006](adr/ADR-0006-validation-semantics.md) | Validation semantics and logical equality | Proposed |
| [ADR-0007](adr/ADR-0007-async-runtime-and-concurrency.md) | Async runtime and concurrency primitives | Proposed |
| [ADR-0008](adr/ADR-0008-error-handling-and-retry.md) | Error taxonomy and retry policy | Proposed |
| [ADR-0009](adr/ADR-0009-cli-and-configuration.md) | CLI and job configuration | Proposed |
| [ADR-0010](adr/ADR-0010-observability.md) | Observability and telemetry | Proposed |
| [ADR-0011](adr/ADR-0011-dependency-and-feature-management.md) | Workspace, dependencies, and features | Proposed |
| [ADR-0012](adr/ADR-0012-scalable-data-processing.md) | Planning, work units, scheduling, workers, and resource budgets | Proposed |
| [ADR-0013](adr/ADR-0013-job-manifest-and-state-management.md) | Durable job state and single-node recovery | Proposed |
| [ADR-0014](adr/ADR-0014-file-format-adapter-contract.md) | File-format adapter contract and safe split capabilities | Proposed |
| [ADR-0015](adr/ADR-0015-table-format-integration-boundary.md) | Table-format integration and native commits | Proposed |
| [ADR-0016](adr/ADR-0016-cloud-authentication.md) | Cloud identity and credential resolution | Proposed |
| [ADR-0017](adr/ADR-0017-output-publication-protocol.md) | Generic file/dataset output publication | Proposed |
| [ADR-0018](adr/ADR-0018-distributed-job-state-store.md) | Future distributed Job State Store and coordination | Proposed; deferred until multi-worker execution is required |

Other open questions include dependency license compatibility, exact release support matrices, and implementation-specific library/version choices. These should be resolved through implementation evidence and focused ADR updates rather than by treating this PRD as a substitute for detailed design.

## 18. Product Definition of Done

A release is considered ready for its declared support level when:

- Supported capabilities and known limitations are documented.
- Compatibility tests pass for the declared format/library versions.
- Required cloud integration tests pass for the declared provider capabilities.
- Schema mapping and validation guarantees are tested, including adversarial cases.
- Failure and retry scenarios are tested.
- Work-unit completion is durably recorded and process-restart recovery is tested for releases claiming resumability.
- Publication failure and ambiguous-acknowledgement scenarios are tested for each supported publication mode.
- Memory, concurrency, and performance benchmarks are reproducible.
- Security review covers credential handling and secret redaction.
- CLI documentation and executable examples are available.
- Breaking changes and persisted-plan/state compatibility are documented.
- The release notes distinguish implemented capability from planned or experimental capability.

---

**Product Statement**

UDC is not merely another file conversion utility.

It is an open-source interoperability platform intended to make data portable, verifiable, and reliable across modern data infrastructure.
