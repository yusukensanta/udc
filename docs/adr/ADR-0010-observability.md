# ADR-0010: Observability and Telemetry

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** Telemetry instrumentation, signal types, cardinality and redaction rules, and export.

## 1. Context

Large migrations can run for hours and involve many files, partitions, retries, cloud APIs, and validation steps. Logs alone do not explain where time, memory, or bandwidth is spent. UDC needs correlated traces, metrics, and structured events without requiring a hosted observability service.

## 2. Decision drivers

1. Local-first operation with optional external telemetry export.
2. Correlation across job, execution generation, pipeline stage, Work Unit, Attempt, and storage request.
3. Low-cardinality metrics suitable for large jobs.
4. Useful progress and resource metrics without logging sensitive object contents or credentials.
5. Integration with common observability platforms.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **`tracing` + `tracing-subscriber` with OpenTelemetry bridge** | Structured spans/events and Rust ecosystem integration; OpenTelemetry export | Requires careful cardinality and sampling design; bridge versions may evolve |
| **OpenTelemetry SDK directly throughout core** | Vendor-neutral API and export | Can spread telemetry concerns through domain code; more verbose instrumentation |
| **Logs only** | Simple and portable | Weak cross-stage correlation and poor visibility into bottlenecks |

## 4. Proposed decision

Use `tracing` as the instrumentation API, `tracing-subscriber` for local formatting/filtering, and OpenTelemetry integration as an optional exporter. Export must be opt-in/configurable; local logs and metrics must remain useful without a collector.

## 5. Rationale

`tracing` models nested operations naturally, which fits job → Work Unit → Attempt → pipeline stage → storage operation lifecycles. OpenTelemetry provides interoperable export. Keeping the bridge at the application/integration boundary limits vendor-specific dependencies in the core.

## 6. Required telemetry

- Counters: files/objects discovered, completed, failed, retried; bytes read/written; rows processed; validation failures.
- Histograms: read/write latency, batch processing time, queue wait time, request latency, retry delay.
- Gauges: in-flight bytes, queue occupancy, active work units, open uploads, CPU/memory usage.
- Per-job progress: completed/total work units and bytes, with totals marked unknown when discovery is incomplete.
- Trace context: job ID, execution generation, Work Unit ID, Attempt ID, and pipeline stage; avoid object paths as metric labels.

## 7. Trade-offs and consequences

- High-cardinality labels such as file path, partition value, and job ID must not be metric dimensions; keep them in sampled traces/log fields where appropriate.
- Telemetry export must not block or crash data processing.
- Sampling and event volume need defaults for very large migrations.
- Sensitive values and customer data must be redacted.

## 8. Validation plan

Run large synthetic migrations and verify telemetry overhead, cardinality, local usability without collector, trace correlation through retries, and absence of secrets or payload data.

## 9. Ownership boundary

**Owns:** the instrumentation API, signal names and types, cardinality and redaction rules, sampling, and export.

**Does not own:**
- Authoritative job progress and state — ADR-0013. Telemetry is derived from it and is never the source of truth.
- Which resource budgets and scheduler signals exist — ADR-0012 lists the signals the processing layer must supply.
- Error codes and categories used as telemetry attributes — ADR-0008.
- Which identity attributes are safe to record — ADR-0016.

## 10. Revisit conditions

Revisit if UDC becomes a managed multi-tenant service or adopts a distributed coordinator.

## 11. References

- [tracing crate](https://docs.rs/tracing/latest/tracing/)
- [OpenTelemetry for Rust](https://opentelemetry.io/docs/languages/rust/)

## 12. Related ADRs

- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0016: Cloud Authentication and Credential Resolution](ADR-0016-cloud-authentication.md)
