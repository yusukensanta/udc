"""What a job left behind, as seen by a reader and by an operator."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from refconf.config import Job
from refconf.duckdb_cli import DuckDB
from refconf.ledger import Ledger
from refconf.s3 import S3


@dataclass(frozen=True)
class Snapshot:
    marker: bool
    visible_files: int
    reader_rows: int
    source_rows: int
    staging_objects: int
    pending_uploads: int
    ledger_units: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def complete_and_correct(self) -> bool:
        return self.marker and self.reader_rows == self.source_rows

    @property
    def leftovers(self) -> bool:
        return self.staging_objects > 0 or self.pending_uploads > 0


def visible_files(s3: S3, job: Job) -> list[str]:
    """Data files under the destination prefix, as a reader that lists the prefix sees them.

    Names that begin with an underscore, such as _SUCCESS, are skipped, as Hadoop-family readers
    do.
    """
    prefix = f"{job.dest_prefix}/"
    return [
        key
        for key in s3.keys(job.dest_bucket, prefix)
        if key.endswith(".parquet") and not key.rsplit("/", 1)[-1].startswith("_")
    ]


def snapshot(job: Job, s3: S3, duck: DuckDB) -> Snapshot:
    files = visible_files(s3, job)
    reader_rows = (
        duck.count(f"s3://{job.dest_bucket}/{job.dest_prefix}/**/*.parquet") if files else 0
    )
    return Snapshot(
        marker=s3.exists(job.dest_bucket, job.marker_key),
        visible_files=len(files),
        reader_rows=reader_rows,
        source_rows=duck.count(f"s3://{job.source_bucket}/{job.source_prefix}/**/*.parquet"),
        staging_objects=len(list(s3.keys(job.dest_bucket, "_staging/"))),
        pending_uploads=s3.pending_uploads(job.dest_bucket),
        ledger_units=len(Ledger(job.ledger_path).load()),
    )
