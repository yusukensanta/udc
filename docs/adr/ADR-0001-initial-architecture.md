# ADR-0001: Initial Architecture Principles

- **Status:** Accepted
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers

## Context

UDC must support file conversion, cross-cloud data movement, validation, and eventually table-format interoperability. These capabilities span concerns with different lifecycles and semantics: physical encodings, logical types, object storage, table transactions, execution, and job orchestration.

The initial design must keep the MVP operable as a local tool while avoiding abstractions that prevent later integrations. Technology choices should be justified against explicit decision drivers and recorded in focused ADRs. This ADR establishes architectural boundaries; it does not select every implementation library.

## Decision drivers

1. Preserve data semantics and make lossy conversions explicit.
2. Keep the core portable across clouds and execution engines.
3. Bound memory use and support streaming/backpressure.
4. Reuse mature protocol and format implementations.
5. Keep the MVP easy to run, test, and contribute to.
6. Make implementation maturity and unsupported capabilities visible.

## Decisions

### 1. Use a modular Rust codebase for the initial implementation

Rust is the initial implementation language. This is a project-level direction, not a claim that Rust is universally superior for data systems. The rationale and alternatives are recorded in [ADR-0002](ADR-0002-rust-implementation-language.md).

### 2. Separate logical semantics from physical and execution representations

UDC will not treat a physical file schema or an in-memory vector schema as the complete definition of a dataset's meaning. A canonical logical model will represent meaning and conversion constraints; physical format schemas and execution representations will be mapped to and from it. See [ADR-0003](ADR-0003-canonical-data-model.md).

### 3. Keep format, storage, catalog, execution, validation, and orchestration boundaries independent

- **Format adapters** decode and encode file-level representations.
- **Table adapters** implement table metadata, snapshot, delete, and commit semantics.
- **Storage adapters** access bytes and object metadata.
- **Catalog adapters** discover and register tables.
- **Execution backends** perform supported transformations and data movement.
- **Validation** defines correctness checks and comparison semantics.
- **Orchestration** manages jobs, retries, checkpoints, staging, and publication.

### 4. Reuse mature implementations instead of reimplementing protocols

UDC should wrap or integrate established libraries where their feature coverage and licensing are acceptable. An adapter must expose the supported feature set and known limitations; a dependency's existence does not mean that UDC supports every feature of the underlying specification.

### 5. Start as a modular monolith with statically linked integrations

The initial deliverable should be a single deployable CLI/library with internal crate boundaries. Dynamic plugin loading and distributed services are deferred until a concrete compatibility or operational requirement justifies their costs.

## Rationale

A modular monolith minimizes deployment and operational complexity while still allowing compile-time boundaries and independent testing. Separating logical semantics from physical encodings avoids coupling correctness to the accidental capabilities of any one file format or engine. Reusing existing implementations reduces protocol-maintenance risk, while explicit capability reporting prevents a thin integration from being mistaken for complete support.

## Trade-offs and consequences

- More interfaces and mapping code are required than in a single-framework implementation.
- Different backends may support different subsets of operations; UDC needs capability negotiation rather than pretending all backends are equivalent.
- Rust dependencies and cloud SDK maturity must be checked per integration.
- Modular boundaries can become over-engineered; abstractions should be introduced around demonstrated variation, not speculative extension points.
- Some table-format operations cannot be safely implemented as generic file conversion.

## Alternatives considered

### One execution framework owns the whole product

Rejected as the architectural default because it would couple storage, format support, execution, and table semantics to a single framework and its release cadence.

### A distributed microservice architecture from the beginning

Rejected because it adds deployment, RPC, and operational complexity before the MVP has demonstrated a need for independent scaling or remote control planes.

### Implement all format and table protocols in UDC

Rejected because it duplicates mature ecosystem implementations and creates a large ongoing compatibility burden.

## Validation

- The MVP must run locally without a mandatory control plane.
- A format conversion path must be testable independently of table-format transaction handling.
- Core tests must be able to use local/fake storage without cloud credentials.
- Unsupported format or table features must fail explicitly, not silently degrade.

## Revisit conditions

Revisit this ADR if the modular monolith prevents independent scaling, if Rust ecosystem limitations block core requirements, or if evidence shows that the chosen boundaries create more complexity than they remove.

## Related ADRs

- [ADR-0002: Rust as the Implementation Language](ADR-0002-rust-implementation-language.md)
- [ADR-0003: Canonical Data Model](ADR-0003-canonical-data-model.md)
- [ADR-0004: Execution Engine Selection](ADR-0004-execution-engine-selection.md)
- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0006: Validation Semantics](ADR-0006-validation-semantics.md)
