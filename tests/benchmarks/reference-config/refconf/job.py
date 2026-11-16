"""The reference configuration's conversion job.

    for each source partition not in the ledger:
        COPY it with DuckDB to a fresh attempt prefix under _staging/
        read the staged file back and compare its row count with the source
        append the unit to the ledger
    copy every staged file to its final key under the destination prefix
    write _SUCCESS
    delete the job's staging prefix

A re-run with the same job ID and ledger resumes: completed units are skipped. If _SUCCESS already
exists, the run only removes leftover staging and stops.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from refconf.config import Job
from refconf.duckdb_cli import ChildStopped, DuckDB
from refconf.faults import FaultMissed, Faults
from refconf.ledger import Entry, Ledger
from refconf.s3 import S3


class CheckFailed(RuntimeError):
    """The staged output does not have the source's row count."""


@dataclass(frozen=True)
class Result:
    status: str
    units: int


def plan(s3: S3, job: Job) -> list[str]:
    """Source partitions, such as `day=0`, in a stable order."""
    prefix = f"{job.source_prefix}/"
    units = set()
    for key in s3.keys(job.source_bucket, prefix):
        first = key[len(prefix) :].split("/", 1)[0]
        if "=" in first and key.endswith(".parquet"):
            units.add(first)
    return sorted(units)


def run(job: Job, s3: S3, duck: DuckDB, faults: Faults) -> Result:
    if s3.exists(job.dest_bucket, job.marker_key):
        s3.delete_prefix(job.dest_bucket, job.staging_prefix)
        return Result("already-complete", 0)

    ledger = Ledger(job.ledger_path)
    done = ledger.load()
    units = plan(s3, job)
    for unit in units:
        if unit in done:
            continue
        attempt = uuid.uuid4().hex
        staged = job.staged_key(attempt, unit)
        faults.at("before_write", unit)
        stop_when = None
        if faults.armed("during_write", unit):
            # Kill DuckDB as soon as its multipart upload of the staged file exists.
            def upload_seen(prefix: str = f"{job.staging_prefix}{attempt}/") -> bool:
                return s3.pending_uploads(job.dest_bucket, prefix) > 0

            stop_when = upload_seen

        try:
            duck.copy(job.source_url(unit), f"s3://{job.dest_bucket}/{staged}", stop_when)
        except ChildStopped:
            faults.fire()
        if stop_when is not None:
            raise FaultMissed(f"during_write@{unit}: the copy finished before an upload was seen")
        faults.at("after_write", unit)

        source_rows = duck.count(job.source_url(unit))
        staged_rows = duck.count(f"s3://{job.dest_bucket}/{staged}")
        if staged_rows != source_rows:
            raise CheckFailed(f"{unit}: staged {staged_rows} rows, source has {source_rows}")
        faults.at("after_check", unit)

        entry = Entry(unit=unit, attempt=attempt, staged_key=staged, rows=staged_rows)
        ledger.append(entry)
        done[unit] = entry
        faults.at("after_ledger", unit)

    for index, unit in enumerate(units):
        s3.copy(job.dest_bucket, done[unit].staged_key, job.final_key(unit))
        faults.at("during_promotion", str(index))

    faults.at("before_marker")
    s3.put(job.dest_bucket, job.marker_key, b"")
    faults.at("after_marker")
    s3.delete_prefix(job.dest_bucket, job.staging_prefix)
    return Result("completed", len(units))
