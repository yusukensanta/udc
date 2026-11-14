# ADR-0005: Storage Abstraction

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers

## Context

UDC must access local files and multiple object stores, initially S3, GCS, and Azure Blob Storage. Provider identity and token acquisition are deliberately separated from byte/object I/O. Format readers and writers need byte-oriented operations such as reads, range reads, writes, listing, and metadata access. Migration orchestration additionally needs staging, multipart/resumable upload, conditional operations, and publication semantics.

A lowest-common-denominator abstraction can hide provider differences that matter for correctness and performance. Conversely, exposing each cloud SDK throughout the core would make portability difficult.

## Decision drivers

1. Keep provider-specific SDK details out of format and orchestration code.
2. Support local files and the target object stores.
3. Preserve access to range reads and streaming writes.
4. Expose provider capabilities and conditional operation support.
5. Integrate with credential resolution without storing secrets in UDC configuration; credential source and refresh policy are owned by [ADR-0016](ADR-0016-cloud-authentication.md).
6. Avoid claiming atomic rename or transaction semantics where object stores do not provide them.
7. Reuse maintained ecosystem libraries where feature coverage is sufficient.

## Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **UDC-owned storage trait and provider implementations** | Full control over API and capabilities | High maintenance burden; duplicates SDK behavior; many cloud-specific edge cases |
| **Common object-store library (e.g. Rust object_store ecosystem) behind a UDC adapter** | Reuses common API and provider implementations; Arrow ecosystem alignment | Lowest-common-denominator API may omit provider-specific features; authentication and feature support must be verified |
| **Direct cloud SDK use throughout UDC** | Full provider feature access | Strong provider coupling; duplicated logic; harder portability and testing |

## Proposed decision

Evaluate the Rust `object_store` ecosystem as the default byte/object access layer behind a small UDC-owned capability interface. Keep provider-specific extensions isolated behind adapter interfaces where required.

This is not yet a commitment that a single object-store API covers all migration and publication requirements.

## Rationale

Most format readers need a relatively small set of object operations. Reusing an established common library can reduce duplicated cloud integration code and align with Arrow-based tooling. UDC still needs its own capability model for semantics above basic object access, particularly conditional writes, multipart upload, consistency behavior, and safe publication.

## Trade-offs and consequences

- Provider-specific capabilities may not be portable and must be surfaced explicitly.
- Credential-chain behavior differs across clouds and needs integration testing.
- Object-store operations are not equivalent to filesystem operations; rename must not be assumed atomic.
- Staging and publication need a separate design from the basic storage trait.

## Validation plan

Test local filesystem, S3, GCS, and Azure with sequential and ranged reads; streaming/multipart writes; large-object behavior; conditional create/replace where available; list and metadata operations; authentication via native credential chains/workload identity; transient failures and retry behavior; cleanup and publication workflows.

Record provider/library versions and unsupported capabilities.

## Ownership boundary

ADR-0005 owns object operations, data transfer and storage-provider capabilities. It consumes provider clients or credential handles resolved under ADR-0016 and exposes object operations used by the generic Publisher under ADR-0017. It does not own credential precedence, token refresh policy, JobStateStore transitions, or final dataset visibility semantics.

## Revisit conditions

Revisit if the common library cannot expose a required provider capability safely, if its maintenance/feature coverage becomes inadequate, or if provider SDK usage materially improves reliability without contaminating core abstractions.
