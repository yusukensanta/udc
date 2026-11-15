# ADR-0008: Error Handling, Retry, and Failure Boundaries

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** The error taxonomy, machine-readable error codes, retry eligibility, and backoff rules.

## 1. Context

Long-running conversions fail for many reasons: corrupt input, incompatible schemas, transient network errors, provider throttling, expired credentials, exhausted disk, and process termination. Retrying every failure is unsafe and wasteful. A scalable migration system needs stable error categories and explicit retry boundaries.

## 2. Decision drivers

1. Distinguish user/configuration errors, data errors, transient infrastructure errors, and internal defects.
2. Retry only failures likely to succeed on another attempt.
3. Avoid duplicate or partially published output.
4. Preserve source context and actionable diagnostics.
5. Support cancellation and resumability without losing failure provenance.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **`thiserror` for typed domain errors + contextual error chains** | Stable library-facing error types; explicit matching; context can retain lower-level causes | Requires deliberate error taxonomy and conversion boundaries |
| **`anyhow` for all errors** | Ergonomic propagation and context in application code | Opaque errors are harder for SDK consumers and retry policy to classify reliably |
| **Ad hoc strings** | Simple initially | No stable classification; poor automation and tests; brittle retry logic |

## 4. Proposed decision

Use typed errors in public/core boundaries (with `thiserror` as a candidate implementation) and contextual dynamic errors at application boundaries (where `anyhow` may be appropriate). Define machine-readable error codes and retry classification independently of crate-specific error types.

Every error belongs to exactly one category in §6. Adapters, backends, and the CLI map their errors to these categories; they do not define their own.

## 5. Rationale

The library needs stable semantic errors; the CLI needs convenient diagnostic context. Retry policy must not infer semantics from error text. Separating classification from presentation lets jobs make deterministic retry decisions across different storage providers and format libraries.

## 6. Error categories

This is the proposed category set. Individual error codes within each category are finalized with the first implementation.

| Category | Examples | Default retry disposition |
|---|---|---|
| Configuration | Invalid option, malformed job configuration, unknown critical setting | Never retried |
| Compatibility | Unsupported format or table feature, incompatible schema mapping, plan or descriptor version the running UDC cannot interpret | Never retried |
| Data | Corrupt input, deterministic decode error, value that violates the mapping policy | Never retried |
| Authentication / authorization | Credentials missing, expired, or not refreshable; permission denied | Not retried without an explicit policy |
| Transient | Selected timeouts, connection resets, provider throttling, temporary identity-endpoint failure | Retried with backoff, within budget |
| Resource | Memory budget exhausted, disk full, quota exceeded | Not retried by default; policy-dependent |
| Conflict | Source changed after planning, concurrent update of the destination, an existing object at a destination name, table commit conflict | Never retried blindly; requires reconciliation or a new plan |
| Cancelled | User cancellation, graceful shutdown | Never retried |
| Internal | Violated invariant, illegal state transition, other defect | Never retried |

"Permanent" is a retry disposition, not a category: Configuration, Compatibility, Data, and Internal errors are permanent for a given plan.

## 7. Retry policy requirements

- Retry only errors whose category is eligible, such as selected timeouts, connection resets, and provider throttling responses.
- Use bounded exponential backoff with jitter and a total retry/time budget.
- Respect provider `Retry-After` hints where present.
- Do not retry invalid configuration, unsupported features, schema incompatibility, deterministic decode errors, or permission failures without an explicit policy.
- A retry is a new Attempt. It relies on attempt-isolated output and conditional acceptance (ADR-0013), so it can never overwrite or duplicate accepted output.
- The retry budget is counted per execution generation (ADR-0013). When a Work Unit exhausts it, the unit becomes FAILED and the job failure policy in ADR-0012 applies.
- Each Attempt record carries the attempt number, error code and category, provider request ID (when safe), and next retry delay. The record itself is defined by ADR-0013.

## 8. Trade-offs and consequences

- Error taxonomies need versioning and documentation.
- Wrapping errors must preserve source chains and relevant provider context without exposing credentials.
- Retry policy must be coordinated with checkpoint and publication semantics (ADR-0013, ADR-0017).

## 9. Validation plan

Inject transient and permanent failures at discovery, read, decode, encode, upload, validation, and publish stages. Verify only eligible failures retry, attempt limits are honored, diagnostics are actionable, and no incomplete output is published. Verify that every error surfaced by an adapter maps to exactly one category.

## 10. Ownership boundary

**Owns:** error categories and codes, the default retry disposition of each category, and backoff and budget rules.

**Does not own:**
- Persisting Attempt records and accepting output — ADR-0013.
- What the Scheduler does with the job when a Work Unit fails — ADR-0012.
- Explicit resume of a failed or cancelled job — ADR-0013.
- Reconciling an ambiguous publication outcome — ADR-0017, or ADR-0015 for a table commit.
- How errors are exported as telemetry — ADR-0010.

## 11. Revisit conditions

Revisit when UDC introduces a durable distributed job coordinator or when new storage/table integrations require different failure classification.

## 12. Related ADRs

- [ADR-0010: Observability and Telemetry](ADR-0010-observability.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0015: Table Format Integration Boundary](ADR-0015-table-format-integration-boundary.md)
- [ADR-0017: Output Publication Protocol](ADR-0017-output-publication-protocol.md)
