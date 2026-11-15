# ADR-0006: Validation Semantics

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** Validation levels, the normalization rules and logical equality, where validation evidence is taken from, and the guarantee each validation result may claim.

## 1. Context

A successful write does not prove that a conversion preserved the source data. Physical byte equality is generally inappropriate across formats because encodings, compression, metadata, ordering, and file layout may differ. UDC therefore needs explicit validation levels and a definition of logical equality.

Checking a conversion is already possible without UDC: a user can run a count or aggregate query, or a separate comparison tool, after the conversion finishes ([PRD §2.5](../PRD.md#25-existing-tools-and-where-udc-fits)). What those approaches leave to the user is the definition of equality. Whether NaN equals NaN, whether `1.0` equals `1.00`, and whether two timestamps in different units are the same value are decided by whichever tool runs the comparison. The review behind PRD §2.5 did not find a tool that publishes those rules as a specification. A validation result is only as meaningful as the rules behind it, so UDC treats the rules themselves as part of the product.

## 2. Decision drivers

1. Detect missing, duplicated, or changed logical values.
2. Distinguish structural validation from content validation.
3. Handle nulls, NaNs, decimals, timestamps, nested values, and floating-point semantics explicitly.
4. Allow scalable validation without requiring a full row-by-row comparison in every job.
5. Make probabilistic checks distinguishable from exact checks.
6. Support reproducible results and clear failure reports.
7. Make the comparison rules public and versioned, so that a result can be reproduced and checked independently of UDC.
8. Provide value-level evidence inside the bounded-memory streaming model of ADR-0012, without sorting the dataset.

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

### 4.2 Normalization rules are a published, versioned specification

The **normalization rules** define the canonical form of a logical value and when two logical values are equal. L3, L4, and L5 all compare values under them.

- The rules are published with the user documentation, not kept as an implementation detail.
- Each release of the rules has a version identifier. A released version never changes; any change to a rule produces a new version.
- Each version is published with **conformance vectors**: input values, their canonical encoding, and the expected fingerprint. An independent implementation of the rules must be able to reproduce them.
- Where a rule allows a choice, the job's **normalization policy** records the choice. The policy is part of the Job (ADR-0012) and of every result (§4.5).

Version 1 covers the logical types reachable from the formats in the first release's support matrix. The proposed version 1 rules are:

| Topic | Rule | Policy option |
|---|---|---|
| Null | Null is distinct from every non-null value, including the empty string, zero, and NaN | None |
| Integer | Compared by mathematical value. Width and signedness are schema properties, checked at L1 | None |
| Floating point | Compared by exact represented value. A 32-bit value widened to 64 bits is equal to the original | None |
| NaN | All NaN bit patterns are one value. NaN is distinct from null | None |
| Signed zero | `-0.0` and `+0.0` are distinct | May be declared equal |
| Infinity | Positive and negative infinity are distinct values, each equal only to itself | None |
| Decimal | Compared by numeric value, so `1.0` and `1.00` are equal. Precision and scale are schema properties, checked at L1 | None |
| Timestamp | Timezone-aware values are compared as instants, independent of unit and of the zone label. Timezone-naive values are compared as wall-clock values, independent of unit. An aware value never equals a naive one | None |
| Date and time of day | Compared by value, independent of unit | None |
| String | Compared as the exact sequence of Unicode code points. No Unicode normalization, trimming, or case folding | None |
| Binary | Compared byte for byte | None |
| Struct | Compared field by field under the field identity of the mapping plan (ADR-0003). Field order is not significant | None |
| List | Element order and element count are significant | None |
| Map | Compared as an unordered set of key–value entries | None |
| Rows | A dataset is a multiset of rows: row order is not significant, and the number of times a row occurs is | None |

These rules are proposals. Each must be confirmed against the adversarial fixtures in §7 before version 1 is released.

A rule is not relaxed silently when a target format cannot satisfy it. The field mapping is instead classified under ADR-0003, and the coverage of the validation result is reduced as described in §4.3.

### 4.3 Where evidence is taken from

**Target side.** Evidence for L2 to L5 is taken from the staged output as stored: UDC reads back what it wrote. Counters held by the writer are not evidence, because they do not show that the stored bytes decode to those rows. A figure taken from the format metadata of the stored object, such as a Parquet footer row count, is allowed where the level permits it and is labelled as metadata (§4.5). Because of this rule, a format that UDC can write but cannot read back is not accepted as a job target (ADR-0014).

**Source side.** What the source-side evidence is computed from depends on the compatibility outcome of each field in the SchemaMappingPlan (ADR-0003):

| Field mapping outcome | Source-side evidence is computed from | A pass covers |
|---|---|---|
| Exact, Safe widening | Source logical values, before coercion | Read, coercion, write, and read-back |
| Lossy / narrowing or Policy-dependent, permitted by an explicit policy | The values after the coercion in the mapping plan | Write and read-back only. The coercion itself is not covered, and the result says so |

Mappings classified Unsupported or Unknown are rejected during planning and never reach validation.

**Text sources.** For formats that do not carry their own types, such as CSV and JSON, the source logical value is the value the reader produces under the declared or resolved schema. Validation does not cover the interpretation of text as a typed value. That interpretation is governed by the mapping plan (ADR-0003) and the adapter contract (ADR-0014).

**Text targets.** The same holds on the target side: read-back of a text target yields the value the reader produces under the target schema. A writer must therefore render each value so that it reads back to the same logical value. Where the format cannot represent a value at all, such as NaN in JSON, the mapping is classified under ADR-0003 and is never passed silently.

### 4.4 Requirements for the logical fingerprint (L4)

L4 is the value-level check that must run inside the streaming pipeline.

- A **row fingerprint** is a hash over the canonical encoding of the row's mapped fields under the normalization rules version in effect.
- Row fingerprints are combined into a dataset fingerprint by an order-independent combiner. No sort is needed, and memory use does not grow with the number of rows.
- The combiner must be sensitive to multiplicity: a dropped row and a duplicated row must each change the result. A combiner under which duplicate rows cancel out, such as XOR, is not acceptable.
- Fingerprints are computed per Work Unit and can be combined to partition and job scope without reading the data again.
- Per-column fingerprints are computed in addition, so that a mismatch can be narrowed to fields. They do not replace the row fingerprint, because per-column fingerprints alone do not detect values that moved between rows.
- The hash function, its width, and the combiner are selected during implementation and recorded as an algorithm identifier. The expected probability of an accidental collision is documented with them.
- L4 detects accidental divergence. It is not a security mechanism and does not resist data constructed deliberately to collide.
- On a mismatch, L4 reports the scope and the fields that differ. It does not identify the rows; that requires L5.

### 4.5 Evidence recorded for every result

Each validation result records:

- the level or check that ran, and its outcome;
- the scope it covers: a Work Unit, a partition, or the whole job;
- the algorithm identifier, the normalization rules version, and the normalization policy in effect;
- for each figure, whether it was computed from data or taken from format metadata;
- for each field, which coverage in §4.3 applies;
- a plain statement of what the result establishes.

### 4.6 Order in which levels are built

The levels are built in the order L1, L2, L4, and then L3 and L5.

- L1 and L2 alone can be obtained from existing tools. Value-level evidence under published rules is the part of validation that UDC adds, so it is not left until last.
- L4 and L5 both depend on the normalization rules. L4 comes first because it needs one bounded-memory pass over each side. L5 needs a declared ordering, or an external sort or a partitioned comparison.
- L3 depends on which statistics each format exposes and is the least comparable across formats.

Which levels a release commits to is defined in [PRD §8.2](../PRD.md#82-mvp-capability-matrix), not here.

## 5. Rationale

Different workloads need different cost/correctness trade-offs. Separating transfer integrity from logical equality avoids a category error: matching bytes are meaningful for copying the same object, but not for converting between different encodings. Named levels let users select an appropriate validation cost and understand what a successful check proves.

Publishing the normalization rules moves the definition of equality from the tool's internals to a document a user can read, cite, and test against. Taking target-side evidence from stored output, and stating coverage per field, keeps a result from claiming more than was checked.

## 6. Trade-offs and consequences

- Canonical value encoding and normalization must be specified and versioned.
- Published rules are a compatibility surface. Results produced under different rules versions are not comparable with each other.
- Floating-point NaN, signed zero, decimal scale, timestamp timezone, and nested-map ordering require explicit policy.
- A strict rule, such as distinct signed zeros, can fail a conversion into a format that cannot preserve the distinction. That surfaces as a mapping classification rather than as a silent pass.
- Reading staged output back adds a full read of the output: time, requests, and, for a remote destination, transferred bytes.
- The reader used for read-back may share a defect with the writer that produced the output, when both come from the same library.
- Statistics may be incomplete or incomparable across source formats.
- Hashes are evidence with defined collision properties, not mathematical proof of equality. An order-independent combiner gives weaker collision resistance than a hash over a sorted stream, which is why L4 claims detection of accidental divergence only.
- L4 cannot say which rows differ.
- Full comparison may require external sorting or partition-aware algorithms.

## 7. Validation plan

Create adversarial fixtures for nulls, NaNs, infinities, signed zero, decimals, timestamps, nested structs/lists/maps, duplicate rows, and schema evolution. Verify that each validation level reports exactly what it checks and does not overstate guarantees. Verify that a transfer-integrity result is never rendered as a validation level.

For L4 and the normalization rules:

- Inject faults into staged output and verify that L4 fails for each: one changed value, one dropped row, one duplicated row, and two values swapped between rows of the same column.
- Verify that L4 passes when only row order, file layout, compression, or physical encoding differs.
- Reproduce the conformance vectors with an implementation of the rules that shares no code with UDC.
- Measure the cost of L4 relative to the same conversion without validation, and confirm that its memory use does not grow with the number of rows.
- Verify that a result for a Lossy / narrowing or Policy-dependent field states that the coercion is not covered.

## 8. Ownership boundary

**Owns:** the validation level names (L1–L5), the normalization rules and their versioning, logical equality, where validation evidence is taken from, the transfer-integrity distinction, the order in which levels are built, and what each result is allowed to claim.

**Does not own:**
- Logical type semantics that normalization builds on, and the classification of a field mapping — ADR-0003.
- How a reader turns stored bytes or text into logical values — ADR-0014.
- When validation runs in the job workflow, and at which scope — ADR-0012.
- Recording validation results, and whether an Attempt is accepted because of them — ADR-0013.
- How a validation mismatch is classified and retried — ADR-0008. A mismatch at a selected level always prevents publication.
- Table-specific checks that are not validation levels, such as the registered file-set check — ADR-0015.
- Which validation levels a release commits to — the PRD.

## 9. Revisit conditions

Revisit when canonical schema and type semantics are stable, when a format added to the support matrix introduces a logical type that the current rules version does not cover, or when benchmark results show that a validation level is too expensive or insufficient for the intended workloads.

## 10. Related ADRs

- [ADR-0003: Canonical Data Model and Schema Compatibility](ADR-0003-canonical-data-model.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0014: File Format Adapter Contract](ADR-0014-file-format-adapter-contract.md)
- [ADR-0015: Table Format Integration Boundary](ADR-0015-table-format-integration-boundary.md)
