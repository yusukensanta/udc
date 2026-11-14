# ADR-0011: Dependency and Feature Management

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** Workspace layout, dependency policy, Cargo feature flags, and the CI feature matrix.

## 1. Context

UDC will integrate many formats, cloud providers, table formats, and optional execution engines. If every adapter is enabled in every build, users may inherit unnecessary dependencies, compile times, binary size, native system requirements, and vulnerability surface.

## 2. Decision drivers

1. Keep the minimal core small and portable.
2. Allow users to compile only needed providers/formats where practical.
3. Prevent incompatible dependency versions and feature unification surprises.
4. Maintain reproducible builds and dependency security.
5. Keep optional integrations discoverable and testable in CI.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **One crate with many Cargo features** | Simple package distribution; central feature selection | Cargo feature unification can activate unexpected combinations; monolithic dependency graph |
| **Workspace with focused adapter crates and optional facade features** | Clear ownership; independently testable; optional integrations | More crate/version management and release coordination |
| **Separate repositories per adapter** | Independent release cycles | More coordination and compatibility overhead for a single OSS product |

## 4. Proposed decision

Use a Rust workspace with a small core and focused adapter crates. Expose convenient optional Cargo features through facade crates only where they do not create confusing feature-unification behavior. Keep provider/execution SDKs out of the core dependency graph.

## 5. Rationale

Adapter-level crates isolate dependency trees and allow feature-specific CI and documentation. A small core improves compile ergonomics and reduces unnecessary runtime footprint. The workspace remains easier to coordinate than a multi-repository ecosystem in the early project stage.

## 6. Required rules

- Core must not depend on concrete cloud provider SDKs or optional query engines.
- Every optional integration documents feature flags, transitive dependencies, native requirements, and supported versions.
- Keep `default` features minimal; do not enable every cloud or format by default.
- Pin and audit dependency updates through reproducible lockfiles and automated checks.
- Review licenses, maintenance status, Rust version requirements, and security advisories before adding dependencies.
- CI must test minimal core, supported feature combinations, and all-features where feasible.

## 7. Trade-offs and consequences

- More crates increase workspace navigation and release complexity.
- Cargo feature unification may make additive features less isolated than users expect; test feature combinations explicitly.
- Optional integrations complicate docs and support matrix generation.

## 8. Validation plan

Measure clean build time, incremental build time, binary size, dependency tree, and compile success for minimal, common, and all-feature builds. Verify core builds without cloud SDKs or query engine integrations.

## 9. Ownership boundary

**Owns:** crate boundaries, the dependency graph, feature flags, dependency review rules, and the CI feature matrix.

**Does not own:**
- Which library is selected for a concern. That belongs to the ADR for the concern: ADR-0004 (execution), ADR-0005 (storage), ADR-0007 (runtime), ADR-0008 (errors), ADR-0009 (CLI), ADR-0010 (telemetry).
- Runtime architecture and component responsibilities — ADR-0001 and ADR-0012.

## 10. Revisit conditions

Revisit when the workspace becomes large enough to require independent adapter release cycles or when Cargo feature constraints materially hinder packaging.

## 11. Related ADRs

- [ADR-0001: Initial Architecture Principles](ADR-0001-initial-architecture.md)
- [ADR-0004: Execution Engine Selection](ADR-0004-execution-engine-selection.md)
- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0007: Async Runtime and Concurrency Control](ADR-0007-async-runtime-and-concurrency.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0009: CLI and Job Configuration](ADR-0009-cli-and-configuration.md)
- [ADR-0010: Observability and Telemetry](ADR-0010-observability.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
