# ADR-0004: Execution Engine Selection

- **Status:** Proposed — Under Evaluation
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** Execution backend capabilities, selection criteria, and the proof of concept that decides them.

## 1. Context

UDC needs to read data in batches, optionally transform/project/filter it, and write it to another format or storage system. A query engine can provide scan planning, expression evaluation, optimization, and parallel execution. However, many conversion paths require only a streaming reader-to-writer pipeline and do not need SQL or a query optimizer.

Selecting a query engine as a mandatory core dependency before measuring this difference could add unnecessary complexity and constrain format coverage.

## 2. Decision drivers

1. Correctness and semantic fidelity across formats.
2. Bounded-memory streaming and backpressure.
3. Throughput and CPU efficiency for conversion-only workloads, compared with the reference configuration of PRD §13.3.
4. Projection/filter pushdown where the source supports it.
5. Coverage of the MVP formats: Parquet, CSV, and JSON. Avro, ORC, and Arrow IPC must remain addable later. Lance and Vortex are not selection criteria (§5.1).
6. Cloud object storage support and range-read behavior.
7. Ability to express optional transformations.
8. Startup time, binary size, dependency footprint, and build complexity.
9. Maintainability and API stability.
10. Avoiding mandatory SQL/query-engine semantics for simple conversions.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Native Arrow/format reader-writer pipeline** | Minimal layers; direct control over batches and writer behavior; naturally fits pure conversion | UDC must implement orchestration, concurrency, projection/filter behavior, and format-specific optimizations; library APIs differ |
| **Apache DataFusion** | Rust-native Arrow query engine; SQL/DataFrame APIs; optimizer and execution framework; extensible table providers | Adds query planning/runtime concepts when conversion may not need them; format and cloud support must be checked feature by feature; integration maintenance |
| **DuckDB** | Strong analytical SQL and broad practical file-format support; useful local execution model | Native Rust embedding/integration boundary and deployment behavior need evaluation; may be excessive for streaming pass-through conversion |
| **Apache Spark** | Mature distributed execution; broad ecosystem and table-format integrations | Heavy runtime and operational footprint; JVM boundary; unsuitable as the mandatory local MVP engine |

## 4. Proposed decision

Do **not** make a query engine mandatory in UDC Core at this stage.

The MVP baseline will retain a native streaming pipeline as the reference path. Evaluate Native Arrow, DataFusion, and DuckDB in a focused proof of concept. Keep Spark as a later distributed execution integration unless MVP requirements demonstrate a need for it.

No engine is selected as the universal execution backend by this ADR.

## 5. Rationale

The product's primary responsibility is reliable conversion and migration, not general-purpose SQL analytics. A path such as `reader -> Arrow RecordBatch stream -> writer` can satisfy a pure conversion without a query planner. An engine becomes valuable when UDC needs expressions, filter/projection pushdown, joins, or a richer optimizer. These needs should be measured rather than assumed.

### 5.1 Why Lance and Vortex are not selection criteria

An earlier version of this ADR listed coverage of Lance and Vortex among the drivers. A check of the ecosystem in November 2026 shows that they do not separate the candidates and do not belong to what UDC competes on.

- **Both engine candidates already reach both formats.** DuckDB reads and writes Vortex and Lance through core extensions: Vortex since January 2026, and Lance since DuckDB 1.5.1 in March 2026. Both projects also publish DataFusion integrations.
- **The native path reaches them as well.** Both formats are implemented in Rust and exchange Arrow data, so a UDC adapter can be built on the format's own library under ADR-0014, whichever backend is selected.
- **Conversion into them is already served.** Existing tools write either format in one statement, and the Lance library converts from Parquet directly. Adding them to UDC is coverage, which the PRD does not treat as differentiation ([PRD §2.5](../PRD.md#25-existing-tools-and-where-udc-fits)).
- **Maturity no longer argues for waiting on the engine.** Vortex declares its file format stable from release 0.36.0 and is an incubation-stage project of LF AI & Data. Lance states that a dataset written with a stable storage version stays readable by later releases.

Two points remain for the day an adapter is proposed. Existing engines handle Lance mainly as a dataset with table semantics, which falls under ADR-0015 and not under a file-format adapter. And the DuckDB Vortex extension is published for Linux and macOS only, so reaching Vortex through that extension would not cover the Windows target of ADR-0019; an adapter built on the Rust library is not bound by that.

Both formats therefore stay unscheduled in the PRD. They are decided by demand for the job layer on those formats, not by this ADR.

## 6. Trade-offs and consequences

- Maintaining a native path and optional engine integrations adds adapter work.
- Backend capability differences must be visible to users and in job plans.
- Some optimizations may be unavailable on the native path initially.
- Avoiding an early engine commitment delays finalization of parts of the execution API but reduces architectural lock-in.

## 7. Validation plan

The decision is validated by a focused proof of concept. Use the same input data, output format, hardware, and validation rules for each implementation.

### 7.1 Workloads

1. Parquet to Parquet rewrite with compression change.
2. Parquet to CSV.
3. CSV to Parquet.
4. Parquet projection of a subset of columns.
5. Parquet filter plus conversion, where applicable.
6. Remote object-store read/write after local baselines are stable.

### 7.2 Measure

- End-to-end throughput and CPU utilization.
- Peak resident memory and batch sizing behavior.
- Backpressure and bounded-memory behavior.
- Startup latency and binary/dependency footprint.
- Projection/filter pushdown actually performed.
- Correctness under nulls, decimals, timestamps, nested values, and schema evolution.
- Failure propagation, cancellation, and retry boundaries.
- Format support quality and maintenance cost, for the formats in driver 5.

### 7.3 Acceptance gates

- No backend may be accepted if it silently changes logical values.
- Streaming workloads must remain within a defined memory budget.
- Any throughput advantage must be evaluated alongside operational and dependency cost.
- The winner may be workload-specific; UDC must not force one backend where a simpler native path is superior.
- Results, benchmark fixtures, and versions must be committed for reproducibility.

### 7.4 Relation to the evidence gates

The comparison with existing tools in [PRD §2.5](../PRD.md#25-existing-tools-and-where-udc-fits) does not change this decision, but it changes what the proof of concept has to show. UDC's distinct part is the job layer (ADR-0012, ADR-0013, ADR-0017), and that layer does not depend on which backend moves the batches.

- The proof of concept also measures each candidate against the reference configuration of [PRD §13.3](../PRD.md#133-value-hypotheses-and-evidence-gates), which supplies the evidence for hypothesis H3.
- If the gates in PRD §13.3 lead to narrowing UDC to the job layer over an existing engine, that engine becomes the reference path and this ADR is revised before implementation continues.

## 8. Ownership boundary

**Owns:** what an execution backend must provide, which backends are candidates, and the evidence used to select them.

**Does not own:**
- Job planning, scheduling, and resource budgets — ADR-0012. A backend works within the budget it is given.
- Job and Attempt state — ADR-0013.
- Reader, writer, and split capabilities of a format — ADR-0014.
- The async runtime and its concurrency primitives — ADR-0007.
- Which coercions are permitted — ADR-0003. A backend performs only the coercions in the mapping plan.

## 9. Revisit conditions

Finalize this ADR after the POC and before introducing an execution engine as a mandatory dependency. Reopen it when a new format integration, workload, or engine release materially changes the trade-offs.

## 10. References

- [DuckDB: announcing Vortex support](https://duckdb.org/2026/01/23/duckdb-vortex-extension.html) and [Vortex extension](https://duckdb.org/docs/current/core_extensions/vortex)
- [DuckDB 1.5.1 announcement](https://duckdb.org/2026/03/23/announcing-duckdb-151) and [Lance extension](https://duckdb.org/docs/current/core_extensions/lance)
- [Vortex](https://github.com/vortex-data/vortex)
- [Lance](https://github.com/lance-format/lance) and [lance-datafusion](https://docs.rs/crate/lance-datafusion/latest)

## 11. Related ADRs

- [ADR-0003: Canonical Data Model and Schema Compatibility](ADR-0003-canonical-data-model.md)
- [ADR-0007: Async Runtime and Concurrency Control](ADR-0007-async-runtime-and-concurrency.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0014: File Format Adapter Contract](ADR-0014-file-format-adapter-contract.md)
- [ADR-0015: Table Format Integration Boundary](ADR-0015-table-format-integration-boundary.md)
- [ADR-0017: Output Publication Protocol](ADR-0017-output-publication-protocol.md)
- [ADR-0019: Packaging, Release, and Distribution](ADR-0019-packaging-and-distribution.md)
