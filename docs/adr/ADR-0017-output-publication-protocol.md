# ADR-0017: Output Publication Protocol

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** The Generic Publisher: staging layout, output manifest, visibility commit, reconciliation, and staging cleanup for generic file/dataset output.

## 1. Context

UDC must not expose partial or unvalidated output as a successfully converted dataset. Object stores do not universally provide filesystem-style atomic directory rename. A migration may involve thousands or millions of output objects, validation artifacts, and a final visible dataset reference. Publication must therefore be explicitly modeled and destination-aware.

Table-format commits have their own transaction protocols and are governed by ADR-0015. This ADR defines generic file/dataset publication only.

## 2. Decision drivers

1. Keep incomplete output invisible to consumers using the published dataset reference.
2. Support object stores without assuming atomic rename.
3. Make publication idempotent and recoverable after client/process failure.
4. Prevent accidental source overwrite and conflicting concurrent jobs.
5. Bind publication to an immutable, validated set of output objects.
6. Minimize extra full-data copies and unnecessary listing operations.
7. Separate data upload durability from dataset visibility.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Write directly to final prefix** | Simple; no extra copy | Partial data may be visible; rollback/overwrite conflicts are difficult |
| **Temporary prefix then rename** | Familiar filesystem model | Object-store rename may be copy+delete or unsupported; not generally an atomic commit |
| **Immutable staging objects + final manifest/pointer** | Visibility can be switched by a small final commit; supports validation and idempotent reconciliation | Consumers must read via manifest/pointer-aware convention; old versions require garbage collection |
| **Provider-specific atomic conditional object update** | Strong commit primitive where supported | Capabilities and semantics vary; cannot be assumed portable across clouds |

## 4. Proposed decision

Use **immutable attempt-scoped staging objects plus an immutable output manifest and a destination-specific publication reference** as the default conceptual protocol. The final publication operation must use a conditional write/version precondition or another provider-specific commit primitive where available. Do not treat prefix existence or a successful rename as proof of publication.

The exact final pointer mechanism (single manifest object, versioned catalog entry, conditional object update, or other provider capability) must be negotiated and tested per destination. If the destination cannot provide safe publication semantics, UDC must either use a documented weaker mode with explicit user acknowledgement or reject the safe-publication guarantee.

The component that executes this protocol is the **Generic Publisher**. This ADR is its only normative definition. Orchestration (ADR-0012) decides when it is invoked; it does not define what the Generic Publisher does.

## 5. Publication phases

Publication depends on steps that other ADRs own. The table lists the full sequence and, for each phase, what this ADR requires and which ADR owns the rest.

| # | Phase | What happens | Defined here | Owned elsewhere |
|---|---|---|---|---|
| 1 | Plan | Determine the publication target and capture destination preconditions/version where available | Target and precondition capture | Output ownership per Work Unit: ADR-0012 |
| 2 | Stage | Write attempt-scoped immutable data objects; never overwrite source objects | Staging layout: attempt-scoped, immutable, outside the published view | Who writes and when: ADR-0012 workers through ADR-0014 writers and ADR-0005 storage |
| 3 | Finalize | Close writers, verify durable upload completion, collect object identities, sizes, checksums/ETags, and format metadata | Which object identities the output manifest needs | Writer close semantics: ADR-0014. Acceptance of the Attempt: ADR-0013 |
| 4 | Validate | Apply the requested validation policy against the source and staged output; record evidence and its scope | That publication requires recorded evidence | What evidence means: ADR-0006. Recording it: ADR-0013 |
| 5 | Build output manifest | Create an immutable manifest listing the exact accepted objects and relevant schema/partition metadata, with a digest and format version | Entirely | — |
| 6 | Commit publication reference | Use a conditional update/version precondition to make the manifest visible as the current output, or a destination-native pointer transaction | Entirely | The conditional-write primitive: ADR-0005 |
| 7 | Record outcome | Record publication intent and result so an ambiguous acknowledgement can be reconciled | The reconciliation procedure | The publication record: ADR-0013 |
| 8 | Garbage collect | Asynchronously remove unreferenced attempt output after retention and reference-safety checks | Reference-safety rules | Retention policy and records: ADR-0013 |

## 6. Idempotency and concurrency

- Publication ID is stable for a Job and its plan generation, and therefore unchanged across execution generations (ADR-0013). A resumed job reconciles the same publication instead of starting a second one.
- Manifest content is immutable and content-addressed or versioned.
- The commit request includes an expected prior destination version/ETag or equivalent precondition where supported.
- A retry after an ambiguous response must read/reconcile the destination reference before attempting another commit.
- Two jobs targeting the same logical destination must not silently overwrite each other; apply conflict detection or explicit overwrite policy.
- Late attempts cannot add objects to an already committed output manifest.
- Garbage collection must be reference-aware and must not delete accepted/published objects.

## 7. Object-store limitations and capability negotiation

The Storage adapter (ADR-0005) exposes provider operations and conditional-write/version capabilities. The Generic Publisher selects a protocol only from capabilities actually verified for that provider/account configuration. It must not infer atomicity from API naming.

Where no suitable conditional commit primitive exists, the default should be a unique versioned output location plus a separately managed pointer/catalog mechanism, or an explicit weaker publication mode. UDC must document consumer requirements for reading the published dataset.

## 8. Validation plan

Inject failure before/during/after each publication phase, including lost response after the destination conditional commit. Verify that consumers never see incomplete output through the supported published reference, repeated commit attempts are idempotent, concurrent destination updates are detected, and garbage collection preserves referenced objects.

Test provider-specific semantics for S3, GCS, and Azure separately; do not generalize one provider's guarantee to the others.

## 9. Ownership boundary

**Owns:** the Generic Publisher and its protocol for generic file/dataset output: staging layout, the output manifest, the visibility commit, reconciliation of ambiguous outcomes, and reference-safe cleanup of staging.

**Does not own:**
- Publication of Iceberg, Delta, Hudi, or Lance tables. This ADR never publishes a table by rewriting a pointer itself; table publication uses the format-native commit protocol — ADR-0015.
- When the job workflow invokes publication — ADR-0012.
- Object operations and conditional-write capabilities — ADR-0005.
- What validation evidence means — ADR-0006.
- The publication record, retention policy, and recovery state — ADR-0013.
- Retry eligibility of publication errors — ADR-0008.

## 10. Revisit conditions

Revisit when a concrete provider set and consumer discovery convention are selected, or when UDC introduces table-format publication as a production capability.

## 11. Related ADRs

- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0006: Validation Semantics](ADR-0006-validation-semantics.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0014: File Format Adapter Contract](ADR-0014-file-format-adapter-contract.md)
- [ADR-0015: Table Format Integration Boundary](ADR-0015-table-format-integration-boundary.md)
