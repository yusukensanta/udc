# ADR-0014: File Format Adapter Contract

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** The FileFormatAdapter contract: the capability descriptor, inspection, safe split planning, and streaming reader and writer behavior.

## 1. Context

UDC supports heterogeneous file representations including row-oriented serialization, columnar formats, and interchange formats. Their safe parallelization boundaries differ. Parquet exposes row-group metadata; Avro container files are block-oriented; CSV may require scanning or an external index to split safely; JSON and JSONL have different framing properties; Lance and Vortex have their own layout and reader capabilities.

A generic adapter API that assumes every format can read arbitrary byte ranges or split into independent files would be incorrect. At the same time, exposing each library's concrete reader/writer types throughout the scheduler would couple orchestration to specific implementations.

## 2. Decision drivers

1. Preserve format-specific semantics and correctness.
2. Expose safe independent read boundaries instead of inventing universal splits.
3. Support streaming and bounded memory.
4. Keep format code independent of global job state and retry policy.
5. Allow optional capabilities such as projection, predicate pushdown, range reads, and metadata-only inspection.
6. Keep adapters testable without cloud credentials or a specific execution engine.
7. Avoid forcing a lowest-common-denominator interface that blocks advanced format capabilities.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **One universal reader/writer trait** | Simple mental model and common call sites | Format differences become hidden flags; unsafe assumptions about splitting and metadata; trait grows excessively |
| **Capability-oriented adapter contracts** | Common lifecycle with explicit optional capabilities; scheduler can plan around actual support | More types and capability negotiation; needs clear contract versioning |
| **Expose underlying library types directly** | Maximum library feature access; minimal wrapping | Leaks dependencies across crates; hard to replace libraries; scheduler becomes format-specific |
| **Pairwise converter plugins** | Can optimize particular source-target pairs | N×M implementation growth; duplicated schema and validation logic |

## 4. Proposed decision

Adopt a **capability-oriented FileFormatAdapter contract** with separate inspection, split planning, streaming read, and streaming write responsibilities. Use Apache Arrow RecordBatch as the initial execution interchange where the selected format library supports it; do not require all format libraries to expose Arrow natively.

A format adapter must expose an explicit capability descriptor. Unsupported capabilities must be reported rather than simulated or silently ignored.

## 5. Rationale

A single universal trait hides the differences that decide correctness: where a format can be split, what metadata is available without a scan, and which types it can represent. Exposing the library types would give access to every feature but would bind the scheduler and every other crate to particular libraries. Pairwise converters grow with the product of the formats and would repeat schema mapping and validation in each pair, although UDC's value depends on those being applied uniformly (ADR-0003, ADR-0006).

A capability descriptor turns each difference into an explicit, testable statement that the Planner can act on. A format without safe splits is planned as one Work Unit per file instead of being split incorrectly. Arrow RecordBatch as the interchange gives every source and target pair through one adapter per format, and lets readers and writers be tested independently of each other.

## 6. Contract boundaries

### 6.1 FormatDescriptor / Capabilities

Expose immutable metadata such as:
- format identifier and adapter version;
- supported read/write operations;
- read-back support: whether the adapter can read everything its writer can produce;
- supported logical and physical types;
- metadata-only inspection support;
- safe split discovery and split independence;
- sequential/streaming read support;
- range-read requirements;
- projection/predicate pushdown support;
- per-reader and per-writer concurrency constraints;
- compression and encoding options;
- format-specific limitations and feature flags.

Capabilities describe what the adapter can guarantee, not what the underlying format specification theoretically permits.

### 6.2 Inspection

Inspection returns physical schema, format metadata, row/record count and size estimates where available, split metadata, and provenance. Inspection must distinguish exact values from estimates and unknown values. It should avoid scanning all records when footer/header metadata is sufficient.

### 6.3 Split planning

The adapter receives source identity and planning constraints, then returns opaque but serializable SplitDescriptors. Each descriptor contains:
- stable format-specific split identity;
- exact source object/version reference;
- safe logical boundary (file, block, row group, or other native unit);
- estimated bytes/rows if known;
- required reader options and versioned adapter interpretation;
- whether the split is independently readable and retryable.

The adapter must never claim independent splitting when it cannot guarantee decoding correctness. Arbitrary compressed byte offsets are not valid split boundaries by default.

UDC's Work Unit wraps a SplitDescriptor with job-level output ownership, validation policy, and resource class. The adapter does not allocate global Work Unit IDs or assign workers.

### 6.4 Streaming reader

Reader contract requirements:
- bounded output batches;
- cancellation and early close;
- explicit schema and projection behavior;
- errors preserve source identity and format context;
- no requirement to materialize an entire file or dataset;
- report progress/bytes where the underlying reader can do so.

Readers do not decide global retry, checkpoint acceptance, or job state. A failed split is retried by orchestration according to ADR-0008 and ADR-0013.

### 6.5 Streaming writer

Writer contract requirements:
- write to an attempt-owned staging destination;
- bounded buffering and explicit flush/close semantics;
- deterministic output metadata/options where possible;
- report output bytes/rows/files and format metadata;
- never publish the job destination;
- surface whether writer close means bytes are durably accepted by the Storage adapter or only flushed to an intermediate buffer.

Final visibility is owned by the Generic Publisher under ADR-0017, or by the table-native commit under ADR-0015 when the destination is a table.

**Read-back is required of a target format.** Validation takes its target-side evidence by reading the staged output back (ADR-0006). A format is therefore accepted as the target of a job only if the adapter can also read what it writes, through a reader that meets §6.4. An adapter that can write a format but cannot read it back reports this in its descriptor, and the Planner rejects a job that selects the format as a target with a Compatibility error (ADR-0008). No mode skips target-side validation for such a format. An adapter that can read a format but not write it is unaffected: the format can be a source.

### 6.6 Schema mapping boundary

Adapters map physical schemas to/from the canonical logical schema defined in ADR-0003. They must preserve format-specific metadata where required and classify unknown/unsupported annotations. They do not independently invent cross-format coercion policy.

## 7. Error and resource contract

- Return typed errors that map to the categories of ADR-0008: Data (corrupt input), Compatibility (unsupported feature, schema mismatch), Configuration (invalid options), Transient (transient I/O failure), and Resource (resource exhaustion).
- Include safe source/split context without leaking credentials or signed URLs.
- Allow scheduler-provided resource limits for read concurrency, batch size/bytes, and writer buffering.
- CPU-intensive decode/encode work must follow ADR-0007 execution constraints.
- Adapter errors are classified for retry by ADR-0008; adapters do not retry indefinitely.

## 8. Compatibility and versioning

SplitDescriptors must include an adapter/descriptor version. A stored plan must not be reinterpreted by a newer adapter version unless compatibility is explicitly declared. If the required reader capability is unavailable during resume, the job must fail with a clear compatibility error or require a new plan.

Public adapter contracts should be narrow and stable. Internal library wrappers may evolve independently behind the contract.

## 9. Trade-offs and consequences

- Capability negotiation adds types and planning logic, and every optional capability multiplies the test cases.
- Values pass through Arrow's type system. A format whose types do not map directly needs an explicit mapping under ADR-0003, and a library that is not Arrow-native pays a conversion cost.
- Optimizations for one pair of formats, such as copying Parquet row groups without decoding them, are not available through the generic path.
- A narrow, stable contract will sometimes not expose a library feature. Adding it is a contract change by design.
- Stored plans pin descriptor versions. An adapter upgrade can make an old plan impossible to resume instead of reinterpreting it (§8).
- The read-back requirement excludes a write-only format as a job target.

## 10. Validation plan

Every adapter must provide:
- format conformance fixtures and malformed/corrupt input tests;
- logical schema round-trip tests against ADR-0003;
- read-back tests proving that the reader reads everything the writer can produce, with every supported writer option, to the same logical values;
- cancellation and bounded-memory tests;
- split coverage tests proving no missing or overlapping records;
- deterministic output and writer-finalization tests;
- compatibility matrix by adapter/library version;
- integration tests using fake/local Storage and real object storage where relevant.

## 11. Ownership boundary

**Owns:** the adapter contract, the capability descriptor, SplitDescriptors and their versioning, and the obligations of streaming readers and writers.

**Does not own:**
- Work Unit identity, scheduling, and resource-budget values — ADR-0012.
- Attempt state, acceptance, and checkpoints — ADR-0013.
- Error categories and retry eligibility — ADR-0008.
- Logical type semantics and cross-format coercion policy — ADR-0003.
- Object I/O — ADR-0005.
- Final visibility of written output — ADR-0017.
- What target-side validation evidence is and why it needs read-back — ADR-0006.
- Table-level semantics above data files — ADR-0015.
- CPU and blocking-work execution constraints — ADR-0007.

## 12. Revisit conditions

Revisit when a new format exposes capabilities that cannot fit the current contract without format-specific extensions, or when Arrow is not a viable interchange for a supported format. Do not add a universal feature merely because one format supports it.

## 13. References

- [Apache Arrow columnar format](https://arrow.apache.org/docs/format/Columnar.html)
- [arrow crate: RecordBatch](https://docs.rs/arrow/latest/arrow/record_batch/struct.RecordBatch.html)

## 14. Related ADRs

- [ADR-0003: Canonical Data Model and Schema Compatibility](ADR-0003-canonical-data-model.md)
- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0006: Validation Semantics](ADR-0006-validation-semantics.md)
- [ADR-0007: Async Runtime and Concurrency Control](ADR-0007-async-runtime-and-concurrency.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0015: Table Format Integration Boundary](ADR-0015-table-format-integration-boundary.md)
- [ADR-0017: Output Publication Protocol](ADR-0017-output-publication-protocol.md)
