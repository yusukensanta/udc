# ADR-0015: Table Format Integration Boundary

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** The TableFormatAdapter boundary: table snapshot and consistency semantics, the table capability model, native table commits, and the operations that connect plain-file datasets to tables.

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
8. Do not duplicate metadata-only operations that the table formats' own tooling already provides.

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

## 5. Rationale

Treating a table as files with additional metadata is the failure this ADR exists to prevent: the rewritten files can be valid while the table is wrong. Implementing the protocols inside UDC would take on the compatibility burden of every table format and its evolving features. Delegating table operations entirely to an external engine would hand that engine the decisions UDC is positioned on, namely what is validated and when a commit happens ([PRD §2.5](../PRD.md#25-existing-tools-and-where-udc-fits)).

A dedicated adapter over an established library leaves protocol correctness with the implementation that the format's community maintains, and keeps orchestration, validation, and the timing of the commit in UDC. Keeping the TableFormatAdapter apart from the FileFormatAdapter and the CatalogAdapter means that file conversion works with no catalog or table dependency, and that table support is stated capability by capability (§9) instead of being implied by the ability to read the data files.

## 6. Responsibility boundaries

### 6.1 TableFormatAdapter owns

- open table at a declared snapshot/ref/timeline instant;
- inspect table metadata, schema, partition spec, sort/order metadata, and supported features;
- enumerate live data files/fragments and associated delete/index/metadata artifacts;
- expose row-level delete and deletion-vector semantics where relevant;
- expose format-native safe data-file rewrite inputs;
- prepare and commit table changes through the native transaction protocol;
- detect commit conflicts and report them without silently overwriting concurrent changes;
- report protocol and library version compatibility.

### 6.2 FileFormatAdapter owns

- decode/encode physical data files;
- expose physical schema, reader/writer, compression, and safe split capabilities;
- produce staged data files for a table operation when requested by the TableFormatAdapter.

### 6.3 CatalogAdapter owns

- table discovery, registration, namespace and catalog protocol operations;
- credential/endpoint handling through ADR-0016;
- catalog-level conditional or transactional behavior where the catalog protocol provides it.

No ADR owns the CatalogAdapter contract yet. This subsection fixes only its boundary with the TableFormatAdapter; a dedicated ADR is required before a catalog integration is implemented. That ADR must decide at least:

- the CatalogAdapter's responsibilities and non-goals, and its boundary with the TableFormatAdapter and the StorageAdapter;
- table identity and namespace resolution, stable across resume;
- how table metadata is read, and how the native commit is coordinated without bypassing the catalog's concurrency control;
- credential acquisition and refresh through ADR-0016, with no secret persisted in job state;
- error mapping to ADR-0008, including the outcome when table metadata changes during a job;
- the first catalog to support and the reason, or that the choice waits for the evidence of PRD §13.3 (H5);
- integration tests for a successful append, a commit conflict, retry or re-planning, and recovery of an ambiguous commit outcome.

### 6.4 StorageAdapter owns

- bytes, object versions/ETags, range reads, uploads, listing, and provider operations (ADR-0005).

### 6.5 Job orchestration owns

- planning work units from the table adapter's snapshot-bound descriptors;
- coordinating file rewrite and validation tasks;
- recording progress and commit outcomes through ADR-0013;
- invoking the table adapter's commit only after required validation succeeds.

## 7. Snapshot and consistency model

A table read must be bound to an explicit snapshot, ref, timeline instant, or other table-native consistency point where supported. Work Units must refer to immutable data-file identities from that captured table view. New data committed after planning must not be silently mixed into the current job.

If a format/library cannot provide a stable read view, the adapter must document the weaker consistency guarantee and the job must require explicit user acceptance before destructive rewrite.

## 8. Commit and publication semantics

Table publication is not equivalent to moving files into a destination prefix. The TableFormatAdapter must validate the planned base snapshot/ref, stage new data and metadata, and use the native commit protocol. Concurrent modification conflicts must fail or trigger an explicitly designed rebase/replan path; they must not be hidden by overwriting catalog pointers.

ADR-0017 defines the generic file-output publication protocol. This ADR owns table-native commit semantics. ADR-0013 records commit intent/result and crash-recovery references but does not implement the table transaction.

## 9. Capability model

Expose feature capabilities independently, including:
- snapshot/ref/timeline read support;
- metadata and schema/partition evolution inspection;
- data-file enumeration;
- row-level delete semantics;
- equality/position deletes or deletion vectors;
- index/fragment management;
- data-file rewrite;
- table creation;
- append commit of new data files;
- atomic/optimistic commit;
- catalog integration;
- concurrent commit conflict detection;
- protocol feature versions.

Capabilities must be tested by version and not inferred solely from the format name.

## 10. Plain-file datasets and tables

A common migration is not table to table but plain files to a table. This section fixes what UDC does on that path and what it leaves to existing tools.

### 10.1 What UDC does not do

UDC does not reimplement metadata-only adoption of existing files. Registering Parquet files in place, building a table log over an existing directory, and translating one table format's metadata into another's are already provided by the table formats' own tooling: Iceberg `migrate`, `snapshot`, and `add_files`, Delta Lake `CONVERT TO DELTA`, Apache XTable, and Delta UniForm. These operations do not read row data, so UDC's conversion and validation machinery adds nothing to the registration step itself.

UDC adds value on this path only where row data is read, checked, or rewritten. That gives three operations.

### 10.2 Compatibility check before registration

A read-only operation that classifies existing plain files against a table schema before another tool registers them.

- Input: a plain-file dataset, and either an existing table at a pinned snapshot or a declared schema and partition spec for a table that does not exist yet.
- Output: for each file, the classification of every field under ADR-0003, the presence or absence of the field identity the table format needs, and whether the partition values implied by the file's location agree with the partition spec.
- UDC does not register the files. The report is the product of this operation.

This addresses a documented gap: Iceberg's `add_files` states that it does not analyze the schema of the files to determine whether they match the table schema.

### 10.3 Dataset-to-snapshot validation

A read-only operation that compares a plain-file dataset with a pinned table snapshot, whichever tool produced the table.

- When the table's data was rewritten, the comparison uses the validation levels of ADR-0006, with the table side read at the pinned snapshot.
- When the files were registered in place, a logical comparison of a file with itself proves nothing. The meaningful check is the **registered file-set check**: the snapshot's live data files are exactly the intended files, none missing and none registered twice. It is reported as a table-level check and never as a validation level.
- If the snapshot carries row-level deletes that the adapter cannot apply, the operation is refused. It is not approximated.

### 10.4 Validated ingestion

A write operation that converts plain files into data files of a table and commits them, when the data has to be rewritten: CSV or JSON sources, Parquet that needs a schema mapping or a different partitioning, or data that has to move to another storage system.

1. Plan against a new table or the pinned base snapshot of an existing table. Classify the mapping against the table schema before any data moves (ADR-0003).
2. Convert each Work Unit into staged data files under the table's data location. The files are not part of the table, because no snapshot references them.
3. Validate the staged files against the source (ADR-0006).
4. Commit exactly the accepted files in one append through the native protocol, only after the required validation has succeeded.
5. Record the commit intent and outcome through ADR-0013.

Requirements:

- The initial scope is append only: create a table, or append to an existing one. Overwrite, replace, delete, upsert, and schema or partition evolution as part of the job are outside it.
- A resumed job reuses accepted data files and commits once. Before committing, it confirms that every accepted file still exists: table maintenance that removes unreferenced files can delete the staged files of a paused or long-running job.
- A commit conflict follows §8. An append may be retried on a refreshed base snapshot only when the table schema and partition spec that the plan was classified against are unchanged; otherwise the job fails and must be re-planned.
- An ambiguous commit outcome is reconciled by looking for the job's commit identity in the table history, never by committing again blindly.
- UDC removes the unreferenced files it wrote when a job fails or is cancelled without a commit.

### 10.5 Order and prerequisites

The read-only operations (§10.2, §10.3) need snapshot read, metadata inspection, and data-file enumeration from §9. Validated ingestion additionally needs table creation, append commit, conflict detection, and catalog integration, and therefore the CatalogAdapter ADR required by §6.3.

Iceberg is the first target. The same three operations apply to other table formats, but none is scheduled for them.

## 11. MVP boundary

The MVP may support file conversion and read-only table inspection. It does not claim full Iceberg/Delta/Hudi/Lance table migration, and it does not include the operations in §10. A destructive table rewrite requires a format-specific adapter and integration tests for snapshot pinning, deletes, conflict detection, and commit recovery.

## 12. Trade-offs and consequences

- Leaving registration to other tools means a migration of files in place uses two tools: UDC to check, and the table format's tooling to register.
- Validated ingestion rewrites data even when the source is Parquet. It is the wrong choice when the files are already compatible and in place; §10.2 followed by registration is cheaper.
- Staged files inside a table's data location are exposed to that table's maintenance operations until they are committed.
- One append per job keeps the result atomic but delays visibility until the whole job has been validated.
- Each operation is limited by what the underlying table library can do. A capability the library lacks is reported as unsupported, not emulated.

## 13. Validation plan

For each table adapter, test:
- opening an exact snapshot/ref/timeline and excluding later commits;
- schema and partition evolution;
- live-file enumeration with deletes applied correctly;
- staging data files without exposing them as committed table state;
- successful native commit;
- concurrent writer conflict;
- crash before and after commit acknowledgement;
- idempotent reconciliation when commit succeeded but the client lost the response.

For the plain-file operations in §10, test:
- a compatibility report that flags a type mismatch, a missing field identity, and a partition value that disagrees with the file's location;
- a registered file-set check that detects a missing file and a file registered twice;
- refusal of dataset-to-snapshot validation when the snapshot carries deletes the adapter cannot apply;
- validated ingestion that leaves the table unchanged when validation fails;
- resume after a crash between validation and commit, with exactly one commit as the result;
- detection of a staged file removed before the commit;
- removal of unreferenced files after a failed or cancelled job.

## 14. Ownership boundary

**Owns:** the TableFormatAdapter boundary, snapshot and consistency semantics for table reads, the table capability model, table-native commit and conflict semantics, and the plain-file operations in §10, including the registered file-set check. It sketches the CatalogAdapter boundary until a dedicated ADR exists.

**Does not own:**
- Publication of generic file/dataset output — ADR-0017.
- Decoding and encoding data files — ADR-0014.
- Object and byte operations — ADR-0005.
- Identity for storage and catalog endpoints — ADR-0016.
- Recording commit intent and outcome, and recovery — ADR-0013.
- Planning and scheduling of rewrite work — ADR-0012.
- Validation evidence required before a commit — ADR-0006.
- Logical type semantics used in cross-format mapping — ADR-0003.

## 15. Revisit conditions

Revisit when UDC chooses a table format for a production migration release or when an existing library cannot expose the required commit/snapshot controls.

## 16. References

- [Apache Iceberg Spark procedures (`migrate`, `snapshot`, `add_files`)](https://iceberg.apache.org/docs/latest/spark-procedures/)
- [Apache Iceberg implementation status by language](https://iceberg.apache.org/status/)
- [Delta Lake table utility commands (`CONVERT TO DELTA`)](https://docs.delta.io/latest/delta-utility.html)
- [Delta Lake UniForm](https://docs.delta.io/latest/delta-uniform.html)
- [Apache XTable features and limitations](https://xtable.apache.org/docs/features-and-limitations/)

## 17. Related ADRs

- [ADR-0003: Canonical Data Model and Schema Compatibility](ADR-0003-canonical-data-model.md)
- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0006: Validation Semantics](ADR-0006-validation-semantics.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0014: File Format Adapter Contract](ADR-0014-file-format-adapter-contract.md)
- [ADR-0016: Cloud Authentication and Credential Resolution](ADR-0016-cloud-authentication.md)
- [ADR-0017: Output Publication Protocol](ADR-0017-output-publication-protocol.md)
