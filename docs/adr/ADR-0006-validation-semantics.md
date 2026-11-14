# ADR-0006: Validation Semantics

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers

## Context

A successful write does not prove that a conversion preserved the source data. Physical byte equality is generally inappropriate across formats because encodings, compression, metadata, ordering, and file layout may differ. UDC therefore needs explicit validation levels and a definition of logical equality.

## Decision drivers

1. Detect missing, duplicated, or changed logical values.
2. Distinguish structural validation from content validation.
3. Handle nulls, NaNs, decimals, timestamps, nested values, and floating-point semantics explicitly.
4. Allow scalable validation without requiring a full row-by-row comparison in every job.
5. Make probabilistic checks distinguishable from exact checks.
6. Support reproducible results and clear failure reports.

## Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Metadata-only checks (schema, file count, row count)** | Cheap and scalable | Cannot detect value corruption when counts remain equal |
| **Physical file/object checksums** | Detect byte changes and transfer corruption | Different encodings produce different bytes even when logical data is equal; does not prove semantic equivalence |
| **Canonical logical hashing** | Can compare values across physical formats after normalization | Requires carefully specified canonical encoding; hash collisions are theoretically possible; expensive |
| **Exact logical row comparison** | Strongest direct equivalence check | High I/O and CPU cost; ordering and duplicate semantics must be defined |

## Proposed decision

Define validation as explicit levels rather than a single boolean:
- **Structural:** schema and metadata compatibility.
- **Cardinality:** row counts and optional per-partition counts.
- **Statistics:** null counts, min/max, distinct estimates where available, with source provenance.
- **Logical fingerprint:** canonicalized per-column or per-row hashes.
- **Exact comparison:** logical row comparison under a declared ordering or multiset policy.

Physical checksums may be used for transfer-integrity checks but must not be presented as proof of logical equivalence.

## Rationale

Different workloads need different cost/correctness trade-offs. Separating transfer integrity from logical equality avoids a category error: matching bytes are meaningful for copying the same object, but not for converting between different encodings. Named levels let users select an appropriate validation cost and understand what a successful check proves.

## Trade-offs and consequences

- Canonical value encoding and normalization must be specified and versioned.
- Floating-point NaN, signed zero, decimal scale, timestamp timezone, and nested-map ordering require explicit policy.
- Statistics may be incomplete or incomparable across source formats.
- Hashes are evidence with defined collision properties, not mathematical proof of equality.
- Full comparison may require external sorting or partition-aware algorithms.

## Validation plan

Create adversarial fixtures for nulls, NaNs, infinities, signed zero, decimals, timestamps, nested structs/lists/maps, duplicate rows, and schema evolution. Verify that each validation level reports exactly what it checks and does not overstate guarantees.

## Revisit conditions

Revisit when canonical schema and type semantics are stable, or when benchmark results show that a validation level is too expensive or insufficient for the intended workloads.
