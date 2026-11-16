# ADR-0018: Distributed Job State Store

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** The future multi-worker JobStateStore backend, its lease protocol, and distributed coordination requirements. Deferred; not part of the MVP.

## 1. Context

ADR-0013 defines the logical JobStateStore contract and requires a local durable implementation for the single-node MVP. ADR-0012 preserves serializable Job and Work Unit contracts for scale-out. A multi-process or multi-node deployment adds concurrent claims, lost workers, duplicate delivery, lease expiry, network partitions, and state-store availability concerns.

A local SQLite database or append-only journal must not be assumed to be a safe shared multi-writer state store. Distributed execution needs a backend with explicit conditional state transitions and a consistency model.

## 2. Decision drivers

1. Correctness under concurrent workers and duplicate task delivery.
2. Atomic claim/lease/attempt acceptance operations.
3. Durable state and recovery under worker/coordinator failure.
4. Strongly defined consistency semantics for state transitions.
5. Operational simplicity proportional to actual distributed scale requirements.
6. Preserve the ADR-0013 logical state model across backend implementations.
7. Avoid coupling Work Unit payload data to the state database.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Shared SQLite / local journal** | Simple and low operational overhead | Not a general multi-host shared transactional store; file locking and shared filesystem semantics are unsuitable assumptions |
| **PostgreSQL or another transactional database** | Transactions, conditional updates, uniqueness constraints, leases and indexes; common operational model | Requires operating and scaling a database; schema and connection management |
| **Object-store manifest with conditional writes** | Durable cloud-native storage; low operational overhead | Conditional mutation and consistency vary; high-frequency state transitions and lease contention may be awkward |
| **Dedicated distributed key-value store** | Potentially high throughput and conditional operations | Additional operational dependency; consistency/transaction capabilities differ by product |
| **Coordinator-owned in-memory state with worker RPC** | Simple worker protocol initially | Coordinator failure loses authority unless backed by durable state; not sufficient alone |

## 4. Proposed decision

Do not implement a distributed state store in the MVP. When multi-worker execution becomes a requirement, select a transactional or conditional-write backend that can implement the ADR-0013 JobStateStore contract. PostgreSQL is the initial baseline candidate for evaluation; object-store-based state is an alternative for low-contention metadata, not presumed equivalent to a transactional database.

The logical state model and transition semantics remain owned by ADR-0013. This ADR selects the future deployment/backend model and its distributed coordination requirements only.

## 5. Rationale

The MVP is single-node and a distributed store has a real operating cost, so none is built until a trigger in §9 is met. This ADR exists now for a different reason: the single-node design must not make choices that a distributed backend cannot honor. Recording the required capabilities (§6) and the lease rules (§7) fixes what the JobStateStore contract of ADR-0013 has to allow.

Among the options, a shared SQLite file or journal is not a safe multi-host store, and state held in a coordinator's memory is not durable. A transactional database provides the conditional transitions, uniqueness constraints, and bounded queries that §6 lists, with an operating model that is widely understood. That is why PostgreSQL is the baseline for evaluation. Object-store manifests remain an alternative for low-contention metadata, because their conditional-write semantics vary and a transition for every Attempt is frequent.

## 6. Required distributed capabilities

A backend must support, directly or through a safe transaction:
- atomic claim of a READY Work Unit conditioned on state/version;
- attempt creation and attempt-count increment in the same transaction;
- lease owner/expiry and conditional heartbeat renewal;
- lease expiry/recovery without assuming the old worker has stopped;
- acceptance of exactly one validated Attempt for a Work Unit;
- atomic transition of Work Unit to COMPLETED with accepted output reference;
- idempotent publication-intent/result recording;
- the resume transition of ADR-0013 (a new execution generation plus Work Unit resets) as one atomic operation;
- bounded queries for ready, retryable, and expired-lease units;
- schema migration and backup/restore procedures;
- visibility/consistency semantics documented for reads after writes.

## 7. Lease and duplicate-delivery protocol

A lease gives a worker temporary authority to attempt a Work Unit; it does not guarantee single execution. A paused or partitioned worker may continue after its lease expires. Therefore:

1. Every attempt writes to a unique staging namespace.
2. Lease heartbeat uses owner token and state version; stale owners cannot renew.
3. Lease expiry makes a unit eligible for a new Attempt but does not accept or delete the old attempt output.
4. The State Store conditionally accepts one validated Attempt.
5. Late completion from an expired attempt is rejected.
6. Cleanup of rejected attempt output is asynchronous and reference-aware.

Fencing tokens or monotonic state versions should be used where a downstream resource can reject stale writers. If a destination cannot enforce fencing, attempt-isolated output plus conditional acceptance at the state store remains mandatory.

## 8. Consistency and availability

Job state transitions require a consistency level strong enough to prevent two workers from both claiming or accepting the same unit. Eventually consistent listing alone is not a sufficient claim/acceptance primitive.

Temporary state-store unavailability must stop new admission and must not cause workers to publish outputs independently. Workers may finish an already running isolated attempt, but acceptance and publication wait until authoritative state can be updated.

## 9. Adoption triggers

Distributed State Store selection is triggered only when at least one of the following is demonstrated:
- single-node CPU/network resources are saturated and throughput needs more nodes;
- dataset or tenant throughput requires independent worker pools;
- job runtime or availability requirements exceed a single host's failure domain;
- users require remote workers as a supported deployment mode.

Do not add distributed state merely to claim horizontal scalability. Until this ADR is accepted and implemented, UDC supports single-node durable execution only.

## 10. Trade-offs and consequences

- Deferral means no horizontal scale. Throughput is bounded by one machine until this ADR is accepted and implemented.
- Designing for a future backend constrains the MVP. Attempt records carry lease fields that the single-process store does not need.
- A transactional database is an operational dependency, with deployment, backup, and migration, for anyone who adopts distributed mode.
- Leases do not prevent duplicate execution. Attempt-isolated staging and conditional acceptance stay mandatory, at the cost of extra storage and cleanup.
- When the state store is unavailable, admission and publication stop. Consistency is preferred to availability.
- The requirements in this ADR are not validated by an implementation and may change with the first prototype.

## 11. Validation plan

Run concurrent-claim tests, duplicate delivery, worker pause beyond lease expiry, split-brain/stale worker completion, coordinator restart, state-store failover, network partitions, transaction conflicts, and publication acknowledgement loss. Verify only one Attempt becomes accepted and no worker can make data visible except through the Generic Publisher (ADR-0017) or a table-native commit (ADR-0015).

Benchmark transition throughput and query latency at realistic Work Unit cardinalities. Include backup, restore, migration, and operational cost in the decision.

## 12. Ownership boundary

**Owns:** selection of a distributed JobStateStore backend, the lease and duplicate-delivery protocol, and the consistency and availability requirements of distributed coordination.

**Does not own:**
- The logical state model, legal transitions, and the resume contract — ADR-0013. A distributed backend implements them unchanged.
- The MVP local backend — ADR-0013.
- Scheduling policy and the worker contract — ADR-0012.
- Making output visible — ADR-0017.

## 13. Revisit conditions

Accept a concrete backend only when the project commits to multi-worker execution. Record the selected DB/product, transaction isolation assumptions, schema/index design, retention policy, backup/restore, availability target, and operational responsibilities in a superseding ADR or this ADR's accepted revision.

## 14. Related ADRs

- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0015: Table Format Integration Boundary](ADR-0015-table-format-integration-boundary.md)
- [ADR-0017: Output Publication Protocol](ADR-0017-output-publication-protocol.md)
