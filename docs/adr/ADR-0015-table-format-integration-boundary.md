# ADR-0015: Table Format Integration Boundary

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Priority:** P0

## 1. Context

Table formats such as Iceberg, Delta Lake, Hudi, and Lance Table are not merely file layouts. Their correctness depends on table metadata, snapshots or timelines, schema/partition evolution, delete semantics, manifests or fragments, catalog state, and commit protocols. A file conversion pipeline can rewrite data files while still corrupting the logical table if it ignores these structures.

UDC therefore needs a clear boundary between File Format Adapter, Table Format Adapter, Catalog Adapter, Storage Adapter, and the conversion execution pipeline.

## 2. Decision drivers

1. Never report a file rewrite as a table migration unless table semantics are preserved.
2. Reuse protocol implementations and commit logic from established libraries.
3. Keep format-level decoding separate from table-level snapshot and transaction semantics.
4. Represent per-format feature coverage explicitly.
5. Ensure readers operate on a declared table snapshot or timeline state.
6. Avoid bypassing concurrent-writer conflict detection and atomic commits.
7. Allow file conversion to remain useful without a catalog or table-format dependency.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Treat table formats as file formats with extra metadata files** | Superficially simple | Incorrectly ignores snapshots, deletes, commits, and catalog semantics |
| **UDC implements all table protocols itself** | Full product-level control | Very high protocol and compatibility maintenance burden |
| **Dedicated TableFormatAdapter backed by mature protocol libraries** | Correct separation; reuses existing semantics; explicit capability support | Library maturity and feature coverage vary; integration boundaries can be complex |
| **Delegate table operations entirely to external engines** | Reuses engine integrations and table connectors | Couples UDC semantics to engine behavior; may not expose required metadata/commit controls |

## 4. Proposed decision

Introduce a dedicated **TableFormatAdapter** boundary that composes with, but is distinct from, FileFormatAdapter and CatalogAdapter. Reuse established table-format implementations wherever practical. UDC owns job orchestration, cross-format mapping policy, validation policy, and publication coordination; the underlying table implementation remains authoritative for protocol-specific snapshot/commit correctness.

No table format is considered fully supported by a generic file adapter alone.

## 5. Responsibility boundaries

### 5.1 TableFormatAdapter owns

- open table at a declared snapshot/ref/timeline instant;
- inspect table metadata, schema, partition spec, sort/order metadata, and supported features;
- enumerate live data files/fragments and associated delete/index/metadata artifacts;
- expose row-level delete and deletion-vector semantics where relevant;
- expose format-native safe data-file rewrite inputs;
- prepare and commit table changes through the native transaction protocol;
- detect commit conflicts and report them without silently overwriting concurrent changes;
- report protocol and library version compatibility.

### 5.2 FileFormatAdapter owns

- decode/encode physical data files;
- expose physical schema, reader/writer, compression, and safe split capabilities;
- produce staged data files for a table operation when requested by the TableFormatAdapter.

### 5.3 CatalogAdapter owns

- table discovery, registration, namespace and catalog protocol operations;
- credential/endpoint handling through ADR-0016;
- catalog-level conditional or transactional behavior where the catalog protocol provides it.

### 5.4 StorageAdapter owns

- bytes, object versions/ETags, range reads, uploads, listing, and provider operations (ADR-0005).

### 5.5 Job orchestration owns

- planning work units from the table adapter's snapshot-bound descriptors;
- coordinating file rewrite and validation tasks;
- recording progress and commit outcomes through ADR-0013;
- invoking the table adapter's commit only after required validation succeeds.

## 6. Snapshot and consistency model

A table read must be bound to an explicit snapshot, ref, timeline instant, or other table-native consistency point where supported. Work Units must refer to immutable data-file identities from that captured table view. New data committed after planning must not be silently mixed into the current job.

If a format/library cannot provide a stable read view, the adapter must document the weaker consistency guarantee and the job must require explicit user acceptance before destructive rewrite.

## 7. Commit and publication semantics

Table publication is not equivalent to moving files into a destination prefix. The TableFormatAdapter must validate the planned base snapshot/ref, stage new data and metadata, and use the native commit protocol. Concurrent modification conflicts must fail or trigger an explicitly designed rebase/replan path; they must not be hidden by overwriting catalog pointers.

ADR-0017 defines the generic file-output publication protocol. This ADR owns table-native commit semantics. ADR-0013 records commit intent/result and crash-recovery references but does not implement the table transaction.

## 8. Capability model

Expose feature capabilities independently, including:
- snapshot/ref/timeline read support;
- metadata and schema/partition evolution inspection;
- data-file enumeration;
- row-level delete semantics;
- equality/position deletes or deletion vectors;
- index/fragment management;
- data-file rewrite;
- atomic/optimistic commit;
- catalog integration;
- concurrent commit conflict detection;
- protocol feature versions.

Capabilities must be tested by version and not inferred solely from the format name.

## 9. MVP boundary

The MVP may support file conversion and read-only table inspection. It does not claim full Iceberg/Delta/Hudi/Lance table migration. A destructive table rewrite requires a format-specific adapter and integration tests for snapshot pinning, deletes, conflict detection, and commit recovery.

## 10. Validation plan

For each table adapter, test:
- opening an exact snapshot/ref/timeline and excluding later commits;
- schema and partition evolution;
- live-file enumeration with deletes applied correctly;
- staging data files without exposing them as committed table state;
- successful native commit;
- concurrent writer conflict;
- crash before and after commit acknowledgement;
- idempotent reconciliation when commit succeeded but the client lost the response.

## 11. Revisit conditions

Revisit when UDC chooses a table format for a production migration release or when an existing library cannot expose the required commit/snapshot controls.

## Related ADRs

- [ADR-0003: Canonical Data Model and Schema Compatibility](ADR-0003-canonical-data-model.md)
- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0006: Validation Semantics](ADR-0006-validation-semantics.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0016: Cloud Authentication and Credential Resolution](ADR-0016-cloud-authentication.md)
- [ADR-0017: Output Publication Protocol](ADR-0017-output-publication-protocol.md)
