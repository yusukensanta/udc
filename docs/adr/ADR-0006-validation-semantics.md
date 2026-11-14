# ADR-0006: Validation Semantics

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** Validation levels, normalization, logical equality, and the guarantee each validation result may claim.

## 1. Context

A successful write does not prove that a conversion preserved the source data. Physical byte equality is generally inappropriate across formats because encodings, compression, metadata, ordering, and file layout may differ. UDC therefore needs explicit validation levels and a definition of logical equality.

## 2. Decision drivers

1. Detect missing, duplicated, or changed logical values.
2. Distinguish structural validation from content validation.
3. Handle nulls, NaNs, decimals, timestamps, nested values, and floating-point semantics explicitly.
4. Allow scalable validation without requiring a full row-by-row comparison in every job.
5. Make probabilistic checks distinguishable from exact checks.
6. Support reproducible results and clear failure reports.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Metadata-only checks (schema, file count, row count)** | Cheap and scalable | Cannot detect value corruption when counts remain equal |
| **Physical file/object checksums** | Detect byte changes and transfer corruption | Different encodings produce different bytes even when logical data is equal; does not prove semantic equivalence |
| **Canonical logical hashing** | Can compare values across physical formats after normalization | Requires carefully specified canonical encoding; hash collisions are theoretically possible; expensive |
| **Exact logical row comparison** | Strongest direct equivalence check | High I/O and CPU cost; ordering and duplicate semantics must be defined |

## 4. Proposed decision

Define validation as named levels rather than a single boolean. These names and identifiers are the only ones used across UDC documents, configuration, and reports.

| Level | Name | What it checks | What a pass establishes | What it does not establish |
|---|---|---|---|---|
| L1 | Structural | Schema and metadata compatibility under the selected mapping policy | The declared structure satisfies the mapping plan | Anything about values |
| L2 | Cardinality | Row or record counts, optionally per partition | Counts agree | That values agree |
| L3 | Statistics | Null counts, min/max, and distinct estimates where available, with the provenance of each figure | The selected aggregates agree under the defined normalization | Row-level equality |
| L4 | Logical fingerprint | Canonicalized per-column or per-row hashes of logical values | Fingerprints agree under a versioned canonical encoding, with stated collision properties | Mathematical proof of equality; byte equality |
| L5 | Exact comparison | Logical row comparison under a declared ordering or multiset policy | Logical records agree under the declared equality and normalization policy | Physical or layout equality |

A job selects which levels to run. Each result reports the levels that actually ran; a pass at one level does not imply that another level ran.

### 4.1 Transfer integrity is not a validation level

A physical checksum or ETag comparison is a **transfer-integrity check**. It establishes that the bytes UDC stored or copied are the bytes it intended to store or copy. It is meaningful for an unchanged object copy and for confirming that an upload was stored intact.

It is reported separately from L1–L5. It must not be reported as L4, and it must not be presented as evidence of logical equivalence: two files with different encodings have different bytes even when their logical data is equal.

### 4.2 Evidence recorded for every result

Each validation result records:

- the level or check that ran, and its outcome;
- the scope it covers: a Work Unit, a partition, or the whole job;
- the algorithm and the version of the normalization rules used;
- for each figure, whether it was computed from data or taken from format metadata;
- a plain statement of what the result establishes.

## 5. Rationale

Different workloads need different cost/correctness trade-offs. Separating transfer integrity from logical equality avoids a category error: matching bytes are meaningful for copying the same object, but not for converting between different encodings. Named levels let users select an appropriate validation cost and understand what a successful check proves.

## 6. Trade-offs and consequences

- Canonical value encoding and normalization must be specified and versioned.
- Floating-point NaN, signed zero, decimal scale, timestamp timezone, and nested-map ordering require explicit policy.
- Statistics may be incomplete or incomparable across source formats.
- Hashes are evidence with defined collision properties, not mathematical proof of equality.
- Full comparison may require external sorting or partition-aware algorithms.

## 7. Validation plan

Create adversarial fixtures for nulls, NaNs, infinities, signed zero, decimals, timestamps, nested structs/lists/maps, duplicate rows, and schema evolution. Verify that each validation level reports exactly what it checks and does not overstate guarantees. Verify that a transfer-integrity result is never rendered as a validation level.

## 8. Ownership boundary

**Owns:** the validation level names (L1–L5), normalization and logical equality rules, the transfer-integrity distinction, and what each result is allowed to claim.

**Does not own:**
- Logical type semantics that normalization builds on — ADR-0003.
- When validation runs in the job workflow, and at which scope — ADR-0012.
- Recording validation results, and whether an Attempt is accepted because of them — ADR-0013.
- How a validation failure is classified for retry — ADR-0008.

## 9. Revisit conditions

Revisit when canonical schema and type semantics are stable, or when benchmark results show that a validation level is too expensive or insufficient for the intended workloads.

## 10. Related ADRs

- [ADR-0003: Canonical Data Model and Schema Compatibility](ADR-0003-canonical-data-model.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
