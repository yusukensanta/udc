# ADR-0013: Job Manifest and State Management

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** Persisted Job, Plan, Work Unit, Attempt, and Publication records; execution generations; legal state transitions; atomicity and durability; single-node restart recovery; and explicit resume.

## 1. Context

ADR-0012 establishes a resource-bounded execution model based on Job, Plan, Work Unit, and Attempt. That model requires durable state to support restart recovery, retry isolation, progress reporting, and safe publication. In-memory state is insufficient for long-running migrations because process termination can occur between writing output and recording completion.

The state model must work for the single-node MVP without forcing a database server, but it must not make process-local memory or a local filesystem path the only possible storage model. A future distributed scheduler will require conditional state transitions and concurrency control across multiple workers.

## 2. Decision drivers

1. Recover job progress after an unclean process termination.
2. Prevent duplicate or late attempts from replacing an accepted output.
3. Make state transitions explicit, validated, and auditable.
4. Keep the MVP easy to install and operate locally.
5. Support large plans without requiring the entire manifest in memory.
6. Permit a future remote state store without changing domain semantics.
7. Separate orchestration metadata from dataset payloads.
8. Avoid claiming distributed multi-writer safety from a single-process store.
9. Version persisted schemas and support explicit compatibility behavior.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **In-memory state only** | Minimal implementation and fast access | No restart recovery; unsuitable for durable jobs |
| **Local append-only manifest / journal** | Simple local deployment; auditable state history; can recover after restart | Requires compaction, corruption handling, and careful fsync/durability policy; single-node scope initially |
| **SQLite-backed state store** | Transactional updates, indexes, single-file deployment, mature tooling | Write concurrency and locking need care; not a distributed shared state store; database schema migrations required |
| **Object-storage manifest documents** | Natural fit for cloud-first jobs and durable remote storage | Conditional update/CAS support varies; concurrent mutation and listing semantics complicate coordination |
| **External database (e.g. PostgreSQL)** | Strong transactional and multi-worker coordination capabilities | Operational dependency; inappropriate as a mandatory local MVP dependency |

## 4. Proposed decision

Define a storage-agnostic **JobStateStore** domain interface and versioned manifest schema. The MVP must implement durable Job and Work Unit state with restart recovery. SQLite is the leading implementation candidate, but the storage technology is not finalized by this ADR; compare SQLite with an append-only local journal in a small crash-recovery PoC before locking the backend. This single-node durability requirement is part of the MVP; distributed leases and multi-writer coordination are deferred.

The abstraction must explicitly distinguish:
- **State store:** authoritative job/work-unit/attempt state and conditional transitions.
- **Artifact storage:** plan fragments, validation reports, and large manifest segments when they do not belong in the transactional state database.
- **Data storage:** source and destination data objects accessed through ADR-0005 storage adapters.

These are separate concerns even if an MVP implementation physically stores several categories in one local directory or SQLite database.

## 5. Domain model and persisted entities

### 5.1 JobRecord

Contains:
- job_id (stable, globally unique identifier);
- manifest_schema_version;
- job_spec_digest and an immutable reference to the effective non-secret configuration (ADR-0009);
- created_at, updated_at, started_at, completed_at;
- job_state and monotonically increasing state_version;
- execution_generation, monotonically increasing (§9);
- source/destination references and source consistency policy;
- plan_id / plan_digest;
- resource profile and retry policy references;
- validation and publication policy references;
- summary counters and progress snapshots (derived/cacheable, not authoritative per-unit truth).

Resolved credentials and secret values must never be persisted in a manifest. Persist identity/credential references only.

### 5.2 PlanRecord and PlanFragment

A plan is immutable after execution begins. It contains the canonical plan digest and references to one or more plan fragments. Large plans must be pageable or chunked; storing millions of Work Unit descriptors in one JSON document or loading them all into RAM is prohibited.

Plan fragments are immutable and content-addressed or versioned. The job record tracks the expected fragment set or an explicit discovery-complete marker. The plan digest covers normalized job intent, relevant source identity, schema mapping, the selected validation levels with the normalization rules version and normalization policy (ADR-0006), the publication target and mode (ADR-0017), adapter capability versions, and work-unit descriptors. It must exclude secrets and non-deterministic runtime details such as worker assignment.

If source discovery is incremental, the job remains in PLANNING until discovery completes or the selected execution policy explicitly supports streaming discovery concurrently with processing. The MVP should prefer complete planning for deterministic output ownership unless memory/cardinality tests demonstrate that incremental plan execution is necessary.

### 5.3 WorkUnitRecord

Contains:
- work_unit_id and plan_id;
- immutable descriptor reference or descriptor payload;
- state and state_version;
- accepted_attempt_id (nullable until completion);
- attempt_count and next_eligible_at;
- created_at / updated_at;
- completion metadata: output artifact reference, bytes/rows, validation result reference;
- last_error_code and sanitized error summary.

Work Unit descriptors are immutable after the plan is sealed. Changes to input boundaries or output ownership require a new plan/version, not an in-place mutation.

### 5.4 AttemptRecord

Contains:
- attempt_id and work_unit_id;
- attempt_number and the execution_generation it ran in;
- attempt_state and state_version;
- worker/runtime identity (informational, not part of unit identity);
- lease_owner and lease_expiry when the backend supports leases;
- started_at, heartbeat_at, completed_at;
- staging output references and multipart upload identifiers where safe to persist;
- resource usage summary;
- structured error code/classification and retry decision.

Each attempt writes to an isolated staging namespace or deterministic idempotent destination. Attempt output must not become the accepted output merely because a worker reports success.

### 5.5 PublicationRecord

Contains publication ID, job ID, publication mode, publication state, the completion marker or publication reference that identifies the commit, expected output manifest digest, timestamps, and failure/reconciliation details. In Promotion mode the record also states whether the destination is unchanged, partially promoted, or committed (ADR-0017). Publication state is separate from Work Unit completion: all units may be complete while the job is not yet published.

### 5.6 ExecutionGenerationRecord

Contains job_id, the generation number, its trigger (initial run or explicit resume), start and end timestamps, the terminal job state it reached, the precondition results of a resume, and any execution-tuning overrides applied. These records are append-only.

## 6. State machines and legal transitions

### 6.1 Job state

| Current state | Allowed next states | Notes |
|---|---|---|
| PLANNING | READY, FAILED, CANCELLED | Plan is validated and sealed before READY |
| READY | RUNNING, FAILED, CANCELLED | Execution can begin |
| RUNNING | VALIDATING, FAILED, CANCELLED | All required work units have reached terminal accepted outcomes |
| VALIDATING | PUBLISHING, SUCCEEDED, FAILED, CANCELLED | Required validation has succeeded. SUCCEEDED directly only for a validation-only job (§6.4) |
| PUBLISHING | SUCCEEDED, FAILED | Publication has a destination-specific commit outcome |
| SUCCEEDED | none | Terminal |
| FAILED | READY, by explicit resume only | Terminal for the execution generation; §9 |
| CANCELLED | READY, by explicit resume only | Terminal for the execution generation; §9 |

### 6.2 Work Unit state

| Current state | Allowed next states | Notes |
|---|---|---|
| PENDING | READY, CANCELLED | Dependencies satisfied and admission possible |
| READY | RUNNING, CANCELLED | Attempt claimed |
| RUNNING | STAGED, RETRY_WAIT, FAILED, CANCELLED | Worker result received or lease deemed expired |
| STAGED | VALIDATING, RETRY_WAIT, FAILED | Output is durable but not yet accepted |
| VALIDATING | COMPLETED, RETRY_WAIT, FAILED | Validation result determines acceptance |
| RETRY_WAIT | READY, FAILED, CANCELLED | Retry budget and deadline checked |
| COMPLETED | none | Accepted attempt is immutable across execution generations |
| FAILED | PENDING, by explicit resume only | Terminal for the execution generation |
| CANCELLED | PENDING, by explicit resume only | Terminal for the execution generation |

### 6.3 Attempt state

| Current state | Allowed next states | Notes |
|---|---|---|
| CLAIMED | RUNNING, ABANDONED | Claim created before work starts |
| RUNNING | STAGED, FAILED, ABANDONED | Worker progress / heartbeat |
| STAGED | ACCEPTED, REJECTED | Scheduler/validator resolves attempt |
| ACCEPTED | none | Sole accepted output for the Work Unit |
| REJECTED | none | Output retained temporarily for diagnosis or cleanup |
| FAILED | none | Error classification recorded |
| ABANDONED | none | Lease expired or execution owner disappeared |

### 6.4 Validation-only jobs

A validation-only job (`udc validate`, ADR-0009) compares two existing datasets and writes no output objects.

- Its Work Units compute evidence for a part of one side. The result of an Attempt is an evidence record held in the State Store, and STAGED means that this record is durable but not yet accepted. The Work Unit and Attempt state machines are unchanged.
- The job moves from VALIDATING to SUCCEEDED when the evidence of the two sides agrees at every selected level, and to FAILED with a Validation error (ADR-0008) when it does not. It never enters PUBLISHING and has no PublicationRecord.
- Restart recovery and explicit resume apply as for any job: evidence of COMPLETED Work Units is kept and not recomputed.
- The plan digest covers both datasets' identities, the declared mapping, and the validation levels with the normalization rules version and policy.

State transitions must be performed by the orchestration layer through compare-and-swap semantics or a transaction. A stale worker must not move a completed unit back to RUNNING or overwrite its accepted attempt.

## 7. Atomicity and concurrency control

### 7.1 Single-node MVP

Use a transactional update boundary for related state changes. At minimum, claiming an attempt and incrementing its attempt count must be atomic; accepting an attempt and marking its Work Unit COMPLETED must be atomic; moving the Job to VALIDATING/PUBLISHING must verify all required predecessor states.

The MVP may use a single-writer process model. It must still use explicit state versions and legal-transition validation so concurrency bugs are caught in tests and future backends can implement the same contract.

### 7.2 Future multi-worker mode

The JobStateStore interface must define conditional operations, such as:
- claim a READY Work Unit only if its state/version still matches;
- renew or expire an attempt lease;
- accept one STAGED Attempt only if no other Attempt is accepted;
- advance a Job only if required Work Units and validations are complete;
- record publication outcome idempotently.

A future backend must implement these operations with database transactions, compare-and-swap, conditional writes, or equivalent serializable coordination. A plain object overwrite is not sufficient for shared multi-writer state.

### 7.3 Leases and heartbeats

Leases are not required for the single-process MVP's correctness, but the Attempt model reserves lease owner/expiry fields. In distributed mode, lease expiration permits recovery from lost workers; it does not prove the old worker stopped. Therefore, attempt-specific staging and conditional acceptance remain mandatory even with leases. The lease protocol for distributed mode is defined by ADR-0018.

## 8. Durability and crash recovery

Durability must be specified per transition. A state update that acknowledges a completed Work Unit must be durable before the scheduler treats it as completed. The implementation must document its fsync/transaction commit guarantees.

On restart:
1. Load and validate manifest schema/version.
2. Identify jobs that were non-terminal at shutdown.
3. Reconcile RUNNING attempts whose process/lease is no longer active.
4. Inspect staged outputs and multipart upload state where provider APIs allow it.
5. Verify source identity/version assumptions still hold.
6. Resume only units whose plan and source identity remain valid.
7. Re-run validation for staged outputs if validation evidence is missing or not durable.
8. Never infer publication success solely from a worker's pre-crash in-memory result.

Recovery uses the effective configuration persisted with the job, not the current environment or config file (ADR-0009).

Corrupt or unsupported manifest versions must fail closed with actionable recovery guidance. Do not silently reset state and re-run the whole migration.

## 9. Job failure and explicit resume

Restart recovery (§8) covers a process that died while its job was non-terminal. This section covers a job that reached FAILED or CANCELLED and still holds durably completed Work Units.

### 9.1 Terms

- **Plan generation:** a sealed Plan identified by plan_id and plan_digest. A Job has exactly one plan generation. Re-planning, meaning any change to the source set, schema mapping, split boundaries, output layout, or another input of the plan digest, requires a new Job.
- **Execution generation:** one run of a sealed Plan from READY to a terminal job state. The first run is generation 1. Explicit resume starts the next generation over the same plan generation.

### 9.2 Reaching a terminal job state

Before a job is recorded FAILED or CANCELLED, every Work Unit is brought to a terminal state: units in STAGED or VALIDATING are resolved to COMPLETED or FAILED, and all other non-terminal units are moved to CANCELLED. Attempts still CLAIMED or RUNNING are recorded ABANDONED. When the Scheduler stops a job after a Work Unit failure is defined by ADR-0012; this ADR defines only the resulting states.

### 9.3 What a failed or cancelled job retains

- COMPLETED Work Units stay COMPLETED. Their accepted Attempt, output reference, and validation evidence are immutable and are not rolled back when the job fails.
- Staged objects referenced by an accepted Attempt are retained until the job is published, is explicitly abandoned, or passes its retention period (§12).
- Attempt records from earlier execution generations are retained as immutable history.

### 9.4 Resume preconditions

Resume is an explicit operation (`udc job resume`, ADR-0009). It is never an automatic side effect of starting another job. It is accepted only if all of the following hold; otherwise it is rejected with the failed precondition and the job stays terminal.

1. The job is FAILED or CANCELLED and its plan was sealed. A SUCCEEDED job cannot be resumed, and a job that ended during PLANNING has no sealed plan to resume and must be created again.
2. The persisted manifest, plan, and descriptor versions are supported by the running UDC version, and the running version implements the normalization rules version pinned by the plan (§13).
3. The job specification digest and plan digest are unchanged. Only execution-tuning settings may be overridden; data-semantics settings may not (ADR-0009).
4. Source identity still matches the plan for every Work Unit, including completed ones, under the job's source consistency policy. A changed source object invalidates the plan.
5. Every output object referenced by an accepted Attempt still exists and matches its recorded identity.

### 9.5 Resume transition

Resume performs the following as one atomic state change:

- increments execution_generation and appends an ExecutionGenerationRecord;
- moves the Job from FAILED or CANCELLED to READY;
- moves every FAILED or CANCELLED Work Unit to PENDING;
- leaves every COMPLETED Work Unit untouched.

The job then follows the normal state machine. Work already backed by durable evidence is not repeated:

- COMPLETED Work Units are not re-executed.
- New Attempts get new attempt IDs and staging namespaces. Attempt numbers continue across generations; the retry budget of ADR-0008 starts fresh in each generation.
- Job-level validation evidence is reused only if it covers exactly the current accepted output set; otherwise it is recomputed.
- Publication always begins by reconciling the destination as ADR-0017 defines for the publication mode: the completion marker and the placed objects in Promotion mode, the publication reference in Reference mode. If a commit from an earlier generation is found applied, the job records SUCCEEDED without committing again.

### 9.6 What resume does not cover

- A deterministic Data or Compatibility error recurs on resume unless its cause was outside the plan. If fixing it changes the source or the plan, a new Job is required.
- Reusing completed Work Units across different plans or jobs is deferred. It needs a defined equivalence between Work Units of different plans (source identity, mapping, adapter version, and writer options) and is not part of the MVP.
- Skipping or quarantining failed Work Units in order to publish a partial dataset is not supported. UDC does not publish a dataset with missing required Work Units.

## 10. Checkpoint semantics

A checkpoint is a durable accepted-work boundary, not an arbitrary reader byte offset. The default checkpoint unit is a completed Work Unit whose output reference and validation evidence have been recorded. Sub-unit checkpointing is allowed only when a format adapter can define a safe, deterministic resume position and output ownership semantics.

For a large compressed file, restarting the whole row-group Work Unit may be safer than resuming at an arbitrary byte offset. Checkpoint frequency and unit granularity are therefore coupled to format capabilities.

## 11. Manifest and artifact layout

The logical manifest schema must be independent of its physical storage layout. A reference layout for local execution:

```text
job-root/
  job-record
  plan/
    plan-header
    fragments/
      fragment-000001
      fragment-000002
  work-units/
  attempts/
  validations/
  publication/
  events/
```

The implementation may normalize entities into SQLite tables or use journaled records. Large plan/validation payloads should be separate artifacts referenced by digest/URI. Avoid a single ever-growing job JSON file rewritten after every unit completion.

## 12. Security and retention

- Redact credentials, signed URLs, sensitive object metadata, and customer payload values from manifests and events.
- Treat manifest and plan files as potentially sensitive metadata; apply least-privilege permissions and encryption at rest where available.
- Define retention/cleanup policies for successful jobs, failed attempts, staged outputs, and validation artifacts.
- Cleanup must be reference-aware and conservative: never delete an artifact referenced by an accepted Work Unit or published job.
- Abandoning a job that failed during PUBLISHING must reconcile the publication first (ADR-0017). Objects of a committed publication are never deleted. In Promotion mode, abandoning a publication that is still in progress withdraws the objects it placed, under the rules of ADR-0017.
- A failed or cancelled job can be resumed only while its accepted outputs are retained; the retention period is therefore also the resume window.
- Persist enough sanitized context to diagnose failures without retaining source data unnecessarily.

## 13. Migration and schema evolution

Every persisted manifest has a schema version. Readers must either migrate supported old versions explicitly or reject them with a clear error. Migration must be transactional or create a verified new generation; never partially rewrite a manifest in place.

Plan and Work Unit descriptor versions must also be pinned because a new UDC version may interpret splitting, schema mapping, or output ownership differently. A resumed job must either use a compatible executor or fail with an explicit compatibility error.

The normalization rules version is pinned by the plan for the same reason. Validation evidence recorded under different rules versions cannot be combined (ADR-0006), so a job never mixes them across Work Units or execution generations.

## 14. MVP scope boundary

Required for MVP:
- Persist the Job record and sealed plan identity.
- Persist Work Unit descriptors and terminal completion state.
- Persist Attempt history sufficient to classify and recover interrupted work.
- Resume remaining Work Units after process restart.
- Explicitly resume a FAILED or CANCELLED job over its sealed plan, reusing COMPLETED Work Units.
- Prevent incomplete staged output from being treated as completed output.
- Record validation and publication outcomes.
- Use a single process/single writer for the first local backend.

Deferred beyond MVP:
- Resuming from an arbitrary byte offset or mid-row-group position.
- Multi-process or multi-host simultaneous JobStateStore writers.
- Distributed leases/heartbeats and worker registration.
- Remote state-store backends such as PostgreSQL or shared object-store manifests.
- A built-in distributed Coordinator.
- Reusing completed work across different plans or jobs.
- Publishing a partial dataset that skips failed Work Units.

After restart, the currently incomplete Work Unit may be re-run from its beginning. Work Units whose accepted output and validation evidence were durably recorded must not be needlessly rewritten.

## 15. Validation plan

Build a crash-recovery test harness that terminates execution after each boundary:
1. Job created / plan partially written.
2. Plan sealed / job READY.
3. Attempt claimed.
4. Source read / decode in progress.
5. Output staged / multipart upload in progress.
6. Output upload completed but before Work Unit acceptance.
7. Attempt accepted and Work Unit completed.
8. All Work Units completed before validation.
9. Validation completed before publication.
10. Destination publication committed but before Job SUCCEEDED is recorded.

Verify recovery is idempotent, legal transitions are enforced, stale attempts cannot be accepted, completed Work Units are not rewritten, and published data is not exposed twice or incorrectly marked failed. Also test manifest corruption, incompatible schema versions, disk full, and concurrent state transitions.

Test explicit resume: resume after FAILED and after CANCELLED; rejection when a source object or an accepted output object changed; rejection for an unsupported descriptor version; no re-execution of COMPLETED Work Units; a fresh retry budget in the new generation; and resume of a job that failed during PUBLISHING, with the commit both applied and not applied, and with a promotion that placed only some of its objects.

## 16. Ownership boundary

**Owns:** persisted records, execution generations, state machines and legal transitions, atomicity, durability, restart recovery, and explicit resume. It records validation and publication outcomes and the references needed to reconcile them.

**Does not own:**
- How work is split, scheduled, or budgeted, and when the Scheduler stops a job after a Work Unit failure — ADR-0012. ADR-0012 may specify when the Scheduler calls the State Store, but it must not define a competing state machine.
- Object-storage operations and multipart transfer semantics — ADR-0005.
- Validation algorithms and equivalence guarantees — ADR-0006.
- Retry eligibility and backoff — ADR-0008.
- The generic publication protocol and the Generic Publisher — ADR-0017. The State Store records publication intent and outcome; it does not make output visible.
- Table snapshot, catalog, and commit protocols — ADR-0015. The State Store records the outcome and reconciliation reference; it does not emulate table transactions.
- Telemetry instrumentation and metric cardinality — ADR-0010.
- The distributed backend and its lease protocol — ADR-0018.

## 17. Revisit conditions

Finalize the local backend after comparing SQLite and a local append-only journal for write amplification, recovery time, metadata scale, crash consistency, and operational ergonomics. Revisit the interface before enabling multi-worker mode; distributed state must have its own backend-specific ADR and integration tests.

## 18. Related ADRs

- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0006: Validation Semantics](ADR-0006-validation-semantics.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0009: CLI and Job Configuration](ADR-0009-cli-and-configuration.md)
- [ADR-0010: Observability and Telemetry](ADR-0010-observability.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0015: Table Format Integration Boundary](ADR-0015-table-format-integration-boundary.md)
- [ADR-0017: Output Publication Protocol](ADR-0017-output-publication-protocol.md)
- [ADR-0018: Distributed Job State Store](ADR-0018-distributed-job-state-store.md)
