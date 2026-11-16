# ADR-0002: Rust as the Implementation Language

- **Status:** Accepted
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** The implementation language of the UDC core, CLI, and initial adapters.

## 1. Context

UDC is intended to be both a reusable library and a portable CLI. Its core workload includes parsing and writing binary formats, moving large datasets with bounded memory, interacting with object storage, and coordinating concurrent I/O and CPU work. The implementation language affects memory safety, runtime behavior, ecosystem access, contributor experience, and integration options.

## 2. Decision drivers

1. Memory safety for a tool that processes untrusted or externally supplied data.
2. Predictable resource use and efficient streaming of large datasets.
3. Strong interoperability with Arrow and the Rust-native data ecosystem.
4. Portable CLI and library distribution.
5. Maintainable concurrency and error handling.
6. Availability and maturity of the required cloud, format, and table libraries.
7. Contributor accessibility and long-term maintenance cost.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Rust** | Memory safety without a tracing GC; explicit ownership; strong Arrow/DataFusion/object-store ecosystem; good CLI distribution | Steeper learning curve; async and trait-heavy APIs can increase complexity; some integrations may lag JVM ecosystems |
| **Java / Scala** | Mature Spark, Iceberg, Hudi, and cloud data ecosystems; broad operational familiarity | JVM runtime and packaging footprint; GC behavior needs tuning for predictable memory pressure; less direct reuse of Rust-native libraries |
| **Go** | Simple deployment and concurrency model; mature cloud SDK ecosystem | Less direct interoperability with Arrow's Rust-native ecosystem; some columnar and table-format integrations may require bridging or bespoke work |
| **C++** | High performance and broad low-level systems access; Arrow has a mature C++ implementation | Manual lifetime and error-safety complexity; higher implementation risk for a new project |

## 4. Decision

Use **Rust** for the UDC core, CLI, and initial adapters.

This decision does not prohibit language-specific external integrations. For example, Spark integration may remain a separate JVM-side component if it becomes necessary.

## 5. Rationale

Rust aligns with the core workload's need for safe binary parsing, explicit memory ownership, streaming, and portable distribution. It also allows direct use of Rust implementations in the Arrow/DataFusion and object-store ecosystems without introducing a language boundary in the hot path.

The selection is conditional on validating the required format and cloud library coverage. It is not based on a blanket claim that Rust is faster or easier than the alternatives.

## 6. Toolchain, edition, and minimum Rust version

Added on 2026-11-17, when the workspace was created. The language decision above is unchanged.

- **Edition:** 2024, the edition `cargo new` selects with the pinned toolchain.
- **Pinned toolchain:** `rust-toolchain.toml` names one exact stable release, 1.100.0 at the time of writing, with rustfmt, clippy, and llvm-tools. Every developer and every CI run builds with it. It is raised by a pull request that changes only the toolchain and passes CI.
- **Minimum supported Rust version (MSRV):** until the first package release, `rust-version` in the workspace equals the pinned toolchain and moves with it. Nobody outside the project builds UDC before then, so an older floor would only add work. A floor for published crates, and how far it may trail the latest stable release, is decided before the first package release (ADR-0019).
- **Lints:** `unsafe_code` is forbidden and Clippy's default set is enforced, through workspace lints, with warnings treated as errors in CI. An exception is made where it is needed, with the reason next to it.

## 7. Trade-offs and consequences

- Contributors need Rust proficiency and familiarity with ownership, lifetimes, traits, and async programming.
- Some protocols or cloud features may have more mature JVM implementations; UDC may need an external integration or defer that capability.
- Dependency compile times and native build complexity must be managed.
- Public APIs should avoid exposing unnecessary implementation-specific types where practical.

## 8. Validation plan

Before declaring the first release production-ready:
- Verify the selected Rust libraries cover required Parquet, CSV, JSON, and cloud storage paths.
- Benchmark memory use and throughput on representative datasets.
- Test cancellation, backpressure, and error propagation under concurrent I/O.
- Review dependency licenses and maintenance activity.

## 9. Ownership boundary

**Owns:** the implementation language of the core, CLI, and initial adapters, and the Rust edition, the pinned toolchain, the minimum supported Rust version, and the language-level lints.

**Does not own:**
- The async runtime and concurrency primitives — ADR-0007.
- Workspace layout, dependency policy, and feature flags — ADR-0011.
- Which targets the official binary supports, and the release gates — ADR-0019.
- Execution backend selection — ADR-0004.

## 10. Revisit conditions

Revisit if required integrations are unavailable or materially incomplete in Rust, if measured performance or operational behavior fails the MVP targets, or if contributor/maintenance costs become prohibitive.

## 11. Related ADRs

- [ADR-0004: Execution Engine Selection](ADR-0004-execution-engine-selection.md)
- [ADR-0007: Async Runtime and Concurrency Control](ADR-0007-async-runtime-and-concurrency.md)
- [ADR-0011: Dependency and Feature Management](ADR-0011-dependency-and-feature-management.md)
- [ADR-0019: Packaging, Release, and Distribution](ADR-0019-packaging-and-distribution.md)
