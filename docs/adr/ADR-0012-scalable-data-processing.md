# ADR-0012: Scalable Data Processing Architecture

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** Job planning, work-unit granularity, scheduling policy, the worker contract, resource budgets, job failure policy, and the point at which validation and publication are invoked.

## 1. Context

UDC must process datasets whose total size can be far larger than process memory and, eventually, local disk. Scale is multidimensional:

- **Volume:** total bytes and rows.
- **Cardinality:** object/file count and metadata entries.
- **Shape:** file-size distribution, row-group distribution, partitions, nested-schema complexity.
- **Skew:** uneven work-unit sizes and processing costs.
- **Resource constraints:** RAM, CPU, local disk, network bandwidth, sockets, file descriptors.
- **Remote-system constraints:** object-store request quotas, throttling, multipart limits, egress bandwidth, and cost.
- **Failure duration:** long jobs can encounter process restarts, credential expiry, transient cloud failures, or partially completed uploads.

A design that streams one large file can still fail on hundreds of millions of objects if it materializes the entire listing. A design that parallelizes every file can exhaust memory, sockets, provider quotas, or destination capacity. UDC must therefore treat planning, scheduling, data movement, retries, and publication as one resource-governed system.

The MVP should be a useful single-node application. It should not require a distributed control plane. However, its execution model should preserve a credible path to multiple worker processes or nodes without changing the meaning of a job.

## 2. Decision drivers

1. Total dataset size must not determine peak process memory.
2. Throughput should increase with available CPU, network, and storage capacity until a measured bottleneck or provider limit is reached.
3. Memory, task count, queue depth, open resources, and provider request rates must remain bounded.
4. Many-small-file and few-large-file workloads must both be supported deliberately.
5. Work must be independently schedulable and recoverable at a safe format-specific granularity.
6. Retries must not create duplicate or visible partial outputs.
7. Job plans and work-unit descriptions must be serializable and independent of process-local closures.
8. The local MVP should remain simple to install, run, debug, and test.
9. Correctness must be preserved when execution order and worker assignment are nondeterministic.
10. Observability must expose bottlenecks and resource pressure without unbounded metric cardinality.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| Sequential whole-dataset processing | Minimal scheduler complexity | Poor resource utilization; whole-job restart; can be constrained by memory and single-stream throughput |
| Single-node bounded streaming with independent work units | Good local utilization; bounded memory; simple deployment; unit-level retry | Limited by one machine and one process failure domain |
| Distributed workers from day one | Horizontal scale and independent worker capacity | Requires durable coordinator, leases, worker protocol, network state management, deployment and compatibility machinery |
| Delegate all scheduling to Spark or another engine | Reuses a mature distributed scheduler | Couples job semantics and recovery to engine semantics; adds runtime integration and may not fit lightweight local CLI usage |

## 4. Proposed decision

Adopt **a resource-bounded, work-unit-based execution model**.

- The initial runtime is single-node.
- UDC owns job planning, work-unit identity, job state, retry policy, validation policy, staging, and publication semantics.
- Format adapters expose safe splitting and reader/writer capabilities; they do not own global job orchestration.
- Execution backends perform work within UDC-provided resource budgets.
- The job/work-unit model must be serializable so future workers can execute it remotely.
- A built-in multi-node coordinator is deferred until benchmarks or user requirements show that single-node execution is insufficient.

The intended conceptual structure is:

`Job -> Plan -> Work Units -> Attempts -> Staged Outputs -> Validation -> Publication`

This is a design direction, not a commitment to a specific scheduler crate or persistent state database.

## 5. Rationale

Sequential processing leaves the machine idle and restarts the whole job after any failure. Distributed workers from the first release would require a coordinator, leases, and a worker protocol before a single conversion is useful. Delegating scheduling to an external engine would tie recovery, validation, and publication to that engine's semantics, and those are the part of a job that UDC is positioned on ([PRD §2.5](../PRD.md#25-existing-tools-and-where-udc-fits)).

A single-node runtime over independent Work Units gives bounded memory, retry of one unit instead of the job, and a simple installation. Because plans and Work Units are serializable data and not process-local closures, the same model can later be executed by remote workers (ADR-0018) without changing what a job means. Owning the job layer and not the batch processing is also what keeps the execution backend replaceable (ADR-0004).

## 6. Domain model

This section defines the processing concepts and their identity rules. The persisted record for each concept, and its states, are defined only by ADR-0013 §6.

### 6.1 Job

A Job is the immutable user intent plus execution policy. It includes:

- Job ID and configuration version.
- Source and destination references.
- The required source consistency class (§8).
- Format and table capability selections.
- Canonical schema and mapping policy references.
- Output layout and file-sizing policy.
- Validation level and normalization policy.
- Resource budget profile.
- Retry and timeout policy.
- Publication policy.
- Resolved plan reference and plan digest.

Credentials and secret values must not be embedded in the serialized job. The job contains credential references or provider identity configuration only.

### 6.2 Plan

A Plan is a deterministic, inspectable description of the work to be done. It includes:

- Plan ID and digest.
- The recorded identity of every source object and the consistency class it reaches (§8).
- Schema mapping and format capabilities required.
- Work-unit descriptors and their stable IDs.
- Expected output ownership for each unit.
- Resource requirements/estimates where available.
- Validation and publication instructions.

The plan must distinguish **known totals** from **unknown totals**. It must support paginated or incremental discovery; it must not require collecting all object metadata in RAM before processing begins.

A plan never claims more consistency than its source objects provide. The class reached, and what a job can rely on in each class, are defined in §8.

### 6.3 Work Unit

A Work Unit is the smallest independently schedulable unit for which UDC can define input boundaries, output ownership, retry behavior, and completion criteria. Its format-native input boundary must originate from the safe SplitDescriptor contract in [ADR-0014](ADR-0014-file-format-adapter-contract.md); the Scheduler must not derive arbitrary splits itself.

A Work Unit descriptor should contain:

- Stable unit ID derived from a canonical descriptor and plan identity.
- Source object or table reference and its recorded identity (§8).
- Format adapter and capability identifier.
- Logical input range (file, row group, partition, range, or adapter-specific split).
- Schema/mapping version.
- Deterministic output key or output ownership token.
- Estimated input bytes/rows when known.
- Required resource class.
- Validation scope.
- Dependency references, if any.

The unit ID must not depend on worker assignment, attempt number, or execution order.

A Work Unit must not be split at arbitrary byte offsets unless the underlying encoding and reader support safe independent decoding. The format adapter reports split boundaries and whether a split is independently readable.

### 6.4 Attempt

An Attempt is one execution of a Work Unit. It writes to its own staging namespace and reports a structured outcome. Its recorded fields and states are defined by ADR-0013.

At-least-once execution is expected. UDC does not promise exactly-once execution. Instead, it must make repeated attempts safe through isolated staging, idempotent output ownership, validation, and a controlled commit/publish step.

## 7. Component responsibilities

### 7.1 Planner

The Planner:

1. Validates the job configuration and preconditions.
2. Inspects source metadata and records the identity of every source object (§8).
3. Resolves format capabilities and schema compatibility.
4. Produces deterministic Work Unit descriptors.
5. Estimates work size and resource class when possible.
6. Writes a plan or plan fragments through the JobStateStore (ADR-0013).

Planning must use pagination and bounded metadata concurrency. For extremely large listings, the Planner may append plan fragments incrementally and mark discovery completion explicitly.

### 7.2 Scheduler

The Scheduler:

- Admits work only when all required resource budgets are available.
- Maintains bounded ready/in-flight queues.
- Applies per-provider and per-destination concurrency limits.
- Separates I/O concurrency from CPU decode/encode concurrency.
- Avoids starvation of small units behind a few very large units.
- Tracks retries, deadlines, cancellation, and worker health.
- Persists state transitions before acknowledging durable completion.

The initial Scheduler is an in-process component. Its API should operate on serializable work descriptors, not arbitrary in-memory closures.

### 7.3 Worker

A Worker executes one attempt:

`read -> decode -> transform (optional) -> encode -> stage -> validate`

In a validation-only job (ADR-0013 §7.4) a Work Unit stops after decoding: it computes evidence for its part of one dataset, and nothing is encoded or staged.

The validate step includes reading the staged output back where ADR-0006 requires it. That read is admitted under the same resource budgets as any other I/O (§10).

A worker should be stateless between attempts. It receives a Work Unit descriptor, a resource budget/lease, and a staging destination. It reports structured progress and outcome.

Worker code must not independently decide global retries or publish a whole job. The Scheduler owns retry scheduling, and publication is invoked only as described in §7.5.

### 7.4 Job State Store boundary

The processing architecture depends on a durable JobStateStore, but does not define its persisted schema or legal transitions. Those are exclusively owned by [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md). The Scheduler invokes the State Store contract to claim work and report outcomes; it must not maintain a competing authoritative state machine.

### 7.5 Publication step

Orchestration decides *when* publication happens: once per job, after every required Work Unit has an accepted Attempt and the required job-level validation has succeeded. It does not define *how* output becomes visible.

- Generic file/dataset output is published by the Generic Publisher. Its staging layout, output manifest, and publication modes are defined only by ADR-0017. Object placement during publication is admitted under the same resource budgets as any other I/O (§10).
- Table-format output is committed by the TableFormatAdapter through the table's native protocol (ADR-0015). The Generic Publisher must not bypass snapshot or catalog transaction semantics.
- Publication intent and outcome are recorded through the JobStateStore (ADR-0013).

## 8. Source identity and consistency

A job converts its source as the source was identified when the job was planned. This section defines how a source object is identified, when the identity is captured and checked, and what happens when the object changes. It is the job's **source consistency policy** that ADR-0013 refers to.

### 8.1 Identity of a source object

The Planner records an identity for every source object in the plan. Which fields exist depends on the provider (ADR-0005):

| Field | Meaning | Examples |
|---|---|---|
| Version identifier | Names one version of the object; a read can address that version directly | S3 version ID in a bucket with versioning enabled; GCS generation; Azure version ID with blob versioning enabled |
| Change validator | An opaque value that changes when the object is replaced; a read can be made conditional on it | S3 ETag; Azure ETag |
| Metadata | Size, modification time, and file identity; no conditional read exists | Local filesystem: size, modification time, and device and inode, or file ID on Windows |

A content checksum that the provider reports, such as an S3 additional checksum, the GCS CRC32C, or an Azure Content-MD5, is recorded as well where present. It is evidence about the bytes, not the identity, and it is not required. An ETag is never treated as a checksum: an S3 ETag is not an MD5 digest for a multipart upload or for an object encrypted with SSE-KMS or SSE-C.

### 8.2 Consistency classes

The strongest identity available for an object decides its consistency class:

| Class | When it applies | What the job can rely on |
|---|---|---|
| Pinned | A version identifier, and the provider retains earlier versions: S3 versioning, GCS object versioning, or Azure blob versioning | Every read names the recorded version. An overwrite after planning does not affect the job while that version is retained |
| Checked | A change validator, or a generation that a read can name, without retention of earlier versions | Every read request is conditional on the recorded identity. A replaced object makes the read fail; the job never reads the new content, but it cannot complete with the old content either |
| Best effort | Metadata only, as on a local filesystem | Size, modification time, and file identity are compared before and after each read. A change that leaves all three unchanged is not detected |

The job states a **required class**. By default it is Checked for object-store sources and Best effort for local files. A job may require Pinned. The Planner rejects a job whose source objects do not reach the required class with a Compatibility error (ADR-0008), before any data is read. Every job result states the class achieved, as the weakest class among its source objects.

On Azure an update of a blob's metadata or properties can also change its ETag. Such a change is reported as a change of the source: the policy fails closed.

### 8.3 When identity is captured and checked

- **Planning.** The identity of every source object is captured from the listing or a metadata request and sealed into the plan. It is covered by the plan digest (ADR-0013). The objects in the plan are the source set: an object created after the listing is not part of the job.
- **Every read.** In the Pinned and Checked classes, every request to a source object carries the recorded identity: data reads, footer and metadata reads, each range read, and the source-side reads that produce validation evidence (ADR-0006). In the Best effort class, metadata is compared before the first read of a Work Unit and after its last.
- **Resume.** Before an explicit resume is accepted, the identity of every source object is checked again, including the objects of COMPLETED Work Units (ADR-0013).

Identity is not checked again before publication. The published output corresponds to the source as identified at planning, not to the source at the time of publication, and the job result says so.

### 8.4 When a source object changes

| The object changes or is deleted | Pinned | Checked | Best effort |
|---|---|---|---|
| After planning, before its Work Unit reads it | The job reads the recorded version | The read fails with a Conflict error | The check before the read fails with a Conflict error |
| While its Work Unit reads it | No effect | The next request fails with a Conflict error | The check after the read fails with a Conflict error, unless size, modification time, and file identity are all unchanged |
| After its Work Unit completed, in the same execution | No effect; the output corresponds to the recorded version | Same | Same |
| Between a failed or cancelled execution and an explicit resume | Resume is accepted while the recorded version is retained | Resume is rejected; a new job is needed | Resume is rejected if the metadata differs |

A Conflict error is never retried blindly (ADR-0008): the Work Unit fails, and the job failure policy (§13.4) applies. A source that keeps changing therefore cannot be converted in the Checked class. It needs versioning, so that the job runs in the Pinned class, or a copy taken before the job.

## 9. Work-unit granularity and format capabilities

Work-unit granularity is format- and workload-specific:

| Granularity | Suitable cases | Constraints |
|---|---|---|
| Object/file | Many independent files | Very small files can make scheduler and request overhead dominant |
| Row group | Large Parquet files | Requires safe reader support and independent row-group boundaries |
| Partition | Partitioned datasets and table-aware operations | Partition skew can be severe; partitioning does not guarantee balanced work |
| Byte range | Splittable encodings and range-readable storage | Requires format-level synchronization/indexing; arbitrary compressed byte ranges are not safe |
| Record/block | Formats with independently decodable blocks | Adapter-specific offsets and schema semantics required |

For Parquet, the file footer and metadata describe row groups and column chunks. Row group is a natural map-style unit where the selected reader supports independent access; column chunk/page are more commonly I/O and decoding granularities. Do not assume each page or arbitrary byte range is an independent output work unit. [Parquet format structure](https://github.com/apache/parquet-format).

The capability descriptor that reports these properties is defined by ADR-0014 §6.1. Planning and scheduling consume it, in particular: metadata-only inspection, safe split enumeration and split independence, range-read and streaming-decode support, row and byte estimates, projection and predicate pushdown, independently owned output objects, and per-reader and per-writer concurrency constraints.

The Scheduler chooses among adapter-provided splits; it must not invent unsafe splits.

## 10. Bounded streaming and resource governance

### 10.1 Resource dimensions

UDC must govern at least:

- Total in-flight memory bytes.
- Maximum batch bytes and/or rows.
- Concurrent source reads.
- Concurrent CPU decode/encode operations.
- Concurrent destination writes.
- Multipart upload concurrency and parts in flight.
- Open files and sockets.
- Per-provider request rate and retry budget.
- Temporary disk/spill budget.
- Per-job and process-wide resource budgets.

### 10.2 Byte-aware memory admission

Queue capacity measured only in number of batches is insufficient because a batch's memory footprint varies with row width, nested data, string/binary payloads, and buffer sharing.

The execution pipeline should reserve memory credits before materializing or enqueueing a batch and release them only when the last consumer releases the relevant buffers. Where exact memory accounting is unavailable, use conservative estimates plus an explicit safety margin and hard process-level limits.

Arrow exposes array-buffer size estimates such as `RecordBatch::get_array_memory_size`; this is useful telemetry, but it can overcount shared buffers and is not a complete process-RSS accounting mechanism. [Arrow Rust RecordBatch](https://arrow.apache.org/rust/arrow/record_batch/struct.RecordBatch.html).

The memory budget is not equal to the entire configured process limit. It must reserve headroom for runtime, metadata, decompression/encoding scratch space, allocator fragmentation, and libraries that allocate outside the tracked pool.

### 10.3 Backpressure

All producer-consumer queues must be bounded. When downstream stages are slow, upstream production waits or reduces admission. An unbounded queue is prohibited in the core data path.

Tokio's guidance explicitly warns that unbounded queues can consume all available memory; bounded channels and explicit concurrency are required. [Tokio channels](https://tokio.rs/tokio/tutorial/channels).

### 10.4 Separate I/O and CPU pools

Network I/O concurrency and CPU parallelism are independent tuning dimensions. CPU-heavy decompression, decoding, encoding, and hashing must not starve async I/O workers. Use bounded CPU execution capacity and independent I/O semaphores.

### 10.5 Adaptive controls

The first implementation should use explicit configurable limits and conservative defaults. Adaptive concurrency may be added after reliable signals exist (queue wait, throughput, throttling, error rate, memory pressure). Do not introduce an opaque autoscaler before deterministic manual limits and metrics work.

## 11. Scheduling, throughput, and skew

The Scheduler should use a bounded ready queue and a bounded in-flight set. It should not create one task for every discovered object.

Scheduling policy should consider:

- estimated input bytes and rows;
- expected processing cost / compression ratio where known;
- provider and destination limits;
- small-unit latency and fairness;
- straggler behavior.

The first scheduler can use a simple policy (for example, bounded concurrency with size-aware ordering and fairness). Work stealing or advanced adaptive scheduling should be added only after benchmark evidence.

The system must avoid a few huge units monopolizing all slots while millions of small units wait. Conversely, it should not starve large units indefinitely. Fairness and throughput trade-offs must be measurable.

## 12. Many-small-file and few-large-file strategies

### 12.1 Many small files

- Paginate listings and process metadata incrementally.
- Batch metadata operations when provider APIs allow it.
- Bound open-file, request, and task concurrency.
- Reduce per-file setup overhead through connection reuse and efficient writer lifecycle.
- Support output compaction/aggregation with configurable target file sizes.
- Do not create a single enormous in-memory list of paths.

### 12.2 Few large files

- Stream sequentially where format readers require it.
- Use row-group or other safe intra-file splits when the adapter supports them.
- Use ranged reads only when access patterns and storage costs justify them.
- Keep batch and decompression memory bounded.
- Avoid excessive concurrent range reads that amplify request costs or overload storage.

### 12.3 Output sizing and partitioning

Target output file size must be configurable. It is a workload-specific optimization, not a universal magic number. UDC should expose file count and size distribution so users can tune downstream scan efficiency. Partition fan-out must be bounded to avoid generating many tiny output files.

## 13. Completion, failure, and publication boundaries

The authoritative Job, Work Unit, Attempt, and Publication state machines, legal transitions, atomicity, durability, and crash-recovery protocol are defined only by [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md). This section describes processing-layer behavior that uses those guarantees.

### 13.1 Work Unit completion boundary

A Work Unit is eligible for durable completion only after:
1. Its Attempt has written output to isolated staging.
2. The writer reports durable completion according to the destination adapter contract.
3. The configured validation policy has produced the required evidence.
4. ADR-0013 accepts exactly one Attempt and durably records the output reference.

### 13.2 Checkpoint granularity

For this ADR, a checkpoint means the boundary between independently completed Work Units. Safe resume from inside a Work Unit is format-adapter-specific and is not assumed. ADR-0013 defines how completed units are persisted and recovered.

A source object that changes during the job is handled as defined in §8. A retry should restart the whole Work Unit unless the format adapter exposes a safe deterministic resume position.

### 13.3 Idempotency and duplicate attempts

- Work Unit identity is stable across Attempts.
- Every Attempt writes to isolated output ownership.
- Worker success is not equivalent to Work Unit completion.
- The State Store decides which validated Attempt is accepted.
- Late or duplicate Attempts cannot overwrite accepted output.
- Error classification and retry budget are owned by ADR-0008.

### 13.4 Work Unit failure and job outcome

A Work Unit becomes FAILED when its error is not retryable, its retry budget is exhausted, or a validation mismatch repeats on its one further Attempt (ADR-0008). A job with a FAILED required Work Unit cannot proceed to job-level validation or publication.

The default Scheduler policy on the first FAILED Work Unit is `fail-fast`:

1. Stop admitting new Work Units for the job.
2. Let in-flight Attempts reach a durable outcome, either acceptance through the normal path or cancellation, within the configured shutdown deadline.
3. Report the job as FAILED through the JobStateStore, with the failed units and their error categories.

Completed Work Units keep their accepted output. Failing the job does not roll them back or delete their staged objects. Whether and how that completed work is reused is defined by the explicit-resume contract in ADR-0013 §10.

A `continue` policy, which keeps processing independent Work Units after a failure so that the failure report is complete and a later resume has less left to do, is a candidate option and not an MVP requirement. Under either policy nothing is published while a required Work Unit is FAILED.

### 13.5 Publication

Orchestration invokes publication as described in §7.5. The protocol is owned by ADR-0017 for generic output and by ADR-0015 for table-native commits. Storage operations and conditional-write capabilities are owned by ADR-0005, validation semantics by ADR-0006, and the publication record with its recovery references by ADR-0013.

## 14. Scale-out boundary

The MVP is one process on one node. It should nevertheless use:

- Serializable Job and Work Unit descriptors.
- Versioned plan and manifest schemas.
- Explicit worker input/output contracts.
- Durable state transitions separate from worker memory.
- Storage references rather than process-local paths as the only addressing form.
- Idempotent, attempt-isolated outputs.
- Capability-negotiated execution backends.

A future distributed coordinator would add leases, heartbeats, worker registration, duplicate-delivery protection, state-store transactions/conditional writes, worker binary compatibility, network security, and scheduling across heterogeneous resources. Those are explicitly out of MVP scope.

Do not promise that the single-node manifest is already a distributed state store. Its abstraction should preserve the option, while its first implementation can remain local and single-writer.

## 15. Observability and operational controls

Instrument names and types, cardinality and redaction rules, and export are owned by ADR-0010. The processing layer must supply at least these signals:

- Job: planned/completed/failed work units, total and completed bytes/rows, elapsed time.
- Scheduler: ready queue size, active units, queue wait, retry wait, scheduling delay.
- Memory: in-flight bytes, reserved credits, largest batch, estimated versus observed RSS.
- I/O: read/write bytes, throughput, request latency, active requests, throttling and retry counts.
- CPU: decode/encode utilization and time per unit.
- Output: file count, size distribution, compaction ratio.
- Recovery: resumed units, abandoned attempts, cleanup counts and recovery duration.

The cardinality and redaction rules of ADR-0010 apply to all of these signals; in particular, object paths, partition values, and job IDs are not metric labels.

## 16. Failure model

The architecture must explicitly handle:

- Source object missing or changed after planning.
- Expired/insufficient credentials.
- Provider throttling and transient network failures.
- Slow or unavailable destination.
- Corrupt input and deterministic decoding errors.
- Disk full and memory pressure.
- Process termination during read, transform, upload, validation, or publication.
- Duplicate/late worker completion.
- State-store write failure.
- Cancellation during multipart upload.

Retry eligibility and budgets follow ADR-0008: only eligible categories are retried, within attempt and time budgets, and deterministic Data and Compatibility errors fail fast. A process crash must leave outputs staged, not visible as a successful dataset.

## 17. Trade-offs and consequences

- Planning, manifests, and state transitions create metadata and implementation complexity.
- Format adapters expose different safe split capabilities; there is no universal split API that makes arbitrary data splittable.
- Memory estimates are imperfect; byte credits need safety headroom and RSS monitoring.
- At-least-once execution is accepted; correctness relies on staged outputs, idempotency, and controlled publication rather than exactly-once task execution.
- Single-node scale-out readiness does not automatically provide distributed correctness. Multi-writer state, leases, consistency, and worker versioning are scoped by ADR-0018.
- Simpler static limits are less adaptive but easier to reason about and benchmark.
- In the Checked class a source that keeps changing cannot be converted at all. That is deliberate: reading a mixture of old and new content would be worse than failing.

## 18. Validation plan

Benchmarks must cover more than one large Parquet file.

### 18.1 Workload profiles

| Profile | Shape | What it validates |
|---|---|---|
| Many-small-files | Millions of objects, small per-file size | Listing, metadata throughput, scheduler overhead, connection reuse |
| Few-large-files | Few very large files and row groups | Streaming, row-group scheduling, range reads, memory bounds |
| Skewed | Highly uneven file and partition sizes | Fairness, straggler handling, throughput |
| Wide/nested schema | Large binary/string columns and deeply nested fields | Byte-aware memory and batch sizing |
| Slow sink | Destination throughput below source throughput | Backpressure and bounded buffering |
| Throttled source | Provider throttling/timeouts | Retry budget and adaptive limits |
| Failure injection | Kill process during every major stage | Recovery and publication safety |

### 18.2 Metrics

Measure end-to-end throughput and cost per TiB; peak RSS; in-flight bytes; CPU utilization; network throughput; object requests/sec; task count; queue wait; retries; time spent in each stage; output file count/size distribution; and recovery time.

### 18.3 Acceptance criteria

- Peak memory remains within the configured process budget plus documented runtime/allocator headroom as total input size increases.
- Queue depth, in-flight bytes, active requests, and task count remain bounded under slow-sink and throttling tests.
- Increasing work-unit count does not cause planner memory to grow linearly with all discovered objects; planning must paginate or spill/persist fragments.
- With sufficient independent work and available resources, throughput increases as concurrency increases until a measured CPU, network, storage, or provider limit is reached.
- A failed Work Unit can be retried without rewriting accepted Work Units or exposing partial output.
- A source object replaced at each point of the table in §8 is never read in its new state: the job reads the recorded version or fails with a Conflict error, as the table states. Each provider and class is tested separately.
- Process interruption at every stage can recover to a valid terminal state or fail with explicit cleanup instructions.
- Results include hardware, software versions, cloud region, dataset shape, limits, and benchmark scripts.

Do not claim PB-scale support from a single-node benchmark. Scale claims must specify dataset shape, worker count, resource budget, cloud topology, and throughput.

## 19. Ownership boundary

**Owns:** planning, the source identity and consistency policy, work-unit granularity selection, scheduling policy and fairness, the worker contract, resource budgets, job failure policy, and the point at which the job workflow invokes validation and publication.

**Does not own:**
- Persisted records, legal state transitions, recovery, and explicit resume — ADR-0013. This ADR must not define a competing state machine.
- Safe split boundaries and reader/writer capabilities — ADR-0014. The Scheduler chooses among adapter-provided splits.
- Which identity fields and conditional reads each storage provider offers — ADR-0005.
- Runtime primitives that enforce the budgets — ADR-0007.
- Error categories and retry eligibility — ADR-0008.
- What validation means and proves — ADR-0006.
- The generic publication protocol and the Generic Publisher — ADR-0017.
- Table snapshot and native commit semantics — ADR-0015.
- Execution backend selection — ADR-0004.
- Telemetry instrumentation and cardinality rules — ADR-0010.
- Distributed coordination — ADR-0018.

## 20. Revisit conditions

Revisit this ADR when:
- benchmarks show the single-node design cannot meet target throughput despite tuning;
- the target user base requires remote workers or multi-node scale-out;
- a selected execution engine imposes a materially different scheduling or memory model;
- table-format operations require transaction-aware planning beyond the file-level model;
- measured source/destination constraints require new scheduling or cost policies.

## 21. References

- [Apache Parquet format](https://github.com/apache/parquet-format)
- [Arrow Rust RecordBatch memory-size API](https://arrow.apache.org/rust/arrow/record_batch/struct.RecordBatch.html)
- [Tokio bounded channels and backpressure](https://tokio.rs/tokio/tutorial/channels)
- [Amazon S3 multipart upload limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html)
- [Apache Iceberg specification](https://iceberg.apache.org/spec/)

## 22. Related ADRs

- [ADR-0004: Execution Engine Selection](ADR-0004-execution-engine-selection.md)
- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0006: Validation Semantics](ADR-0006-validation-semantics.md)
- [ADR-0007: Async Runtime and Concurrency Control](ADR-0007-async-runtime-and-concurrency.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0010: Observability and Telemetry](ADR-0010-observability.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0014: File Format Adapter Contract](ADR-0014-file-format-adapter-contract.md)
- [ADR-0015: Table Format Integration Boundary](ADR-0015-table-format-integration-boundary.md)
- [ADR-0017: Output Publication Protocol](ADR-0017-output-publication-protocol.md)
- [ADR-0018: Distributed Job State Store](ADR-0018-distributed-job-state-store.md)
