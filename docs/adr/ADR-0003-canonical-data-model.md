# ADR-0003: Canonical Data Model

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
