# ADR-0004: Execution Engine Selection

- **Status:** Proposed — Under Evaluation
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers

## Context

UDC needs to read data in batches, optionally transform/project/filter it, and write it to another format or storage system. A query engine can provide scan planning, expression evaluation, optimization, and parallel execution. However, many conversion paths require only a streaming reader-to-writer pipeline and do not need SQL or a query optimizer.

Selecting a query engine as a mandatory core dependency before measuring this difference could add unnecessary complexity and constrain format coverage.

## Decision drivers

1. Correctness and semantic fidelity across formats.
2. Bounded-memory streaming and backpressure.
3. Throughput and CPU efficiency for conversion-only workloads.
4. Projection/filter pushdown where the source supports it.
5. Coverage of required formats, including Parquet, CSV, JSON, Avro, ORC, Arrow IPC, Lance, and Vortex as they mature.
6. Cloud object storage support and range-read behavior.
7. Ability to express optional transformations.
8. Startup time, binary size, dependency footprint, and build complexity.
9. Maintainability and API stability.
10. Avoiding mandatory SQL/query-engine semantics for simple conversions.

## Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Native Arrow/format reader-writer pipeline** | Minimal layers; direct control over batches and writer behavior; naturally fits pure conversion | UDC must implement orchestration, concurrency, projection/filter behavior, and format-specific optimizations; library APIs differ |
| **Apache DataFusion** | Rust-native Arrow query engine; SQL/DataFrame APIs; optimizer and execution framework; extensible table providers | Adds query planning/runtime concepts when conversion may not need them; format and cloud support must be checked feature by feature; integration maintenance |
| **DuckDB** | Strong analytical SQL and broad practical file-format support; useful local execution model | Native Rust embedding/integration boundary and deployment behavior need evaluation; may be excessive for streaming pass-through conversion |
| **Apache Spark** | Mature distributed execution; broad ecosystem and table-format integrations | Heavy runtime and operational footprint; JVM boundary; unsuitable as the mandatory local MVP engine |

## Proposed decision

Do **not** make a query engine mandatory in UDC Core at this stage.

The MVP baseline will retain a native streaming pipeline as the reference path. Evaluate Native Arrow, DataFusion, and DuckDB in a focused proof of concept. Keep Spark as a later distributed execution integration unless MVP requirements demonstrate a need for it.

No engine is selected as the universal execution backend by this ADR.

## Rationale

The product's primary responsibility is reliable conversion and migration, not general-purpose SQL analytics. A path such as `reader -> Arrow RecordBatch stream -> writer` can satisfy a pure conversion without a query planner. An engine becomes valuable when UDC needs expressions, filter/projection pushdown, joins, or a richer optimizer. These needs should be measured rather than assumed.

## Proof-of-concept plan

Use the same input data, output format, hardware, and validation rules for each implementation.

### Workloads

1. Parquet to Parquet rewrite with compression change.
2. Parquet to CSV.
3. CSV to Parquet.
4. Parquet projection of a subset of columns.
5. Parquet filter plus conversion, where applicable.
6. Remote object-store read/write after local baselines are stable.

### Measure

- End-to-end throughput and CPU utilization.
- Peak resident memory and batch sizing behavior.
- Backpressure and bounded-memory behavior.
- Startup latency and binary/dependency footprint.
- Projection/filter pushdown actually performed.
- Correctness under nulls, decimals, timestamps, nested values, and schema evolution.
- Failure propagation, cancellation, and retry boundaries.
- Format support quality and maintenance cost.

### Acceptance gates

- No backend may be accepted if it silently changes logical values.
- Streaming workloads must remain within a defined memory budget.
- Any throughput advantage must be evaluated alongside operational and dependency cost.
- The winner may be workload-specific; UDC must not force one backend where a simpler native path is superior.
- Results, benchmark fixtures, and versions must be committed for reproducibility.

## Trade-offs and consequences

- Maintaining a native path and optional engine integrations adds adapter work.
- Backend capability differences must be visible to users and in job plans.
- Some optimizations may be unavailable on the native path initially.
- Avoiding an early engine commitment delays finalization of parts of the execution API but reduces architectural lock-in.

## Revisit conditions

Finalize this ADR after the POC and before introducing an execution engine as a mandatory dependency. Reopen it when a new format integration, workload, or engine release materially changes the trade-offs.
