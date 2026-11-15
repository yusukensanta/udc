# ADR-0001: Initial Architecture Principles

- **Status:** Accepted
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** Architecture principles, the responsibility map, shared vocabulary, and the rules for resolving conflicts between ADRs. Detailed contracts are owned by the focused ADRs listed in the scope map.

## 1. Context

UDC must support file conversion, cross-cloud data movement, validation, and eventually table-format interoperability. These capabilities span concerns with different lifecycles and semantics: physical encodings, logical types, object storage, table transactions, execution, and job orchestration.

The initial design must keep the MVP operable as a local tool while avoiding abstractions that prevent later integrations. Technology choices should be justified against explicit decision drivers and recorded in focused ADRs. This ADR establishes architectural boundaries; it does not select every implementation library.

## 2. Decision drivers

1. Preserve data semantics and make lossy conversions explicit.
2. Keep the core portable across clouds and execution engines.
3. Bound memory use and support streaming/backpressure.
4. Reuse mature protocol and format implementations.
5. Keep the MVP easy to run, test, and contribute to.
6. Make implementation maturity and unsupported capabilities visible.

## 3. Decisions

### 3.1 Use a modular Rust codebase for the initial implementation

Rust is the initial implementation language. This is a project-level direction, not a claim that Rust is universally superior for data systems. The rationale and alternatives are recorded in [ADR-0002](ADR-0002-rust-implementation-language.md).

### 3.2 Separate logical semantics from physical and execution representations

UDC will not treat a physical file schema or an in-memory vector schema as the complete definition of a dataset's meaning. A canonical logical model will represent meaning and conversion constraints; physical format schemas and execution representations will be mapped to and from it. See [ADR-0003](ADR-0003-canonical-data-model.md).

### 3.3 Keep architectural responsibilities independent

Each concern has one owner. The table states what the concern owns, what it must not own, and the ADR that holds its contract.

| Concern | Owns | Must not own | Authoritative ADR |
|---|---|---|---|
| Canonical logical schema | Logical type semantics, compatibility outcomes, and the schema mapping plan | Physical decoding or batch execution | ADR-0003 |
| File-format adapter | Physical inspection, decode/encode, format metadata, and safe split and streaming capabilities | Global scheduling, job state, retry policy, or publication | ADR-0014 |
| Table-format adapter | Table snapshot, metadata, deletes, indexes, and native commit semantics | Generic file conversion or generic file publication | ADR-0015 |
| Catalog adapter | Table discovery, registration, and catalog protocol | Job lifecycle | None yet; boundary sketched in ADR-0015 |
| Storage adapter | Object bytes, range reads, listing, multipart primitives, and provider capabilities | Credential policy, durable job state, or dataset-level visibility | ADR-0005 |
| Credential resolution | Provider identity selection and refresh integration | Object I/O or CLI syntax | ADR-0016 |
| Execution backend | Batch processing and optional transformations | Job/Attempt lifecycle or final publication | ADR-0004 |
| Validation | Meaning and evidence of correctness checks | Scheduling or durable state | ADR-0006 |
| Runtime | Async runtime and bounded runtime primitives | Scheduling policy, resource-budget policy, or durable state | ADR-0007 |
| Error handling | Error taxonomy, retry eligibility, and backoff rules | Persisting attempts or accepting output | ADR-0008 |
| CLI and configuration | User-facing commands, configuration format, and configuration precedence | Internal job-state representation or credential resolution | ADR-0009 |
| Observability | Instrumentation, cardinality and redaction rules, and export | The job state machine | ADR-0010 |
| Orchestration | Planning, work-unit scheduling, worker contract, resource budgets, job failure policy, and the point at which validation and publication are invoked | Persisted state schema, storage consistency semantics, validation semantics, or the publication protocol | ADR-0012 |
| Job State Store | Durable Job/Plan/Work Unit/Attempt/Publication records, legal transitions, atomic acceptance, recovery, and explicit resume | Dataset payload I/O, format decoding, or table transactions | ADR-0013 |
| Generic Publisher | File/dataset staging layout, output manifest, and publication modes with their guarantees | Table-native transactions, or inventing atomic rename | ADR-0017 |
| Packaging and distribution | Distribution channels, official targets and feature set, crate and binary naming, release pipeline, and the public-release gate | Cargo feature mechanics, or persisted-state versioning | ADR-0019 |

### 3.4 Reuse mature implementations instead of reimplementing protocols

UDC should wrap or integrate established libraries where their feature coverage and licensing are acceptable. An adapter must expose the supported feature set and known limitations; a dependency's existence does not mean that UDC supports every feature of the underlying specification.

### 3.5 Start as a modular monolith with statically linked integrations

The initial deliverable should be a single deployable CLI/library with internal crate boundaries. Dynamic plugin loading and distributed services are deferred until a concrete compatibility or operational requirement justifies their costs.

## 4. Authoritative ADR scope map

| ADR | Authoritative scope | Explicitly out of scope |
|---|---|---|
| 0001 | Architecture principles, responsibility map, shared vocabulary, conflict-resolution rules | Detailed implementation protocol |
| 0002 | Core implementation language | Runtime, libraries, execution architecture |
| 0003 | Canonical logical schema, compatibility outcomes, and schema mapping plan | Arrow buffer execution and validation algorithms |
| 0004 | Execution backend capabilities and selection | Job orchestration and durable state |
| 0005 | Data object storage operations and provider capabilities | Identity resolution, job state transitions, and dataset visibility |
| 0006 | Validation levels, normalization, equivalence guarantees, and the transfer-integrity distinction | Job state and retry classification |
| 0007 | Async runtime and runtime-level concurrency primitives | Work scheduling policy, resource-budget policy, and durable state |
| 0008 | Error taxonomy, error codes, and retry eligibility/backoff | Persisting attempt state, output acceptance, job failure policy, and resume |
| 0009 | CLI, user configuration, and configuration precedence | Internal job state representation and credential resolution |
| 0010 | Telemetry instrumentation and export | Business state machine |
| 0011 | Workspace/dependency/feature graph, and which crates are published | Runtime architecture decisions, per-concern library selection, crate naming, and what the official binary contains |
| 0012 | Job planning, work-unit granularity, scheduler policy, worker contract, resource budgets, job failure policy, and the point at which validation and publication are invoked | Persisted state schema, legal state transitions, resume, and the publication protocol |
| 0013 | Job/Plan/Work Unit/Attempt/Publication records, execution generations, state transitions, atomicity, durability, single-node recovery, and explicit resume | Data I/O and scheduling policy; distributed backend selection |
| 0014 | File-format adapter contract, safe splits, streaming reader/writer capabilities | Job scheduling and retry/state |
| 0015 | Table-format adapter boundary, snapshot semantics, native table commits, and plain-file-to-table operations | Generic file-output publication |
| 0016 | Cloud identity resolution, credential source, and refresh policy | Object byte operations and CLI syntax |
| 0017 | Generic Publisher: file/dataset staging layout, output manifest, publication modes and their guarantees, reconciliation, and staging cleanup rules | Table-native transaction protocol; when publication is invoked |
| 0018 | Future multi-worker JobStateStore backend, leases, and distributed coordination | Logical state model and MVP local backend |
| 0019 | Distribution channels, official binary targets and feature set, crate and binary naming, release pipeline and provenance, upgrade communication, and the public-release gate | Cargo feature mechanics, persisted-state migration, and per-concern library selection |

## 5. Shared vocabulary

All project documents use these terms with the meaning given by the defining ADR. An ADR that needs a different meaning must define a new term instead of reusing one of these.

| Term | Meaning | Defined by |
|---|---|---|
| Job | Immutable user intent plus execution policy for one conversion or migration | ADR-0012 (concept), ADR-0013 (record) |
| Plan, plan generation | The sealed, immutable, digest-identified description of the work for a Job. A Job has exactly one plan generation; re-planning requires a new Job | ADR-0012 (concept), ADR-0013 (record) |
| Execution generation | One run of a sealed Plan from READY to a terminal job state. Explicit resume starts a new execution generation over the same plan generation | ADR-0013 |
| Work Unit | The smallest independently schedulable and retryable unit with a defined input boundary and output ownership | ADR-0012 |
| SplitDescriptor | An adapter-provided safe input boundary, wrapped by a Work Unit | ADR-0014 |
| Attempt | One execution of a Work Unit, writing to its own staging namespace | ADR-0012 (concept), ADR-0013 (record) |
| Acceptance | The durable, conditional selection of exactly one validated Attempt as a Work Unit's output | ADR-0013 |
| Checkpoint | A durable accepted-work boundary: a completed Work Unit | ADR-0013 |
| JobStateStore | The interface that holds authoritative orchestration state | ADR-0013 |
| Job manifest | The versioned persisted records held by the JobStateStore. Not the output manifest | ADR-0013 |
| Staging | An attempt-scoped, immutable output location outside the destination prefix, which is not part of the published view | ADR-0017 |
| Output manifest | The immutable list of the exact accepted output objects that one publication makes visible | ADR-0017 |
| Publication | Making a validated output set visible, in a publication mode for generic output or through a native commit for a table | ADR-0017 (generic), ADR-0015 (table) |
| Publication mode | How the objects of an output manifest become visible, and the guarantee that may be claimed: Promotion mode (validated before visible, for consumers that list a prefix) or Reference mode (all or nothing, for consumers that read a publication reference) | ADR-0017 |
| Generic Publisher | The component that executes the generic file/dataset publication protocol | ADR-0017 |
| Validation level (L1–L5) | A named level of validation evidence | ADR-0006 |
| Normalization rules | The published, versioned specification of the canonical form of a logical value and of when two logical values are equal. The normalization policy is a job's selection among the choices a rules version allows | ADR-0006 |
| Transfer integrity | A physical byte checksum of a stored or copied object. Not a validation level | ADR-0006 |
| Error category | A stable class of failure with a default retry disposition | ADR-0008 |
| Capability descriptor | An explicit, versioned statement of what an adapter or backend guarantees | ADR-0014, ADR-0015, ADR-0005, ADR-0004 |

## 6. Normative cross-ADR rules

1. Each concern has one authoritative ADR as shown in the scope map. Other ADRs may reference it but must not redefine its normative contract.
2. Proposed decisions are not finalized dependencies. The PRD and README must preserve decision status.
3. The MVP requires durable Work Unit completion, safe restart recovery, and explicit resume of a failed or cancelled job over its sealed plan. Partial progress inside a Work Unit, reuse of completed work across plans, and distributed resume are future capabilities.
4. Execution is at-least-once. Safe effects rely on attempt-isolated staging, conditional acceptance, validation, and controlled publication; exactly-once task execution is not promised.
5. ADR-0012 owns resource-budget policy and scheduling. ADR-0007 owns the runtime primitives used to enforce it.
6. ADR-0013 owns durable state transitions, recovery, and resume. ADR-0012 must not define a competing state machine.
7. ADR-0005 owns object-storage semantics. ADR-0013 may require conditional state operations but cannot assume they are supplied by an object store.
8. Table-format publication must use the table format's commit protocol; the Generic Publisher cannot bypass it.
9. ADR-0014 defines format-specific split/reader/writer capabilities; ADR-0012 consumes them but cannot invent unsafe split boundaries.
10. ADR-0015 owns table snapshot and native commit semantics. ADR-0017 applies only to generic file/dataset publication.
11. ADR-0016 owns cloud identity resolution; ADR-0005 owns object operations using the resolved provider client.
12. ADR-0013 owns the logical state contract and MVP local durability. ADR-0018 only selects a future distributed backend and coordination protocol; it cannot redefine ADR-0013's entity/state semantics.
13. ADR-0017 is the only definition of the Generic Publisher and its protocol. ADR-0012 decides only when the job workflow invokes publication.
14. ADR-0006 owns the validation level names (L1–L5) and what each establishes. A physical checksum is a transfer-integrity check, not a validation level, and must not be reported as evidence of logical equivalence.
15. ADR-0008 owns error categories and retry disposition. Other documents reference those categories instead of defining their own lists.
16. ADR-0009 owns configuration precedence. A recovered or resumed job uses the effective configuration persisted under ADR-0013, not the current environment.
17. ADRs carry no priority labels. Capability priority (P0–P3) and roadmap phases (Phase 0–8) are defined only in the PRD.
18. ADR-0019 owns what the official binary contains, which targets are built, and crate naming. ADR-0011 owns which crates are published and how crates and Cargo features are arranged to produce the official binary.

When ADRs appear to conflict, the authoritative owner in the scope map takes precedence and dependent ADRs must be amended to reference it.

## 7. Rationale

A modular monolith minimizes deployment and operational complexity while still allowing compile-time boundaries and independent testing. Separating logical semantics from physical encodings avoids coupling correctness to the accidental capabilities of any one file format or engine. Reusing existing implementations reduces protocol-maintenance risk, while explicit capability reporting prevents a thin integration from being mistaken for complete support.

## 8. Options considered

### 8.1 One execution framework owns the whole product

Rejected as the architectural default because it would couple storage, format support, execution, and table semantics to a single framework and its release cadence.

### 8.2 A distributed microservice architecture from the beginning

Rejected because it adds deployment, RPC, and operational complexity before the MVP has demonstrated a need for independent scaling or remote control planes.

### 8.3 Implement all format and table protocols in UDC

Rejected because it duplicates mature ecosystem implementations and creates a large ongoing compatibility burden.

## 9. Trade-offs and consequences

- More interfaces and mapping code are required than in a single-framework implementation.
- Different backends may support different subsets of operations; UDC needs capability negotiation rather than pretending all backends are equivalent.
- Rust dependencies and cloud SDK maturity must be checked per integration.
- Modular boundaries can become over-engineered; abstractions should be introduced around demonstrated variation, not speculative extension points.
- Some table-format operations cannot be safely implemented as generic file conversion.
- The catalog adapter has a boundary but no contract yet; a dedicated ADR is required before a catalog integration is implemented.

## 10. Validation plan

- The MVP must run locally without a mandatory control plane.
- A format conversion path must be testable independently of table-format transaction handling.
- Core tests must be able to use local/fake storage without cloud credentials.
- Unsupported format or table features must fail explicitly, not silently degrade.

## 11. Ownership boundary

**Owns:** architecture principles, the responsibility map, the ADR scope map, shared vocabulary, and cross-ADR conflict resolution.

**Does not own:** any detailed contract. Each one belongs to the ADR named in the scope map (ADR-0002 through ADR-0019).

## 12. Revisit conditions

Revisit this ADR if the modular monolith prevents independent scaling, if Rust ecosystem limitations block core requirements, or if evidence shows that the chosen boundaries create more complexity than they remove.

## 13. Related ADRs

- [ADR-0002: Rust as the Implementation Language](ADR-0002-rust-implementation-language.md)
- [ADR-0003: Canonical Data Model and Schema Compatibility](ADR-0003-canonical-data-model.md)
- [ADR-0004: Execution Engine Selection](ADR-0004-execution-engine-selection.md)
- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0006: Validation Semantics](ADR-0006-validation-semantics.md)
- [ADR-0007: Async Runtime and Concurrency Control](ADR-0007-async-runtime-and-concurrency.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0009: CLI and Job Configuration](ADR-0009-cli-and-configuration.md)
- [ADR-0010: Observability and Telemetry](ADR-0010-observability.md)
- [ADR-0011: Dependency and Feature Management](ADR-0011-dependency-and-feature-management.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0014: File Format Adapter Contract](ADR-0014-file-format-adapter-contract.md)
- [ADR-0015: Table Format Integration Boundary](ADR-0015-table-format-integration-boundary.md)
- [ADR-0016: Cloud Authentication and Credential Resolution](ADR-0016-cloud-authentication.md)
- [ADR-0017: Output Publication Protocol](ADR-0017-output-publication-protocol.md)
- [ADR-0018: Distributed Job State Store](ADR-0018-distributed-job-state-store.md)
- [ADR-0019: Packaging, Release, and Distribution](ADR-0019-packaging-and-distribution.md)
