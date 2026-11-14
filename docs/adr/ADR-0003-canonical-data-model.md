# ADR-0003: Canonical Data Model and Schema Compatibility

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers

## Context

A conversion tool must distinguish at least three representations: logical meaning, physical representation, and execution representation. Logical meaning includes decimal precision/scale, timestamp meaning, nullability, and nested structure. Physical representation includes format-specific primitive types, encodings, annotations, and metadata. Execution representation is how an engine stores values in memory, such as Arrow arrays and RecordBatches.

These representations overlap but are not interchangeable. Treating Arrow's schema as the complete canonical contract risks losing source-specific annotations and conversion policy. Treating each format pair independently creates an unmaintainable N×M mapping problem.

## Decision drivers

1. Preserve logical type semantics across format boundaries.
2. Represent unsupported and lossy conversions explicitly.
3. Avoid an N×M set of pair-specific converters.
4. Interoperate efficiently with Arrow-based readers, writers, and engines.
5. Retain source/target-specific physical metadata when needed.
6. Keep the model small enough to implement and evolve.

## Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Arrow Schema as the sole canonical model** | Directly interoperable with Arrow libraries; less model code; convenient execution boundary | Does not necessarily express every format-specific semantic, policy, or provenance requirement; metadata conventions can become implicit |
| **Custom canonical logical model plus Arrow execution representation** | Explicit semantics and conversion policy; decouples domain contract from engine; supports multiple physical formats | Requires mappings, validation, and model evolution; risk of duplicating Arrow concepts |
| **Pairwise source-to-target mappings** | Can preserve special cases for a specific pair | Complexity grows with format combinations; semantics become inconsistent; poor extensibility |

## Proposed decision

Adopt a **separate canonical logical schema model**, while using Apache Arrow as the primary execution interchange representation.

Keep physical schema descriptors and format-specific metadata at adapter boundaries. The canonical model should represent only semantics UDC needs to reason about; it must not become a second general-purpose in-memory data engine.

## Rationale

The canonical model is responsible for deciding whether a source timestamp can be represented by a target timestamp without loss, whether decimal precision/scale changes are safe, and whether nullability constraints are compatible. Arrow remains responsible for efficient in-memory batches and ecosystem interoperability. Keeping these responsibilities separate avoids forcing logical policy into engine-specific metadata or format-specific physical types.

## Trade-offs and consequences

- Every format adapter needs explicit mappings to/from the canonical model.
- The model must distinguish unknown, unsupported, and intentionally ignored metadata.
- Schema evolution and compatibility rules need versioned tests.
- The model must avoid duplicating arrays, buffers, compute kernels, or execution functionality already supplied by Arrow.
- Exact logical equality requires normalization rules coordinated with the validation ADR.

## Validation plan

Build a schema compatibility matrix covering signed/unsigned integer widths; decimal precision and scale; timestamp unit and timezone semantics; date/time types; UTF-8 and binary; nullability; nested struct/list/map types; field identity and metadata; unknown or format-specific annotations.

For every mapping, classify it as exact, widening, narrowing/lossy, unsupported, or policy-dependent. Test round-trips and cross-format conversion independently of a particular query engine.

## Revisit conditions

Revisit if practical format coverage shows that Arrow Schema plus a small, well-defined metadata contract can represent all required semantics without a separate domain model, or if the proposed model creates unacceptable duplication and maintenance burden.

## 10. Schema compatibility decision model

Schema mapping is not a name-based cast operation. UDC must evaluate compatibility between source and target schemas using the canonical logical model before starting expensive data movement.

### 10.1 Compatibility outcomes

Each field mapping must resolve to one of these outcomes:

| Outcome | Meaning | Default behavior |
|---|---|---|
| Exact | Same logical meaning and representable values | Allow |
| Safe widening | Target can represent every source value under the declared semantics | Allow when mapping is explicit or unambiguous |
| Lossy / narrowing | Some values or precision may be lost | Reject unless the user explicitly selects a loss policy |
| Unsupported | No valid mapping is implemented | Reject |
| Policy-dependent | Compatibility depends on timezone, rounding, overflow, null, or normalization policy | Require explicit policy |
| Unknown | Source metadata is insufficient to determine semantics | Do not silently assume; require override or reject |

### 10.2 Field identity and name resolution

Resolve fields using stable field IDs where the source format/table format provides them. Otherwise use an explicit configurable resolution policy: exact name matching by default, with case sensitivity documented. Renames must be represented as explicit mappings unless stable IDs prove continuity. Duplicate names and ambiguous matches must fail planning.

Field order is not field identity. Writers may reorder fields only according to an explicit target schema; implicit positional mapping is prohibited for nested or evolved schemas.

### 10.3 Numeric semantics

- Integer widening is safe only when signedness and target range contain the entire source range.
- Signed/unsigned conversion must not be assumed safe from width alone.
- Decimal mapping must compare precision and scale mathematically; increasing scale can require increasing precision to preserve integer digits.
- Narrowing, rounding, truncation, and overflow behavior require explicit policy.
- Floating-point conversion must document IEEE representation, NaN, infinities, and signed-zero behavior where the source/target differ.

### 10.4 Temporal semantics

- Timestamp unit conversion must detect precision loss.
- Timezone-aware and timezone-naive timestamps are distinct logical types.
- UTC normalization must be explicit; a local timestamp must not be silently interpreted as UTC.
- Date/time types and calendar semantics must be modeled independently of physical integer encodings.

### 10.5 Nullability and nested values

- A nullable source cannot map to a required target without an explicit null-handling policy and proof/check that nulls are absent.
- A required source can map to a nullable target, but the target schema must reflect the widened nullability.
- Struct field identity, list element nullability, map key constraints, and nested evolution must be checked recursively.
- Unsupported nested conversions fail during planning, not midway through a large job.

### 10.6 Metadata and provenance

Preserve field IDs, logical annotations, and application metadata when the target format has a compatible representation. Classify metadata as semantic, operational, or informational. Unknown metadata must be preserved opaquely when safe or reported as dropped; silent loss is prohibited when it may affect interpretation.

### 10.7 Planning contract

The schema compatibility evaluator produces a versioned SchemaMappingPlan containing source/target logical schemas, field mapping, coercion operations, policy decisions, warnings, and a deterministic digest. The Plan is immutable once execution begins. Format adapters translate physical schemas to/from the canonical logical model; execution backends perform only the explicit coercion operations in the mapping plan.

## 11. Validation plan for compatibility

Maintain property-based and golden test matrices for boundary values: integer min/max, decimal precision/scale edges, timestamps around timezone/DST boundaries, null-bearing nested arrays/maps, NaN/infinity/signed zero, field renames/IDs, duplicate names, unknown metadata, and round-trip conversions.

Tests must prove both accepted conversions and expected rejections. A conversion that succeeds by silently changing logical meaning is a correctness failure.

## Related ADRs

- [ADR-0014: File Format Adapter Contract](ADR-0014-file-format-adapter-contract.md)
- [ADR-0006: Validation Semantics](ADR-0006-validation-semantics.md)
