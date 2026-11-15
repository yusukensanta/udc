# UDC — Product Requirements Document

**Universal Data Converter**

| Attribute | Value |
|---|---|
| Project | UDC |
| Full Name | Universal Data Converter |
| Document | Product Requirements Document |
| Version | 0.5.0 |
| Status | Draft |
| License | Apache License 2.0 (proposed; subject to dependency/license review) |
| Development Model | OSS-first |
| Primary Language | Rust |
| Target Users | Data Engineers / Data Platform Engineers |

---

## 1. Executive Summary

UDC (Universal Data Converter) is an open-source tool that runs data-format conversions as verified, resumable jobs.

Its mission is to make a conversion trustworthy: classified before it starts, validated against its source, resumable after a failure, and published only when it has passed.

UDC aims to provide a unified product experience for:

- Evaluating and applying explicit schema mappings before data moves.
- Validating conversion results with clearly stated guarantees.
- Running recoverable jobs with bounded resource consumption and controlled output publication.
- Inspecting source datasets and their schemas.
- Converting between supported file formats.
- Reading from one supported storage provider and writing to another within a conversion job.
- Integrating with table formats through their native metadata and transaction protocols.

UDC will reuse mature format, storage, table-protocol, and execution libraries where practical. It will not reimplement an entire query engine or table-format protocol merely to provide a common user experience.

**Product principle:** UDC owns schema-mapping policy, job orchestration, validation policy, and user-facing capability reporting. Specialized libraries remain authoritative for the low-level format, storage, and table-protocol behavior they implement.

**Positioning.** Converting between these formats and reaching these storage systems are already served by mature tools (§2.5). UDC's intended contribution is the job layer around a conversion: classifying schema compatibility before data moves, recording validation evidence under published rules, resuming from durably completed work, and publishing only validated output. It delivers these together, as a single binary, for datasets stored as plain files rather than in a table format. Whether enough users need that combination is not yet established; §13.3 defines how it is tested.

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

### 2.5 Existing tools and where UDC fits

The documentation of about 40 existing tools was reviewed on 2026-11-15 against the capabilities planned here. No tool was executed for that review, and several "not found" results rest on a capability being absent from documentation rather than on an explicit statement. The table below must be read with that limit.

| Planned capability | Relative to existing tools |
|---|---|
| File-format conversion (Parquet, CSV, JSON) | Already served. DuckDB and clickhouse-local convert between these formats from a single binary; Spark and Polars convert them as well |
| Local, S3, GCS, and Azure storage, including across clouds | Already served. The same engines read and write these stores, and rclone is the baseline for moving bytes between any pair |
| Single-binary distribution | Already served when taken on its own |
| Bounded memory | Unproven. Existing engines document streaming or spilling rather than a hard byte bound, but UDC has no measurement yet |
| Schema compatibility classified before data moves | Partial gap. Engines increasingly fail at run time on overflow instead of corrupting silently; none was found that classifies the field mapping before the job starts |
| Validation evidence recorded by the conversion job | Gap in integration only. Comparison tools such as datacompy and the Data Validation Tool exist separately. No converter was found that checks its own output against the source, and no tool was found that publishes its equality rules as a specification |
| Resume from durably completed work | Gap only in combination. NiFi, SeaTunnel, dlt, and Airbyte resume from recorded progress but need a JVM, a server, or a Python runtime; the single-binary engines do not resume |
| Publication of validated output only | Gap for plain files. Writing to Iceberg or Delta Lake already gives an atomic commit; for plain-file output, no reviewed tool stages, validates, and then publishes. UDC cannot make a set of plain files appear atomically to a reader that lists a prefix; what it adds is that nothing unvalidated becomes visible (FR-07) |
| Table-format migration | Metadata-only registration and translation are served by the table formats' own tooling and by Apache XTable, and UDC does not duplicate them. Three gaps remain where row data is read or rewritten: checking plain files against a table schema before registration, validating a table against the files it came from, and loading files that need a rewrite with validation before the commit (§5.2) |

Three consequences follow.

1. **UDC is not differentiated by conversion or storage reach.** Its distinct part is the job layer around a conversion: pre-flight schema classification, validation evidence under published rules, resume, and publication of validated output, for datasets stored as plain files, in a single binary. Each element exists in some tool. The combination was not found.
2. **The realistic alternative is a wrapped engine, not a bare one.** An existing engine driven by a script that adds a per-attempt staging prefix, a row-count check, a ledger of completed units, and a completion marker can reproduce much of that job layer. UDC therefore saves integration work; it does not make possible something that was impossible. §13.3 uses this configuration as the reference to measure against.
3. **The failures are documented; the demand is not.** The failure modes in §2.4 are well supported, most strongly non-atomic job commit on object stores. No direct evidence was found that practitioners want one integrated tool for them. That is an absence of evidence, not evidence of absence. It is carried as an open risk (§16) and tested through the gates in §13.3.

One boundary follows from the first consequence. UDC does not offer a byte-for-byte copy or synchronization of objects between stores. That is served by tools such as rclone and by the providers' own transfer services. Cross-cloud operation is a property of a conversion job, whose source and destination may be on different providers; it is not a product of its own.

The position is also moving. Engines fail loudly more often than they used to, which narrows the schema-safety gap, and adoption of table formats reduces the number of users who publish plain files. The plain-file-to-table operations in §5.2 are the response to the second trend: they apply the same job layer where the destination is a table.

References for this section:

- [DuckDB `COPY`](https://duckdb.org/docs/2.0/sql/statements/copy.html) and [tuning workloads](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html)
- [clickhouse-local](https://clickhouse.com/docs/operations/utilities/clickhouse-local)
- [rclone overview](https://rclone.org/overview/)
- [datacompy CLI](https://capitalone.github.io/datacompy/cli.html) and [Data Validation Tool](https://github.com/GoogleCloudPlatform/professional-services-data-validator)
- [Spark cloud integration](https://spark.apache.org/docs/latest/cloud-integration.html) and [Hadoop S3A committer architecture](https://hadoop.apache.org/docs/stable/hadoop-aws/tools/hadoop-aws/committer_architecture.html)
- [NiFi overview](https://nifi.apache.org/nifi-docs/overview.html), [SeaTunnel state storage and recovery](https://seatunnel.apache.org/docs/engines/zeta/state-storage-and-recovery), [dlt running in production](https://dlthub.com/docs/running-in-production/running), and [Airbyte resumability](https://docs.airbyte.com/platform/understanding-airbyte/resumability)
- [Iceberg table migration](https://iceberg.apache.org/docs/latest/table-migration/) and [Spark procedures](https://iceberg.apache.org/docs/latest/spark-procedures/)
- [Delta Lake table utilities](https://docs.delta.io/latest/delta-utility.html) and [Apache XTable](https://xtable.apache.org/docs/how-to/)

## 3. Product Vision

**Verified, resumable conversion jobs for plain-file datasets.**

UDC will make the result of a conversion something a user can check, without pretending that all formats, stores, engines, or table protocols have identical capabilities.

The product is organized around four pillars:

1. **Data integrity:** classify schema compatibility before data moves, and record validation evidence under published rules.
2. **Reliable job execution:** plan work, bound resource use, isolate failures, recover completed work, and publish only validated output.
3. **Format coverage:** inspect and convert supported physical representations while preserving or explicitly mapping logical meaning.
4. **Storage reach:** access local and cloud object storage through capability-aware adapters.

Pillars 1 and 2 are where UDC intends to differ from existing tools. Pillars 3 and 4 are prerequisites: they are built by reusing existing libraries, they are added where the job layer is needed, and they are not what UDC competes on (§2.5).

The name Universal Data Converter is kept. "Universal" describes the intended reach of the job layer across formats and stores. It is not a claim to convert more formats than existing tools do.

## 4. Target Users and Primary Use Cases

### 4.1 Data Engineer

Needs to convert, move, and validate datasets without building a bespoke pipeline for each format and storage pair.

Typical use cases:
- Parquet to CSV, JSON, or another supported columnar format.
- Compression or physical-layout changes.
- Partition-preserving dataset conversion.
- Conversion whose source and destination are on different storage providers.
- Schema compatibility checks before a large transfer.

### 4.2 Data Platform Engineer

Needs conversions and table loads whose results can be verified across lakehouse and storage technologies.

Typical use cases:
- Inspecting table metadata and supported table features.
- Planning a table-format migration.
- Checking plain files against a table schema before registering them with the table format's own tooling.
- Verifying a table against the plain files it was created from.
- Loading CSV, JSON, or Parquet that needs a rewrite into a table, with validation before the commit.
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
| Orchestration | Planner, Scheduler, Worker | Job planning, work-unit lifecycle, retries, resource budgets, and invocation of validation and publication |
| Publication | Generic Publisher, table-native commit | Making a validated output set visible in a stated publication mode or through a native table commit |

**Priority and phase labels.** Two different labels are used and they must not be confused:

- **Capability priority (P0–P3)** ranks integration targets *within one layer's table* below. P0 is the first group of targets in that layer, P1 the next, P2 requires an evaluation before any commitment, and P3 depends on earlier capabilities in the same layer. A priority label says nothing about MVP membership or timing.
- **Roadmap phase (Phase 0–8)** states sequencing and is defined in §12. The Phase column below links each capability to it.

MVP membership is defined only by §8.2.

### 5.1 File and columnar formats

The format list below is a capability roadmap, not a claim that these formats are currently implemented or production-ready.

| Format | Intended read/write scope | Priority | Phase | Notes |
|---|---|---|---|---|
| Apache Parquet | Read and write | P0 | Phase 0 | Primary analytical columnar format |
| CSV | Read and write | P0 | Phase 1 | Interchange format; parsing and type inference policies must be explicit |
| JSON / JSONL | Read and write | P0 | Phase 1 | Semi-structured interchange; schema inference and heterogeneous records require explicit policy |
| Apache Avro | Read and write | P1 | Phase 7 | Row-oriented serialization and schema evolution |
| Apache ORC | Read and write | P1 | Phase 7 | Columnar analytical format |
| Apache Arrow IPC / Feather | Read and write | P1 | Phase 7 | Arrow-native interchange and file representation |
| Lance File | Evaluate read/write | P2 | Not scheduled | Distinct from Lance Table. Existing engines read and write Lance mainly as a dataset with table semantics; conversion into it is already served |
| Vortex | Evaluate read/write | P2 | Not scheduled | File format declared stable from release 0.36.0. Already read and written by DuckDB, DataFusion, Spark, and Polars, so an adapter is justified only by demand for the job layer on this format |

UDC support is defined by the capabilities implemented and tested in its adapter—not by the format's inclusion in this table. Each adapter must report its actual inspection, split, read, write, and option capabilities. See [ADR-0014: File Format Adapter Contract](adr/ADR-0014-file-format-adapter-contract.md).

**Lance distinction:** Lance File and Lance Table are separate integration targets. A file adapter does not imply table, index, catalog, namespace, or transaction support.

### 5.2 Table formats

| Format | Intended capability | Priority | Phase | Boundary |
|---|---|---|---|---|
| Apache Iceberg | Metadata and snapshot inspection | P0 | Phase 5 | Initial table-format integration target; read-only inspection does not imply rewrite |
| Apache Iceberg | Compatibility check of plain files against a table schema, before registration by another tool | P0 | Phase 5 | Read-only; UDC produces a report and does not register files |
| Apache Iceberg | Validation of a plain-file dataset against a table snapshot | P0 | Phase 5 | Read-only; refused when the snapshot carries deletes the adapter cannot apply |
| Apache Iceberg | Validated ingestion of plain files by append commit | P1 | Phase 6 | For data that must be rewritten; append only; requires a catalog integration and its ADR |
| Apache Iceberg | Data-file rewrite / migration of an existing table | P1 | Phase 8 | Requires snapshot pinning, delete handling, conflict detection, and native commit |
| Delta Lake | Integration evaluation | P2 | Not scheduled | Protocol feature compatibility and available Rust/JVM integration must be assessed |
| Apache Hudi | Integration evaluation | P2 | Not scheduled | Timeline and table-type semantics must be assessed |
| Lance Table | Metadata inspection | P2 | Not scheduled | Separate from Lance File |
| Lance Table | Migration / rewrite | P3 | Not scheduled | Must account for fragments, deletions, indices, manifests, and native commit behavior |

**Plain files to a table.** UDC does not reimplement metadata-only adoption of existing files: Iceberg `migrate`, `snapshot`, and `add_files`, Delta Lake `CONVERT TO DELTA`, and Apache XTable already register or translate files without reading row data. UDC covers the parts of that path where row data is read or rewritten: the compatibility check, dataset-to-snapshot validation, and validated ingestion listed above. The operations are defined in [ADR-0015](adr/ADR-0015-table-format-integration-boundary.md).

A table-format feature is supported only when its adapter can preserve the relevant table semantics. Unsupported protocol features must be surfaced explicitly; they must not be silently ignored. The authoritative integration boundary and snapshot/commit responsibilities are specified in [ADR-0015](adr/ADR-0015-table-format-integration-boundary.md).

### 5.3 Storage providers

| Provider | Service | Priority | Phase | Notes |
|---|---|---|---|---|
| Local | Local filesystem | P0 | Phase 0 | Development and local execution |
| AWS | Amazon S3 | P0 | Phase 3 | |
| GCP | Google Cloud Storage | P0 | Phase 3 | |
| Azure | Azure Blob Storage | P0 | Phase 4 | Target capability; release inclusion depends on tested capability coverage |

Storage adapters expose object operations and provider-specific capabilities. They must not assume filesystem rename semantics or universal atomic directory publication. The storage abstraction is described in [ADR-0005](adr/ADR-0005-storage-abstraction.md).

A storage provider is supported as a source or destination of conversion jobs. Copying or synchronizing objects between providers without converting them is not a UDC capability (§2.5).

Authentication is a separate concern. UDC should prefer native credential chains, short-lived credentials, and workload identity. Credential references—not resolved secrets—may be persisted in job metadata. The proposed identity and refresh boundary is described in [ADR-0016](adr/ADR-0016-cloud-authentication.md).

### 5.4 Catalogs and namespaces

Catalog integration is distinct from storage and table-format integration. A catalog adapter is responsible for discovery, registration, and catalog-specific operations; it does not own job lifecycle or file conversion.

Glue, REST Catalog, and Lance Namespace are examples of ecosystems to evaluate. No catalog implementation is part of the MVP.

Validated ingestion into an Iceberg table (Phase 6, §5.2) requires one catalog integration. Which catalog is supported first, and the catalog adapter contract, must be decided in a dedicated ADR before that phase starts. Complete catalog migration is not planned.

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
- A format is offered as a conversion target only if UDC can also read it, because validation reads the output back.

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

The compatibility evaluator must produce a deterministic, versioned `SchemaMappingPlan` containing source/target logical schemas, field mapping, coercion operations, policy decisions, warnings, and a digest. The canonical model and compatibility decision rules are defined in [ADR-0003](adr/ADR-0003-canonical-data-model.md).

### FR-05: Data validation

UDC must distinguish structural validation, transfer integrity, and logical data equivalence. Each result must state its scope and guarantee.

Validation levels:

| Level | Name | What a pass can establish |
|---|---|---|
| L1 | Structural | Declared schema and structural properties satisfy the selected policy |
| L2 | Cardinality | Row or record counts agree; does not prove values agree |
| L3 | Statistics | Selected aggregates/statistics agree under defined normalization |
| L4 | Logical fingerprint | Canonicalized hashes of logical values agree under a versioned encoding; evidence, not proof |
| L5 | Exact comparison | Logical records agree under an explicitly defined equality and normalization policy |

Transfer integrity is a separate check, not a validation level. A physical checksum or ETag comparison establishes that stored or copied bytes are intact. It must not be reported as L4 or presented as proof of logical equivalence.

Requirements:
- The normalization rules that define logical equality are published as a versioned specification with conformance vectors. Every result records the rules version and the normalization policy in effect.
- Target-side evidence is taken from the stored output by reading it back, not from counters held by the writer.
- Each result states what it covers relative to the schema mapping. A field whose mapping is lossy or policy-dependent is validated after coercion, and the result says so.
- Value-level evidence (L4) must be computable within the bounded-memory streaming model, without sorting the dataset.
- A mismatch at a selected level prevents publication. The affected work unit is run once more from the source; a mismatch that repeats fails the job, and no setting publishes in spite of it.

The level names, algorithms, normalization rules, the source of evidence, and the guarantee each result may claim are governed by [ADR-0006: Validation Semantics](adr/ADR-0006-validation-semantics.md).

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
- Explicit resume of a failed or cancelled job over its sealed plan, reusing durably completed work units while the plan, source identity, and accepted outputs remain valid.
- No exactly-once execution claim; safe effects are achieved through attempt isolation, acceptance, validation, and publication.

The MVP requires a durable local Job State Store, restart recovery, and explicit resume. The persisted state model, legal transitions, and the recovery and resume contracts are defined in [ADR-0013](adr/ADR-0013-job-manifest-and-state-management.md). Planning, scheduling, worker contracts, resource budgets, and job failure policy are defined in [ADR-0012](adr/ADR-0012-scalable-data-processing.md).

### FR-07: Safe output publication

UDC must not present incomplete or unvalidated output as a successfully published dataset.

For generic file/dataset output, the proposed protocol uses attempt-isolated staging outside the destination, an immutable output manifest, validation, and a publication mode. The mode is selected according to how the dataset's consumers find the data, and each mode has a stated guarantee:

| Publication mode | Protects | Guarantee |
|---|---|---|
| Promotion (default) | Consumers that list a prefix, such as a query engine given a path or an external table location | Validated before visible: nothing appears under the destination before the whole output has passed validation, and a job that fails before publication leaves the destination unchanged. The set of objects does not appear atomically |
| Reference | Consumers that read a publication reference | All or nothing: the consumer sees the previous output set or the new one |

UDC does not claim an atomic commit for plain files read by listing a prefix. A consumer that needs a complete set waits for the completion marker that promotion writes last.

Requirements:
- Stage outputs separately from the published dataset.
- Bind publication to the exact accepted output set.
- Validate before any output object reaches a location that consumers read.
- Never place an output object over an existing object, and never delete an object the publication did not place.
- Report the publication mode and its guarantee with every publication result.
- Use conditional writes, version preconditions, or another verified destination-specific mechanism where available.
- Reconcile ambiguous publication outcomes after process failure.
- Detect conflicting writes to the same logical destination.
- Clean up only unreferenced staging artifacts.
- Reject the job at planning time where the destination cannot provide the primitives the selected mode requires; never fall back to writing directly into the destination.
- When a publication is interrupted, complete it on resume, or withdraw the objects it placed when the job is abandoned.

There is no universal atomic directory rename guarantee across object stores. Generic file/dataset publication is specified in [ADR-0017](adr/ADR-0017-output-publication-protocol.md). Table-format writes must use their native commit protocol as specified in ADR-0015.

### FR-08: CLI

UDC must provide a CLI for local inspection, conversion, validation, and job operations.

Initial command concepts:
- `udc inspect` — schema, metadata, and capabilities of a dataset.
- `udc convert` — a conversion job, with a plan-only form that prints the schema compatibility classification before any data is written.
- `udc validate` — compare two existing datasets under the same rules a conversion job uses, without converting or publishing. This also checks a conversion performed by another tool.
- `udc job status`
- `udc job resume`
- `udc job abandon`

Configuration is resolved from CLI flags, then environment variables, then the configuration file, then defaults. Exact flags, file format, and compatibility policy remain subject to [ADR-0009](adr/ADR-0009-cli-and-configuration.md).

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

- Every error must be classified into one of the categories defined by ADR-0008 (configuration, compatibility, data, authentication/authorization, transient, resource, conflict, cancelled, internal), each with a default retry disposition.
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
- A failed or cancelled job must be resumable over its sealed plan without rewriting completed work units, while the plan, source identity, and accepted outputs remain valid.
- Mid-work-unit checkpointing is not required for the MVP.
- State-store implementation details must not be confused with bulk dataset storage or artifact storage.

The local durability and resume contract belongs to ADR-0013. A distributed backend must implement the same logical state contract and is deferred to ADR-0018.

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
- Validating schema (L1), row counts (L2), and logical fingerprints (L4) under the published normalization rules.
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
| Schema validation (L1) | Required |
| Row-count validation (L2) | Required |
| Normalization rules, version 1, published with conformance vectors | Required for the logical types reachable from the MVP formats |
| Logical fingerprint validation (L4) | Required |
| Statistics and exact comparison (L3, L5) | Not an MVP commitment |
| Transfer-integrity check (physical checksum; not a validation level) | Basic, with guarantee clearly labeled |
| Streaming and bounded memory | Required |
| Bounded concurrency and backpressure | Required |
| CLI | Required |
| Standalone validation of two existing datasets (`udc validate`) at the MVP validation levels | Required |
| Durable local Job State Store | Required |
| Durable work-unit completion and process-restart resume | Required |
| Explicit resume of a failed or cancelled job over its sealed plan | Required |
| Generic publication, Promotion mode (validated before visible) | Required for each storage provider in the release support matrix |
| Generic publication, Reference mode (all or nothing for consumers that read the reference) | Optional; only with a consumer convention that has been implemented and verified (ADR-0017) |
| Read-only Iceberg metadata inspection | First table-format target (Phase 5); not a prerequisite for the core file-conversion MVP unless explicitly selected as a release milestone |
| DataFusion / DuckDB as mandatory runtime | Not selected; evaluate via ADR-0004 POC |
| Spark integration | Deferred |
| Avro / ORC / Arrow IPC | Deferred from initial MVP |
| Lance File / Vortex | Deferred; decided by demand for the job layer on these formats, since conversion into them is already served |
| Plain-file compatibility check and dataset-to-snapshot validation for Iceberg | Deferred (Phase 5) |
| Validated ingestion of plain files into an Iceberg table | Deferred (Phase 6) |
| Metadata-only registration or translation of existing files | Not planned; provided by the table formats' own tooling |
| Byte-for-byte copy or synchronization of objects between stores | Not planned; provided by tools such as rclone and by provider transfer services |
| Full Iceberg / Delta / Hudi / Lance Table migration | Deferred |
| Mid-work-unit resume | Deferred |
| Reuse of completed work across different plans or jobs | Deferred |
| Distributed State Store / multi-worker coordination | Deferred |
| Remote Worker / built-in distributed Coordinator | Deferred |
| Self-hosted API Server / Web UI | Future consideration, not MVP |

The table describes product commitments and deferrals, not the current implementation status. Actual release support must be based on implemented adapters and passing compatibility/integration tests.

### 8.3 MVP recovery and publication boundary

The MVP must durably record completed work units and safely resume remaining work after process restart. It does not require restoring partial progress inside a work unit.

A job that ends FAILED or CANCELLED keeps its completed work units. An explicit resume re-runs only the remaining units over the same sealed plan; a change that alters the plan requires a new job.

Execution is at-least-once. A retry may repeat computation; correctness depends on attempt-isolated staging, conditional acceptance, validation, and controlled publication. UDC does not claim exactly-once execution.

Generic file/dataset output is published in a publication mode whose guarantee has been tested for the destination. The MVP default is Promotion mode: validated output is placed under the destination prefix only after validation, and a completion marker is written last. Prefix existence or successful object upload alone is not proof that a complete dataset has been published. Table-format publication is outside the Generic Publisher and must use the table's native commit protocol.

See [ADR-0012](adr/ADR-0012-scalable-data-processing.md), [ADR-0013](adr/ADR-0013-job-manifest-and-state-management.md), and [ADR-0017](adr/ADR-0017-output-publication-protocol.md).

### 8.4 MVP acceptance criteria

1. Convert supported Parquet datasets without loading the entire dataset into memory.
2. Convert supported CSV and JSON datasets into Parquet.
3. Read and write through the cloud storage providers included in the release support matrix.
4. Preserve supported partition structures or report unsupported layouts.
5. Detect incompatible schema mappings before data movement begins.
6. Validate schema (L1), row counts (L2), and logical fingerprints (L4), with result semantics, normalization rules version, and coverage clearly reported.
7. Detect an injected changed value, dropped row, and duplicated row in the output through L4, and pass when only row order or physical encoding differs.
8. Report actionable errors with retry classification.
9. Keep unvalidated output out of the destination, and leave the destination unchanged when a job fails before publication.
10. Resume remaining work after process restart, and after an explicit resume of a failed or cancelled job, using durable work-unit state and without rewriting completed work units.
11. Demonstrate bounded memory on a dataset substantially larger than the configured memory budget.
12. Demonstrate bounded queues and backpressure when the destination is slower than the source.
13. Demonstrate retry isolation after a work-unit failure without accepting stale or partial output.
14. Exercise ambiguous publication outcomes and interrupted publications, and verify idempotent reconciliation, completion on resume, and withdrawal on abandon for each supported publication mode.
15. Provide reproducible CLI examples and automated unit/integration tests.

## 9. Architecture Principles

This section summarizes product-level boundaries. The linked ADR is authoritative for each detailed contract. Any technology or protocol marked Proposed or Under Evaluation remains unfinalized.

### 9.1 Modular architecture and ownership

The initial implementation is a modular Rust codebase, not a set of independently deployed microservices.

| Concern | Owns | Does not own |
|---|---|---|
| Canonical logical schema | Logical type semantics, compatibility outcomes, and the schema mapping plan | Physical decoding or batch execution |
| File-format adapter | Physical inspection, decode/encode, format metadata, and safe split and streaming capabilities | Global scheduling, job state, retry policy, or publication |
| Table-format adapter | Table snapshot, metadata, deletes, indexes, and native commit semantics | Generic file conversion or generic file publication |
| Catalog adapter | Table discovery, registration, and catalog protocol | Job lifecycle |
| Storage adapter | Object bytes, range reads, listing, multipart primitives, and provider capabilities | Credential policy, durable job state, or dataset-level visibility |
| Credential resolution | Provider identity selection and refresh integration | Object I/O or CLI syntax |
| Execution backend | Batch processing and optional transformations | Job/Attempt lifecycle or final publication |
| Validation | Meaning and evidence of correctness checks | Scheduling or durable state |
| Runtime | Async runtime and bounded runtime primitives | Scheduling policy, resource-budget policy, or durable state |
| Error handling | Error taxonomy, retry eligibility, and backoff rules | Persisting attempts or accepting output |
| CLI and configuration | User-facing commands, configuration format, and configuration precedence | Internal job-state representation or credential resolution |
| Observability | Instrumentation, cardinality and redaction rules, and export | The job state machine |
| Orchestration | Planning, work-unit scheduling, worker contract, resource budgets, job failure policy, and the point at which validation and publication are invoked | Persisted state schema, storage consistency semantics, validation semantics, or the publication protocol |
| Job State Store | Durable Job/Plan/Work Unit/Attempt/Publication records, legal transitions, atomic acceptance, recovery, and explicit resume | Dataset payload I/O, format decoding, or table transactions |
| Generic Publisher | File/dataset staging layout, output manifest, and publication modes with their guarantees | Table-native transactions, or inventing atomic rename |
| Packaging and distribution | Distribution channels, official targets and feature set, crate and binary naming, release pipeline, and the public-release gate | Cargo feature mechanics, or persisted-state versioning |

This table summarizes the responsibility map in [ADR-0001](adr/ADR-0001-initial-architecture.md), which is authoritative together with its shared vocabulary and conflict-resolution rules. Focused contracts are in ADR-0003 through ADR-0019.

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
- ADR-0017: the Generic Publisher and its staging, output manifest, and publication modes.
- ADR-0015: table-format snapshot and native commit protocol.

UDC must not assume object stores provide atomic directory rename or a universal conditional-update primitive. Safe publication guarantees are destination-specific and must be capability-checked and tested.

### 9.6 Job processing, state, and recovery

ADR-0012 owns planning, work-unit granularity, scheduling policy, resource budgets, worker contracts, job failure policy, and the point at which validation and publication are invoked. It does not define the publication protocol, which belongs to ADR-0017.

ADR-0013 owns the persisted Job/Plan/Work Unit/Attempt/Publication records, legal state transitions, atomicity, durability, single-node recovery, and explicit resume of a failed or cancelled job.

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
| Workspace / features | Cargo workspace with focused adapter crates; smallest workable set of published crates | Proposed; ADR-0011 |
| Packaging / distribution | Prebuilt binaries on GitHub Releases plus crates.io; `dist`, `release-plz`, and Trusted Publishing as automation candidates | Proposed; ADR-0019 |
| Table-format integrations | Mature protocol libraries where suitable | Per-format capability and licensing review required; ADR-0015 |

No dependency should be considered selected solely because it appears in this table. Concrete versions, feature flags, license compatibility, and supported capabilities must be verified before implementation and release.

## 11. Packaging and Repository Organization

### 11.1 MVP packaging

The MVP is intended to be distributed and run as a local CLI and reusable Rust library. Its runtime does not require an API server, hosted control plane, database service, or Kubernetes.

The proposed distribution is prebuilt binaries on GitHub Releases plus crates.io packages, starting at the first MVP release. The repository is private until that release and becomes public with it, so no public installation channel exists before then.

- The package name `udc` belongs to unrelated projects on crates.io, PyPI, and npm. The proposed CLI package is `udc-cli`, installing a command named `udc`; fallback names are prepared in ADR-0019.
- Every channel ships one official feature set, which matches the release support matrix.
- Release artifacts are built only by CI and carry checksums and provenance attestations.

Channels, official targets, naming, the release pipeline, and the conditions for making the repository public are specified in [ADR-0019](adr/ADR-0019-packaging-and-distribution.md).

Container packaging may be useful for reproducible development and deployment, but a containerized service is not an MVP requirement.

### 11.2 Illustrative repository organization

The following is a logical organization guide, not a requirement to create every crate or directory before its functionality is needed.

The crate list is an upper bound, not a plan. Every crate that a published crate depends on must itself be published to crates.io, and a published name is permanent, so the first release publishes the smallest workable set and an adapter may begin as a Cargo feature of an existing crate. See [ADR-0011](adr/ADR-0011-dependency-and-feature-management.md).

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

The roadmap is capability-driven, not strictly time-driven. Phases identify sequencing intent and do not override MVP acceptance criteria or actual implementation status. Phase numbers are distinct from the capability priority labels (P0–P3) defined in §5.

| Phase | Deliverable |
|---|---|
| Phase 0 | Core contracts, local Parquet inspection/conversion, reproducible baseline, and the reference configuration with the first evidence gate (§13.3) |
| Phase 1 | CSV / JSON adapters and basic schema mapping |
| Phase 2 | Validation semantics including normalization rules version 1 and L4, durable local job/work-unit recovery, and explicit resume |
| Phase 3 | S3 / GCS integration and verified generic output publication |
| Phase 4 | Azure integration, reliability hardening, and performance benchmarks |
| Phase 5 | Read-only Iceberg: metadata inspection, compatibility check of plain files before registration, and dataset-to-snapshot validation |
| Phase 6 | Validated ingestion of plain files into an Iceberg table by append commit |
| Phase 7 | Avro / ORC / Arrow IPC and additional format coverage |
| Phase 8 | Rewrite of an existing Iceberg table: data-file rewrite with snapshot pinning, delete handling, conflict detection, and native commit |

Phases 0–1 build conversion, which existing tools already provide (§2.5). The job layer that distinguishes UDC arrives in Phases 2–3. The evidence gate at the end of Phase 0 exists so that this investment is checked before it is made. After the MVP, the table path (Phases 5–6) is sequenced ahead of additional file formats (Phase 7), because more formats repeat what existing tools provide and the table path does not.

Distributed execution, SDKs, and integrations with external systems are not roadmap phases. They are future considerations (§14) and are scheduled only when a concrete workload or the adoption evidence of §13.3 calls for them.

The MVP defined in §8 corresponds to Phases 0–4; Azure's inclusion in the MVP release remains gated on tested support (§8.2). This is a proposed sequence and may change as implementation evidence is gathered. The MVP remains single-node; bounded resource use and recovery are MVP requirements, not late-stage scale-out features. See [ADR-0012](adr/ADR-0012-scalable-data-processing.md) and [ADR-0013](adr/ADR-0013-job-manifest-and-state-management.md).

## 13. Success Metrics

### 13.1 Technical metrics

The first group measures the job layer, which is what UDC is positioned on (§2.5). The second group measures prerequisites and coverage; growth in it is not by itself success.

Job layer:

- Fault detection by each validation level on the injected fault classes of ADR-0006, and the number of false passes, which must be zero.
- Cost of each validation level relative to the same conversion without validation.
- Share of incompatible schema mappings and unsupported capabilities reported at planning time, before any data is written.
- Share of interrupted jobs that resume to completion without re-running completed work units.
- Publication correctness in the failure-injection suite: no unvalidated object observed at a destination, and every ambiguous outcome reconciled.
- Retry isolation: no stale or partial output accepted.

Prerequisites and coverage:

- Peak resident memory and maximum in-flight bytes relative to the configured budget.
- Conversion throughput under a documented workload and environment, stated next to the reference configuration (§13.3).
- Number of implemented and tested source/target format combinations.
- Number of storage providers with passing integration tests.

### 13.2 OSS adoption metrics

- Active external contributors.
- External projects and integrations using UDC.
- Release downloads.
- CLI adoption.
- Community issue resolution.
- Documentation and example usage.

GitHub Stars are supplementary indicators, not the primary success metric.

### 13.3 Value hypotheses and evidence gates

§2.5 identifies where UDC could add value. It does not show that users need it. The hypotheses below turn that question into things that can be checked.

They are assessed against a **reference configuration**: an existing single-binary engine driven by a script that adds a per-attempt staging prefix, a row-count check with read-back, a ledger of completed units, and a completion marker, run on the MVP reference demonstration (§8.1).

| ID | Hypothesis | Evidence | Gate |
|---|---|---|---|
| H1 | Some users publish converted datasets as plain files rather than through a table format, and partial or unverified output is a real cost to them | Conversations with practitioners outside the project; public issue reports or write-ups describing the problem | End of Phase 0 |
| H2 | The reference configuration is costly to build or leaves gaps in practice | Build it. Interrupt writes at several points against a disposable bucket. Record what remains at the destination (partial objects, pending multipart uploads) and what the script had to handle | End of Phase 0 |
| H3 | UDC holds a memory bound that the reference configuration does not | Peak resident memory of both on a dataset substantially larger than the budget (§8.4; ADR-0004 proof of concept) | Before ADR-0004 is finalized |
| H4 | Value-level validation inside the job finds faults that L1 and L2 miss, at an acceptable cost | Fault-injection results and the cost of L4 relative to the same conversion without validation (ADR-0006) | End of Phase 2 |
| H5 | Users moving plain files into a table format want the schema check before registration, or validation tied to the commit, and do not get it from the table format's own tooling | Conversations with practitioners who have run such a migration; issue reports on registered files that did not match the table | Before Phase 5 starts |

Rules for the gates:

- The bar for a hypothesis is written down before its evidence is collected, so that the result cannot move the bar.
- A hypothesis without evidence at its gate counts as not supported, and is recorded as such in this document.
- If H1 or H2 is not supported at the end of Phase 0, the maintainers choose one of the following before Phase 2 starts and record the choice here:
  1. Narrow UDC to the job layer over an existing engine used as the execution backend. This feeds ADR-0004.
  2. Narrow UDC to validating conversions performed by other tools.
  3. Continue as planned, with the reason stated.
  4. Stop.
- If H3 is not supported, bounded memory stays a requirement (NFR-01) but is no longer described as a differentiator.
- If H4 is not supported, the L4 commitment in §8.2 is reconsidered before the MVP release.
- If H5 is not supported, Phases 5–6 are reduced to metadata inspection or reordered behind Phase 7.

Proposed starting bars, to be confirmed by the maintainers before collection begins:

- **H1:** at least five practitioners outside the project independently describe publishing plain-file datasets from conversion jobs and a cost caused by partial or unverified output.
- **H2:** at least one interruption case leaves output visible to readers, or leaves state that the script cannot reconcile without implementing the equivalent of acceptance (ADR-0013) and publication (ADR-0017).
- **H3:** the reference configuration exceeds the memory budget on the test dataset and UDC stays within it.
- **H4:** L4 detects every fault class listed in the ADR-0006 validation plan, and its cost stays within a bound set before measurement.
- **H5:** at least three practitioners outside the project independently describe a plain-file-to-table migration in which a mismatch was found after registration, or in which validation had to be built separately.

After the first release, the adoption metrics in §13.2 are read against these hypotheses: use of validation, resume, and publication counts as evidence for the job layer, and use of conversion alone does not.

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

Potential future evaluations include distributed execution with remote workers, alternative execution backends, language SDKs and SDK-first integrations, integrations with external orchestration or catalog systems, and additional catalog/table-format adapters. None of them has a roadmap phase. These must be justified by concrete workloads and must preserve the ownership boundaries in the ADRs.

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
| Existing tools already provide conversion, storage reach, and single-binary distribution (§2.5) | Do not position UDC on those; concentrate differentiation on the job layer for plain-file datasets; measure against the reference configuration (§13.3) |
| Demand for an integrated job layer is unproven | Evidence gates H1 and H2 at the end of Phase 0, with the recorded options in §13.3 if they are not supported |
| The gap narrows as engines fail loudly and table formats spread | Repeat the existing-tool review before each release that changes positioning; apply the job layer to table destinations through the plain-file-to-table operations (§5.2, ADR-0015) |
| The plain-file-to-table path depends on append and commit support in a table library and on a catalog contract that has no ADR yet | Gate each operation on tested adapter capabilities; write the catalog ADR before Phase 6; report a missing capability as unsupported instead of emulating it |
| Differentiating validation arrives too late or costs too much | Normalization rules version 1 and L4 are MVP commitments; fault detection and cost are measured (H4) |
| Adding L4 enlarges the MVP | Limit rules version 1 to the logical types reachable from the MVP formats; keep L3 and L5 deferred |
| Semantic differences between formats | Canonical logical schema, explicit mapping plans, and adversarial compatibility tests |
| Adapter capability mismatch | Capability descriptors, versioned contracts, and tested support matrices |
| Cloud API differences | Provider-specific capability reporting and integration tests |
| Object-store publication assumptions | Publication modes with stated guarantees, selected from verified capabilities; never assume atomic directory rename |
| Promotion mode is mistaken for an atomic commit | State the mode and its guarantee with every publication result and in the documentation; write a completion marker for consumers that need a complete set; offer Reference mode once a consumer convention is verified |
| The extra copy of promotion is too costly for large outputs | Provider-side copy within one store; measure promotion time against conversion time (ADR-0017); revisit the sealed version location if the cost is material |
| Memory exhaustion or resource starvation | Byte-aware memory admission, bounded queues, backpressure, and separate I/O/CPU limits |
| Partial migration failure | Attempt-isolated staging, durable acceptance, validation, publication reconciliation, and explicit resume over the sealed plan |
| Process crash or duplicate work | Durable work-unit state; at-least-once execution with idempotent effects |
| Table-format corruption | Snapshot pinning and native table commit through mature protocol implementations |
| Cloud credential expiry or leakage | Provider-native refresh, short-lived identities, opaque handles, and secret redaction |
| Dependency or protocol maturity | POC, compatibility tests, licensing review, and explicit deferred capabilities |
| Premature distributed architecture | Keep MVP single-node; introduce remote coordination only when independently scaling is justified |
| Package name `udc` is taken on crates.io, PyPI, and npm, and other names cannot be reserved | Publish as `udc-cli` under the `udc-` prefix; warn in installation docs; keep the fallback naming plans of ADR-0019 ready; re-check names at the public-release gate |
| Native dependencies break a build target | Explicit TLS and native-library choices validated per target before the target is declared supported |

## 17. Open Architecture Decisions

Architecture contracts and decisions are tracked in the ADRs. A Proposed or Under Evaluation status means the decision is not finalized and must not be treated as a fixed implementation dependency. ADRs carry no priority labels; an ADR must be accepted before the roadmap phase that first depends on it.

| ADR | Topic | Status |
|---|---|---|
| [ADR-0001](adr/ADR-0001-initial-architecture.md) | Architecture principles, ownership, and conflict resolution | Accepted |
| [ADR-0002](adr/ADR-0002-rust-implementation-language.md) | Rust implementation language | Accepted |
| [ADR-0003](adr/ADR-0003-canonical-data-model.md) | Canonical logical schema and schema compatibility | Proposed |
| [ADR-0004](adr/ADR-0004-execution-engine-selection.md) | Execution backend selection and POC | Proposed — Under Evaluation |
| [ADR-0005](adr/ADR-0005-storage-abstraction.md) | Storage abstraction and provider capabilities | Proposed |
| [ADR-0006](adr/ADR-0006-validation-semantics.md) | Validation levels (L1–L5), normalization rules, transfer integrity, and logical equality | Proposed |
| [ADR-0007](adr/ADR-0007-async-runtime-and-concurrency.md) | Async runtime and concurrency primitives | Proposed |
| [ADR-0008](adr/ADR-0008-error-handling-and-retry.md) | Error categories and retry policy | Proposed |
| [ADR-0009](adr/ADR-0009-cli-and-configuration.md) | CLI, job configuration, and configuration precedence | Proposed |
| [ADR-0010](adr/ADR-0010-observability.md) | Observability and telemetry | Proposed |
| [ADR-0011](adr/ADR-0011-dependency-and-feature-management.md) | Workspace, dependencies, and features | Proposed |
| [ADR-0012](adr/ADR-0012-scalable-data-processing.md) | Planning, work units, scheduling, workers, resource budgets, and job failure policy | Proposed |
| [ADR-0013](adr/ADR-0013-job-manifest-and-state-management.md) | Durable job state, single-node recovery, and explicit resume | Proposed |
| [ADR-0014](adr/ADR-0014-file-format-adapter-contract.md) | File-format adapter contract and safe split capabilities | Proposed |
| [ADR-0015](adr/ADR-0015-table-format-integration-boundary.md) | Table-format integration and native commits | Proposed |
| [ADR-0016](adr/ADR-0016-cloud-authentication.md) | Cloud identity and credential resolution | Proposed |
| [ADR-0017](adr/ADR-0017-output-publication-protocol.md) | Generic Publisher and file/dataset output publication | Proposed |
| [ADR-0018](adr/ADR-0018-distributed-job-state-store.md) | Future distributed Job State Store and coordination | Proposed; deferred until multi-worker execution is required |
| [ADR-0019](adr/ADR-0019-packaging-and-distribution.md) | Packaging, release, distribution, and the public-release gate | Proposed |

Other open questions include dependency license compatibility, exact release support matrices, and implementation-specific library/version choices. These should be resolved through implementation evidence and focused ADR updates rather than by treating this PRD as a substitute for detailed design.

## 18. Product Definition of Done

A release is considered ready for its declared support level when:

- Supported capabilities and known limitations are documented.
- Compatibility tests pass for the declared format/library versions.
- Required cloud integration tests pass for the declared provider capabilities.
- Schema mapping and validation guarantees are tested, including adversarial cases.
- For releases claiming L4 or L5, the normalization rules version in use is published with its conformance vectors.
- Failure and retry scenarios are tested.
- Work-unit completion is durably recorded, and process-restart recovery and explicit resume are tested, for releases claiming resumability.
- Publication failure and ambiguous-acknowledgement scenarios are tested for each supported publication mode.
- Memory, concurrency, and performance benchmarks are reproducible.
- Security review covers credential handling and secret redaction.
- CLI documentation and executable examples are available.
- Release artifacts are built by the release pipeline for every declared target, and installation is verified through each supported channel.
- Breaking changes and persisted-plan/state compatibility are documented.
- The release notes distinguish implemented capability from planned or experimental capability.

---

**Product Statement**

UDC does not aim to be another way to convert files.

It aims to make a conversion a job whose result can be trusted: classified before it starts, validated against its source, resumable after a failure, and published only when it has passed.
