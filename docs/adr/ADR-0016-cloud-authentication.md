# ADR-0016: Cloud Authentication and Credential Resolution

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Priority:** P1

## 1. Context

UDC accesses Amazon S3, Google Cloud Storage, Azure Blob Storage, and potentially cloud-hosted catalogs. Each provider has different credential chains, identity federation, token refresh, role assumption, and endpoint rules. Authentication concerns must not leak into FileFormatAdapter or the canonical schema model. A long-running job must also survive credential refresh without serializing secrets into its Job Manifest.

## 2. Decision drivers

1. Prefer short-lived credentials and workload identity over long-lived static secrets.
2. Reuse provider-native SDK credential resolution and refresh where practical.
3. Keep provider SDK types out of the UDC domain model.
4. Support local developer workflows without making them the production default.
5. Avoid credentials in CLI arguments, job manifests, logs, traces, or error messages.
6. Permit refresh during long-running jobs.
7. Support least privilege and provider-specific endpoint/region configuration.
8. Make credential source and identity diagnosable without exposing secret material.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **UDC-managed static access keys** | Simple and uniform | Secret distribution/rotation burden; poor workload identity; high leakage risk |
| **Provider-native default credential chains and SDK refresh** | Matches cloud best practices; reuses provider behavior; supports workload identity and federation | Credential chain behavior varies by SDK; test matrix required |
| **UDC-owned universal token broker** | Uniform abstraction and central policy | Duplicates provider identity systems; large security scope and maintenance burden |
| **External secret manager only** | Central secret storage and rotation | Does not itself define cloud identity or token refresh; adds service dependencies |

## 4. Proposed decision

Define a provider-neutral **CredentialResolver** interface, while delegating actual identity acquisition and token refresh to provider-native SDK credential chains wherever possible. UDC configuration should select a credential profile/source or identity mode, not carry resolved secret values. Static credentials may be supported as an explicitly opt-in local/testing path, but must not be the recommended production mode.

## 5. Responsibility boundaries

- CredentialResolver resolves identity for a provider/resource scope and returns a short-lived provider client/session or opaque credential handle.
- Storage adapters use the resolved provider client; they do not parse user config or implement their own global credential precedence.
- Catalog adapters use the same identity-resolution policy but may require separate audience/scopes.
- CLI/config layer defines user-visible settings and precedence under ADR-0009.
- Job Manifest persists only credential references/profile identifiers and non-secret identity metadata under ADR-0013.
- Observability records provider, credential source category, expiry/refresh outcome, and identity subject where safe; never records tokens or key material.

## 6. Provider considerations

### AWS

Evaluate the AWS SDK default credential provider chain, including environment/profile, web identity, container credentials, and instance role sources. Role assumption and session refresh should use SDK-supported mechanisms.

### GCP

Evaluate Application Default Credentials and workload identity federation. Do not assume service-account key files are required or preferred.

### Azure

Evaluate DefaultAzureCredential or the relevant Azure SDK chain, including managed identity and developer tooling. Verify token refresh behavior for long-running uploads.

These are candidates to validate against the specific Rust SDKs selected by ADR-0005; this ADR does not assert that all chains have equivalent feature support in every Rust library.

## 7. Long-running job behavior

- Resolve credentials as late as practical, near resource access.
- Support token refresh without restarting the whole job where SDKs provide it.
- Distinguish authentication failure from authorization failure and transient identity endpoint failure.
- Do not persist bearer tokens or signed URLs in Plan/Attempt records.
- If refresh cannot be performed, stop admission of new work and fail/retry only according to ADR-0008; do not publish incomplete outputs.
- Document re-authentication requirements for resumed jobs.

## 8. Security requirements

- No secrets in command-line arguments by default.
- No secret values in config snapshots, Job Manifest, event logs, metrics, or traces.
- Redact signed URLs and authorization headers.
- Use least-privilege identity scopes per source, destination, and catalog.
- Support TLS and provider-native endpoint validation.
- Make static credentials explicit and opt-in, with clear rotation guidance.

## 9. Validation plan

Test local developer profile, role/workload identity, token expiry/refresh, revoked permissions, wrong audience/scope, network interruption to identity service, and resumed jobs. Inspect persisted manifests and telemetry to verify that no secret material is present.

## 10. Revisit conditions

Revisit when provider SDK selection is finalized or when UDC adds a managed multi-tenant execution service with delegated identity requirements.

## Related ADRs

- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0009: CLI and Job Configuration](ADR-0009-cli-and-configuration.md)
- [ADR-0010: Observability and Telemetry](ADR-0010-observability.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
