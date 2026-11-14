# ADR-0012: Scalable Data Processing Architecture

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers

## Context

UDC's value depends on processing datasets much larger than the memory or local disk of a single process. Scale has several independent dimensions: total bytes, object/file count, per-file size, partition count, schema complexity, remote request rate, and destination throughput. Optimizing only throughput on one large file is insufficient.

UDC should scale from a laptop to a high-resource single node and, later, to distributed execution without embedding a distributed control plane in the first MVP. The architecture must make work units independently schedulable and resource-bounded.

## Decision drivers

1. Process data larger than available RAM and avoid whole-dataset materialization.
2. Scale throughput with available CPU, network, and storage capacity while respecting provider limits.
3. Bound memory and concurrency under skew, slow sinks, and retries.
4. Recover from process failure without restarting completed work unnecessarily.
5. Handle both many-small-files and few-large-files workloads.
6. Keep single-node local execution useful and simple.
7. Provide a path to distributed execution without assuming shared local disk.
8. Maintain deterministic output publication and validation.

## Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Sequential whole-dataset processing** | Simple and predictable | Low throughput; may fail on datasets larger than memory/disk; no work-level recovery |
| **Single-node bounded streaming with parallel work units** | Efficient local execution; bounded memory; simple deployment; natural baseline for CLI | Limited by one host's CPU, network, and failure domain |
| **Distributed workers from the beginning** | Horizontal scale across hosts; potentially high aggregate throughput | Requires coordinator, durable work queue, worker protocol, leases, distributed failure handling, and operational platform before product-market fit |
| **Engine-owned distributed execution (e.g. Spark)** | Mature distributed scheduler and ecosystem | Runtime dependency, integration complexity, and execution semantics owned by external engine |

## Proposed decision

Adopt **bounded streaming with partitionable work units** as the core execution model. The initial runtime is single-node, but its job plan and work-unit model must not assume that all work is executed by one process. Defer a built-in distributed coordinator until single-node limits and real user requirements justify it. Evaluate Spark or another distributed backend as an integration rather than baking distributed scheduling into core.

## Architectural model

### 1. Plan before execution

Discover source metadata and produce a deterministic plan before writing output. The plan records source identity/version where available, schema mapping, partition/file work units, destination layout, resource limits, validation policy, and publication strategy. For very large object listings, discovery itself must support pagination and incremental persistence rather than materializing every object in memory.

### 2. Choose the smallest safe independent work unit

Work-unit granularity is adapter-dependent: object/file, row group, partition, or byte range where format and storage semantics permit it. Avoid splitting compressed streams at arbitrary byte offsets unless the format supports safe independent seeking. Work units must have stable IDs and deterministic output ownership.

### 3. Bounded streaming pipeline

Each work unit flows through bounded stages: source read → decode → optional transform → encode → staged write → validation. Use bounded channels and byte-aware admission control. When a sink slows down, upstream stages must stop producing data instead of accumulating unbounded batches.

### 4. Resource budgets

Define independent budgets for:
- total in-flight memory bytes;
- batch size / batch bytes;
- concurrent source reads;
- concurrent CPU decode/encode tasks;
- concurrent destination writes and multipart parts;
- open files/sockets;
- per-provider request rate and retry budget;
- temporary disk/spill usage.

Do not use only a fixed number of RecordBatches as a memory limit because batches can vary significantly in byte size. Admission control should account for estimated or measured bytes and reserve headroom for decoder/writer allocations.

### 5. Parallelism and skew

Parallelize independent work units while bounding concurrency. Use adaptive scheduling only after collecting reliable size/throughput estimates. Avoid a single global FIFO queue becoming a bottleneck. Support smaller units or row-group-level parallelism for large files only when readers/writers and data semantics permit it. Track skew and stragglers separately from aggregate throughput.

### 6. Checkpoint and retry

Persist work-unit state and attempt metadata in a durable job manifest when resumability is enabled. A retry writes to an attempt-specific staging location or deterministic idempotent key; it must not overwrite a completed/published output silently. Acknowledge a unit only after write completion and required validation. Process crash recovery must reconcile in-progress multipart uploads and abandoned staging artifacts.

### 7. Small-file and large-file strategies

- Many small files: batch listing and metadata operations; bounded open-file concurrency; optionally compact outputs to target file sizes.
- Few large files: use row-group/range parallelism where safe; stream sequentially when the format lacks independent split boundaries.
- Output sizing: target file size should be configurable and based on downstream access pattern, not a universal constant.
- Partitioning: do not create excessive tiny files or high-cardinality partition layouts by default.

### 8. Scale-out boundary

Define a serializable job plan and work-unit contract that can later be dispatched to remote workers. Worker execution must be stateless with respect to process memory; durable state belongs in the job manifest/state store. Do not require distributed execution in the MVP, but avoid APIs that pass in-memory closures or local-only paths as the sole representation of work.

## Rationale

Bounded streaming controls memory independently of dataset size. Work-unit partitioning exposes safe parallelism and isolates retries. A single-node runtime keeps the MVP operable without a control plane, while serializable plans and durable work-unit state preserve a route to remote workers. Separating the many-small-files and few-large-files cases avoids optimizing one workload shape at the expense of the other.

## Trade-offs and consequences

- Planning and checkpointing introduce metadata and state-management complexity.
- Work-unit granularity differs by format; not every format supports safe intra-file parallelism.
- Byte-aware memory accounting is approximate because libraries may allocate internally or retain buffers.
- Exactly-once end-to-end effects are not assumed; the design should provide at-least-once work execution with idempotent/staged outputs and atomic publication boundaries.
- Distributed execution will require lease expiry, duplicate-worker protection, state-store consistency, and worker compatibility/versioning.

## Validation plan

Benchmark and fault-test at least:
1. Many tiny files (high object count).
2. Few very large Parquet files (multi-TB aggregate).
3. Highly skewed file sizes and partition sizes.
4. Slow destination / throttled source.
5. Process termination during read, encode, multipart upload, validation, and publication.
6. Memory pressure and disk-full conditions.

Measure throughput, peak RSS, in-flight bytes, task count, open descriptors, requests/sec, retries, queue wait, output file count/size distribution, and recovery time. Verify memory remains within configured bounds as total input size grows.

## Revisit conditions

Revisit when a single-node benchmark shows a sustained bottleneck that cannot be addressed by tuning or optional external distributed execution, or when users require multi-host execution as a core product capability.

## Related ADRs

- [ADR-0004: Execution Engine Selection](ADR-0004-execution-engine-selection.md)
- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0006: Validation Semantics](ADR-0006-validation-semantics.md)
- [ADR-0007: Async Runtime and Concurrency Control](ADR-0007-async-runtime-and-concurrency.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0010: Observability and Telemetry](ADR-0010-observability.md)
