# ADR-0008: Error Handling, Retry, and Failure Boundaries

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers

## Context

Long-running conversions fail for many reasons: corrupt input, incompatible schemas, transient network errors, provider throttling, expired credentials, exhausted disk, and process termination. Retrying every failure is unsafe and wasteful. A scalable migration system needs stable error categories and explicit retry boundaries.

## Decision drivers

1. Distinguish user/configuration errors, data errors, transient infrastructure errors, and internal defects.
2. Retry only failures likely to succeed on another attempt.
3. Avoid duplicate or partially published output.
4. Preserve source context and actionable diagnostics.
5. Support cancellation and resumability without losing failure provenance.

## Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **`thiserror` for typed domain errors + contextual error chains** | Stable library-facing error types; explicit matching; context can retain lower-level causes | Requires deliberate error taxonomy and conversion boundaries |
| **`anyhow` for all errors** | Ergonomic propagation and context in application code | Opaque errors are harder for SDK consumers and retry policy to classify reliably |
| **Ad hoc strings** | Simple initially | No stable classification; poor automation and tests; brittle retry logic |

## Proposed decision

Use typed errors in public/core boundaries (with `thiserror` as a candidate implementation) and contextual dynamic errors at application boundaries (where `anyhow` may be appropriate). Define machine-readable error codes and retry classification independently of crate-specific error types.

## Rationale

The library needs stable semantic errors; the CLI needs convenient diagnostic context. Retry policy must not infer semantics from error text. Separating classification from presentation lets jobs make deterministic retry decisions across different storage providers and format libraries.

## Retry policy requirements

- Retry only classified transient errors such as selected timeouts, connection resets, and provider throttling responses.
- Use bounded exponential backoff with jitter and a total retry/time budget.
- Respect provider `Retry-After` hints where present.
- Do not retry invalid configuration, unsupported features, schema incompatibility, deterministic decode errors, or permission failures without an explicit policy.
- Use idempotency keys or immutable attempt outputs so retries cannot overwrite or duplicate committed results.
- Record attempt number, error code, provider request ID (when safe), and next retry delay.

## Trade-offs and consequences

- Error taxonomies need versioning and documentation.
- Wrapping errors must preserve source chains and relevant provider context without exposing credentials.
- Retry policy must be coordinated with checkpointing and publication semantics.

## Validation plan

Inject transient and permanent failures at discovery, read, decode, encode, upload, validation, and publish stages. Verify only eligible failures retry, attempt limits are honored, diagnostics are actionable, and no incomplete output is published.

## Revisit conditions

Revisit when UDC introduces a durable distributed job coordinator or when new storage/table integrations require different failure classification.
