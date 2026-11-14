# ADR-0001: Initial Architecture Direction

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers

## Context

UDC aims to provide a cloud-agnostic interface for file format conversion, table format interoperability, migration execution, and data validation.

The project must integrate with an ecosystem of mature execution engines and format implementations without coupling its core domain model to a particular cloud provider or execution engine.

## Decision

The initial architecture will follow these principles:

1. Implement the core in Rust.
2. Use Apache Arrow as the primary in-memory representation.
3. Define a separate canonical logical schema model for type semantics and compatibility decisions.
4. Initially evaluate Apache DataFusion as the native execution engine.
5. Keep file format adapters separate from table format integrations.
6. Keep storage, catalog, execution, validation, and orchestration as separate capabilities.
7. Prefer existing table format libraries and interoperability projects over implementing specifications from scratch.
8. Begin with statically linked adapters and explicit capability discovery; defer dynamic plugin loading.

## Consequences

### Positive

- Strong separation of concerns.
- Reuse of established ecosystem components.
- A clear path to multiple execution engines and cloud providers.
- Explicit handling of semantic compatibility.

### Trade-offs

- The canonical logical schema introduces additional modeling and maintenance work.
- Engine adapters may expose different capabilities.
- Rust ecosystem coverage for some formats and cloud authentication flows requires technical validation.
- Cross-cloud integration testing requires access to real cloud environments.

## Rejected alternatives

### Use Arrow alone as the complete canonical model

Rejected because in-memory types do not fully capture all source and target format semantics, constraints, annotations, and lossy conversion policies.

### Implement every format and table protocol internally

Rejected due to duplicated effort and long-term protocol maintenance burden.

### Start with a distributed microservice architecture

Rejected because the MVP should remain easy to run locally, develop, and contribute to.

## Follow-up decisions

- Canonical logical type system.
- Format reader/writer interfaces.
- Storage and object-store abstraction.
- Job and publication semantics.
- Validation and logical equality semantics.
- Table format integration boundaries.
