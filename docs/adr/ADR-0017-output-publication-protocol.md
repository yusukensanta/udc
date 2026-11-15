# ADR-0017: Output Publication Protocol

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** The Generic Publisher: staging layout, output manifest, publication modes and the guarantee each one gives, reconciliation, and staging cleanup for generic file/dataset output.

## 1. Context

UDC must not expose partial or unvalidated output as a successfully converted dataset. Object stores do not universally provide filesystem-style atomic directory rename. A migration may involve thousands or millions of output objects, validation artifacts, and a final visible dataset reference. Publication must therefore be explicitly modeled and destination-aware.

What "visible" means depends on how a consumer finds the data. A plain-file dataset has no transaction log, so most consumers read whatever objects are under a prefix: a query engine given a path or a glob, or an external table whose location is a prefix. Amazon Athena, for example, documents that it reads all data stored in the location of a table. A publication reference that such a consumer never reads does not protect it. Publication of validated output only is one of the capabilities UDC is positioned on ([PRD §2.5](../PRD.md#25-existing-tools-and-where-udc-fits)), so the guarantee must be stated for these consumers and not only for consumers that follow a reference.

Table-format commits have their own transaction protocols and are governed by ADR-0015. This ADR defines generic file/dataset publication only.

## 2. Decision drivers

1. Keep incomplete and unvalidated output invisible to consumers.
2. State the guarantee for each kind of consumer, including consumers that only list a prefix.
3. Support object stores without assuming atomic rename.
4. Make publication idempotent and recoverable after client/process failure.
5. Prevent accidental source overwrite and conflicting concurrent jobs.
6. Bind publication to an immutable, validated set of output objects.
7. Minimize extra full-data copies and unnecessary listing operations.
8. Separate data upload durability from dataset visibility.
9. Do not make a guarantee depend on a naming convention that only some readers honor.

## 3. Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Write directly to final prefix** | Simple; no extra copy | Unvalidated and partial data is visible for the whole run and remains after a failure; rollback and overwrite conflicts are difficult |
| **Temporary prefix then rename** | Familiar filesystem model | Object-store rename may be copy+delete or unsupported; not generally an atomic commit |
| **Stage, validate, then promote into the destination prefix** | Protects consumers that only list a prefix; nothing unvalidated ever appears; works with per-object primitives that every target store has | The set of objects does not appear atomically; one extra provider-side copy of the output on object stores |
| **Immutable staging objects + final manifest/pointer** | Visibility can be switched by a small final commit; all-or-nothing for the consumer; no extra copy | Protects only consumers that read through the manifest/pointer; old versions require garbage collection |
| **Sealed version location with an external reference** | No extra copy; a prefix-listing consumer that is pointed at the location after the commit sees exactly the output set | The consumer's location must be switched outside UDC; the location must be cleared of rejected Attempt output before the commit |
| **Provider-specific atomic conditional object update** | Strong commit primitive where supported | Capabilities and semantics vary; cannot be assumed portable across clouds |

## 4. Proposed decision

Use **immutable attempt-scoped staging objects and an immutable output manifest** for every publication. How the objects in the output manifest become visible is a **publication mode**, selected per job according to how the dataset's consumers find the data. Each mode has a stated guarantee. UDC reports the mode and its guarantee with every publication result and never describes a publication in stronger terms than its mode provides.

Do not treat prefix existence or a successful rename as proof of publication.

### 4.1 Two kinds of consumer

- A **prefix-listing consumer** reads the objects it finds under a prefix. It does not read any UDC metadata.
- A **reference-aware consumer** reads the publication reference, then the output manifest it names, and then exactly the objects in that manifest.

### 4.2 Publication modes

| | Promotion mode | Reference mode |
|---|---|---|
| Protects | Prefix-listing consumers, and any other consumer | Reference-aware consumers only |
| How output becomes visible | After validation, each object in the output manifest is placed under the destination prefix; a completion marker is written last | A publication reference is switched to the output manifest by one conditional update; the objects stay where they were staged |
| Guarantee | **Validated before visible** (§6.1) | **All or nothing** (§7.1) |
| Appearance of the object set | Not atomic: a consumer that lists during promotion can read a subset | Atomic for a reference-aware consumer |
| Replacing an existing dataset | Not offered | Supported, by switching the reference |
| Extra copy of the output | One provider-side copy on object stores; none on a local filesystem | None |
| MVP | Required; the default | Optional (§7.3) |

Promotion mode is the default because it protects the consumers a plain-file dataset most often has. Its guarantee is weaker than all-or-nothing, and this ADR states the difference instead of hiding it.

If a destination cannot provide the primitives a mode requires (§9), UDC rejects the job at planning time. It does not fall back to writing directly into the destination prefix.

### 4.3 The Generic Publisher

The component that executes this protocol is the **Generic Publisher**. This ADR is its only normative definition. Orchestration (ADR-0012) decides when it is invoked; it does not define what the Generic Publisher does.

The publication target and the publication mode are data-semantics settings (ADR-0009). They are inputs to the plan digest (ADR-0013) and cannot change when a job is resumed.

## 5. Publication phases

Publication depends on steps that other ADRs own. The table lists the full sequence and, for each phase, what this ADR requires and which ADR owns the rest. Phases 1 to 5 and 7 to 8 are the same in both modes. Phase 6 differs by mode.

| # | Phase | What happens | Defined here | Owned elsewhere |
|---|---|---|---|---|
| 1 | Plan | Determine the publication target and mode, check the destination preconditions of the mode, and capture the destination version where available | Target, mode, and precondition capture | Output ownership per Work Unit: ADR-0012 |
| 2 | Stage | Write attempt-scoped immutable data objects; never overwrite source objects | Staging layout (§5.1) | Who writes and when: ADR-0012 workers through ADR-0014 writers and ADR-0005 storage |
| 3 | Finalize | Close writers, verify durable upload completion, collect object identities, sizes, checksums/ETags, and format metadata | Which object identities the output manifest needs | Writer close semantics: ADR-0014. Acceptance of the Attempt: ADR-0013 |
| 4 | Validate | Apply the requested validation policy against the source and staged output; record evidence and its scope | That publication requires recorded evidence | What evidence means: ADR-0006. Recording it: ADR-0013 |
| 5 | Build output manifest | Create an immutable manifest listing the exact accepted objects and relevant schema/partition metadata, with a digest and format version | Entirely | — |
| 6 | Make visible | Promotion mode: place the objects and write the completion marker (§6.4). Reference mode: commit the publication reference (§7.2) | Entirely | The conditional-write and copy primitives: ADR-0005 |
| 7 | Record outcome | Record publication intent and result so an ambiguous acknowledgement can be reconciled | The reconciliation procedure | The publication record: ADR-0013 |
| 8 | Garbage collect | Asynchronously remove unreferenced attempt output after retention and reference-safety checks | Reference-safety rules (§8) | Retention policy and records: ADR-0013 |

Validation always completes before phase 6 starts. No object reaches a place where a consumer of either kind reads it before the whole output set has passed the selected validation.

### 5.1 Staging layout

- Staged objects are immutable, and each object name is unique to its Attempt.
- The attempt scope is encoded so that the directory layout of the output, including partition directories, is preserved below the staging root. An accepted object's path relative to the staging root determines its path relative to the destination.
- The staging root is never inside the destination prefix. UDC rejects a job whose staging root is inside its destination prefix, or whose destination prefix is inside its staging root.
- Invisibility of staged output does not rely on a hidden-name convention such as a leading underscore or dot. Some readers skip such names; that behavior is reader-specific.
- By default the staging root is in the same bucket or container as the destination, so that promotion can use a provider-side copy. The staging root is a job setting. A consumer that lists a common parent of the staging root and the destination can read staged objects; the documentation states this.

## 6. Promotion mode

### 6.1 Guarantee: validated before visible

Promotion mode guarantees the following for every consumer:

1. No object appears under the destination prefix before the whole output set of the job has passed the selected validation. A job that fails before publication, or whose validation fails, leaves the destination prefix unchanged.
2. Every object that appears is complete. Objects are placed with single-object operations that the provider documents as atomic for the object.
3. An object is never placed over an existing object, and promotion never deletes or changes an object it did not place.
4. The completion marker appears only after every object in the output manifest is in place. It names the digest of the output manifest.

Promotion mode does **not** guarantee:

- **Atomic appearance of the set.** A consumer that lists the destination prefix while promotion is in progress can read a subset of the output set. Every object in that subset is validated output, but the dataset is incomplete. A consumer that needs a complete set waits for the completion marker or uses Reference mode.
- **A bounded exposure time after an interruption.** If the process is terminated during promotion, the subset placed so far stays visible until the job is resumed or abandoned (§6.5).

The guarantee is therefore narrower than a table-format commit. Compared with writing directly into the destination prefix, it removes two exposures: output that has not been validated is never visible, and a job that fails before publication leaves nothing behind. It shortens a third: the time during which the set is incomplete is the duration of promotion, not the duration of the conversion.

### 6.2 Destination preconditions

- By default the destination prefix must contain no objects. This is checked at planning time and again when promotion starts.
- An explicit policy may allow promotion into a prefix that already contains objects, for example to add partitions. Promotion then only adds objects with new names. If any destination name in the output manifest already exists when promotion starts, the job fails with a Conflict error (ADR-0008) before any object is placed.
- Replacing or removing existing objects is not offered in promotion mode. A prefix-listing consumer would read a mixture of old and new objects, and no ordering of the operations prevents that. A dataset is replaced by publishing to a new prefix and directing consumers to it, or through Reference mode.

### 6.3 Placing an object

- An object is placed with a no-replace operation: a provider-side copy or a write that succeeds only if the destination name does not exist.
- After placement the Publisher compares the placed object with the validated staged object, using the size and a checksum that the provider reports for both. This is a transfer-integrity check, not a validation level (ADR-0006). Where the provider reports no checksum that is comparable across the copy, the publication record states that the placement was not verified.
- If staging and the destination are in different stores, no provider-side copy exists and the bytes are transferred again through UDC. The same comparison applies.
- If a destination name already exists after promotion has started, the Publisher compares its identity with the staged object. An identical object is treated as placed by an earlier try of this publication. A different object is a Conflict error.

### 6.4 Sequence

1. Record publication intent with the digest of the output manifest (ADR-0013).
2. Check the destination preconditions (§6.2). If reconciliation shows that this publication is already in progress, the check is instead that every object present under the default precondition is one this publication placed.
3. Place every object in the output manifest (§6.3). Placement order is not significant, and placements run under the resource budgets of ADR-0012.
4. Verify that every object in the output manifest exists at its destination name with the expected identity.
5. Write a copy of the output manifest, and then the completion marker, with no-replace writes.
6. Record the outcome.

The publication is committed when the completion marker exists and names the expected manifest digest. Before that point it is in progress, however many objects have been placed.

By default the manifest copy and the completion marker are written under the destination prefix with names that begin with an underscore, following the `_SUCCESS` convention of Hadoop-family committers. Whether each supported reader ignores these names is verified per reader (§11). A job may place them outside the destination prefix instead, for a consumer that does not tolerate additional objects.

### 6.5 Interruption, resume, and withdrawal

- **Reconciliation.** Promotion always starts by reading the destination: the completion marker first, then the placed objects. A committed publication is recorded as such and nothing is placed again. An in-progress publication continues with the objects that are missing.
- **Resume.** A resumed job continues promotion from the retained staged objects under the same publication ID.
- **Withdrawal.** Withdrawal removes the objects that this publication placed, and only those: an object is removed only if its name is in the output manifest, its identity matches the staged object, and no completion marker exists. After withdrawal the destination prefix is as it was before promotion.
- When promotion fails with an error that is not retried (ADR-0008), the Publisher attempts withdrawal before the job is recorded FAILED. The publication record states whether the destination is unchanged or partially promoted, and lists the placed objects in the second case.
- Abandoning a job whose publication is in progress performs withdrawal. Abandoning never removes objects of a committed publication.
- A terminated process cannot withdraw. The subset stays visible until the job is recovered, resumed, or abandoned; `udc job status` reports the in-progress publication.

### 6.6 Local filesystem

On a local filesystem, placement is a no-replace rename within one filesystem, which needs no copy. When the destination directory does not yet exist and staging is on the same filesystem, the Publisher renames the staged directory as a whole. The output set then appears in one step, and the publication is all-or-nothing for prefix-listing consumers as well. This stronger result is reported only where the filesystem's rename behavior has been verified.

## 7. Reference mode

### 7.1 Guarantee: all or nothing

A reference-aware consumer sees either the previous output manifest or the new one, never a mixture and never a partial set. The guarantee holds only for consumers that read through the reference. A consumer that lists the location of the staged objects is outside the guarantee; it can read objects of rejected Attempts and of earlier versions.

### 7.2 Commit

The final publication operation uses a conditional write, a version precondition, or another provider-specific commit primitive. The commit request includes the expected prior version or ETag of the reference where supported. The exact mechanism (a single reference object, a versioned catalog entry, or another provider capability) is negotiated and tested per destination (§9).

The published objects are the staged objects themselves. They are referenced by a committed output manifest and are never removed as staging leftovers.

### 7.3 Consumer convention and MVP status

Reference mode is useful only with a convention that consumers can follow. The candidates are:

- UDC prints the object list of a published dataset, and the consumer passes the list to its reader.
- UDC writes a manifest in a format that existing engines already read, such as the Hive symlink manifest that Delta Lake generates for Presto, Trino, and Athena.

Neither is selected. Reference mode is part of an MVP release only if one convention has been implemented and verified against at least one consumer. Which convention is worth supporting is one of the questions for the practitioner conversations of [PRD §13.3](../PRD.md#133-value-hypotheses-and-evidence-gates).

A third arrangement, a sealed version location whose reference is held outside UDC (§3), needs no extra copy and serves prefix-listing consumers. It is not part of the MVP and is revisited with the first evidence about how consumers are switched to a new location.

## 8. Idempotency and concurrency

- Publication ID is stable for a Job and its plan generation, and therefore unchanged across execution generations (ADR-0013). A resumed job reconciles the same publication instead of starting a second one.
- Manifest content is immutable and content-addressed or versioned.
- A retry after an ambiguous response reads and reconciles the destination before it writes again: the completion marker in Promotion mode, the publication reference in Reference mode.
- Two jobs targeting the same logical destination must not silently overwrite each other. In Reference mode the precondition on the reference detects the conflict. In Promotion mode the no-replace placement detects two jobs that produce the same object name. Under the default precondition the completion marker has a fixed name, so two publications to one empty prefix cannot both commit even when their object names differ. Under the policy that allows a non-empty prefix, the marker name includes the publication ID, and two publications conflict only through an object name.
- Late attempts cannot add objects to an already committed output manifest.
- Garbage collection is reference-aware. It never deletes an object at its published location. In Promotion mode the staged copies are no longer referenced once the publication is committed and are removed after the retention period. In Reference mode the staged objects are the published objects and are never removed by staging cleanup.

## 9. Object-store limitations and capability negotiation

The Storage adapter (ADR-0005) exposes provider operations and their capabilities. The Generic Publisher selects a mode only from capabilities actually verified for that provider/account configuration. It must not infer atomicity from API naming.

| Mode | Required capability |
|---|---|
| Promotion | No-replace creation of an object, by write and by provider-side copy; a strongly consistent listing of the destination prefix; delete, for withdrawal |
| Promotion, verified placement | A checksum that the provider reports for both the staged and the placed object |
| Reference | A conditional update of one object or entry against an expected prior version |

Provider documentation describes the following. Each item is confirmed by test before a release claims it, and is not generalized from one provider to another.

- **Amazon S3:** the `If-None-Match` header is accepted by `PutObject`, `CompleteMultipartUpload`, and `CopyObject`. It is not accepted by the individual multipart operations, so a large object copied in parts is made conditional at completion. The same documentation states that `CopyObject` with a conditional header fails when a bucket policy enforces conditional writes; this case must be tested and documented.
- **Google Cloud Storage:** copy and rewrite accept preconditions on the destination object; `ifGenerationMatch=0` succeeds only when no live object has the name.
- **Azure Blob Storage:** copy operations accept conditional headers for the destination blob.

If a required capability is absent or cannot be verified, the job is rejected at planning time with a Compatibility error (ADR-0008).

## 10. Trade-offs and consequences

- Promotion mode costs one additional copy of the output on object stores. The copy is provider-side when staging and destination share a store, so the bytes do not pass through UDC, but it adds requests and time proportional to the output.
- Promotion mode does not make a multi-object dataset appear atomically. UDC cannot offer that to a consumer that only lists a prefix; the documentation must say so wherever publication is described.
- Withdrawal deletes objects under the user's destination prefix. The rules in §6.5 restrict it to objects this publication placed, and it requires delete permission on the destination.
- A terminated process leaves a partially promoted destination until someone acts. Recovery after restart and `udc job status` make the state visible; they do not remove the exposure.
- Reference mode gives the stronger guarantee but depends on a consumer convention that plain-file tooling does not share. Until one is selected, it protects few real consumers.
- Supporting two modes increases the test matrix: each mode is tested per provider.
- The completion marker and manifest copy are additional objects under the destination prefix by default. A reader that does not ignore them needs them placed elsewhere.

## 11. Validation plan

Inject failure before, during, and after each publication phase, including a lost response after the completion marker or the reference commit is written. For every case verify the guarantee of the mode in use.

Promotion mode:

- While a job runs and after a job fails before publication or fails validation, the destination prefix lists no object of the job.
- With promotion interrupted after each number of placed objects, a resumed job completes the publication without placing an object twice, and an abandoned job leaves the destination prefix as it was.
- An existing object with a destination name is never overwritten, and withdrawal never removes an object that this publication did not place.
- The completion marker never exists while an object of the output manifest is missing.
- Two jobs promoting to the same destination: at most one commits, and the other fails with a Conflict error and withdraws.
- Each supported reader, including DuckDB, Spark, and Athena, reads a promoted dataset with the completion marker and manifest copy present.
- Measure promotion time and request count against conversion time on the benchmark datasets, and compare the exposure window with a direct write by the reference configuration (PRD §13.3, H2).

Reference mode, where it is offered:

- A reference-aware consumer never reads an incomplete set, repeated commit attempts are idempotent, concurrent updates of the reference are detected, and garbage collection preserves referenced objects.

Test provider-specific semantics for the local filesystem, S3, GCS, and Azure separately; do not generalize one provider's guarantee to the others.

## 12. Ownership boundary

**Owns:** the Generic Publisher and its protocol for generic file/dataset output: staging layout, the output manifest, the publication modes and the guarantee each one may claim, the completion marker and the publication reference, reconciliation of ambiguous outcomes, withdrawal, and reference-safe cleanup of staging.

**Does not own:**
- Publication of Iceberg, Delta, Hudi, or Lance tables. This ADR never publishes a table by rewriting a pointer itself; table publication uses the format-native commit protocol — ADR-0015.
- When the job workflow invokes publication — ADR-0012.
- Object operations, provider-side copy, and conditional-write capabilities — ADR-0005.
- What validation evidence means, and the definition of transfer integrity — ADR-0006.
- The publication record, retention policy, and recovery state — ADR-0013.
- Retry eligibility of publication errors — ADR-0008.
- How the publication mode is expressed in configuration — ADR-0009.

## 13. Revisit conditions

Revisit when a consumer convention for Reference mode is selected, when measurements show that the promotion copy is too costly for target datasets, when evidence shows how users switch consumers to a new location (the sealed version location of §3), or when UDC introduces table-format publication as a production capability.

## 14. References

- [Amazon Athena: specify a table location in Amazon S3](https://docs.aws.amazon.com/athena/latest/ug/tables-location-format.html)
- [Amazon S3: how to prevent object overwrites with conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)
- [Amazon S3: enforce conditional writes on Amazon S3 buckets](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html)
- [Google Cloud Storage: request preconditions](https://cloud.google.com/storage/docs/request-preconditions)
- [Azure Blob Storage: Copy Blob](https://learn.microsoft.com/en-us/rest/api/storageservices/copy-blob)
- [Delta Lake: Presto, Trino, and Athena integration using manifests](https://docs.delta.io/latest/presto-integration.html)

## 15. Related ADRs

- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0006: Validation Semantics](ADR-0006-validation-semantics.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0009: CLI and Job Configuration](ADR-0009-cli-and-configuration.md)
- [ADR-0012: Scalable Data Processing Architecture](ADR-0012-scalable-data-processing.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0014: File Format Adapter Contract](ADR-0014-file-format-adapter-contract.md)
- [ADR-0015: Table Format Integration Boundary](ADR-0015-table-format-integration-boundary.md)
