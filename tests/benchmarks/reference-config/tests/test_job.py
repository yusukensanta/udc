"""The reference configuration against a real S3-compatible store."""

from __future__ import annotations

import pytest

from refconf import datagen, job
from refconf.duckdb_cli import ChildStopped, DuckDB, DuckDBError
from refconf.faults import Fault, FaultMissed, Faults, InjectedFault
from refconf.observe import snapshot, visible_files


def test_plan_lists_partitions_only(s3, dataset):
    s3.put(dataset.source_bucket, "dataset/README.txt", b"x")
    s3.put(dataset.source_bucket, "dataset/day=9/notes.txt", b"x")
    assert job.plan(s3, dataset) == ["day=0", "day=1", "day=2", "day=3"]


def test_a_run_converts_publishes_and_cleans_up(s3, duck, dataset):
    result = job.run(dataset, s3, duck, Faults(None))
    assert (result.status, result.units) == ("completed", 4)
    after = snapshot(dataset, s3, duck)
    assert after.complete_and_correct
    assert after.visible_files == 4
    assert not after.leftovers
    assert after.ledger_units == 4

    again = job.run(dataset, s3, duck, Faults(None))
    assert again.status == "already-complete"


@pytest.mark.parametrize(
    "fault",
    [
        "before_write@day=1",
        "after_write@day=1",
        "after_check@day=1",
        "after_ledger@day=1",
        "during_promotion@1",
        "before_marker",
        "after_marker",
    ],
)
def test_a_rerun_after_a_fault_completes(s3, duck, dataset, fault):
    with pytest.raises(InjectedFault):
        job.run(dataset, s3, duck, Faults(Fault.parse(fault, "raise")))
    job.run(dataset, s3, duck, Faults(None))
    after = snapshot(dataset, s3, duck)
    assert after.complete_and_correct
    assert after.staging_objects == 0


def test_promotion_fault_leaves_part_of_the_output_visible(s3, duck, dataset):
    with pytest.raises(InjectedFault):
        job.run(dataset, s3, duck, Faults(Fault.parse("during_promotion@1", "raise")))
    assert len(visible_files(s3, dataset)) == 2
    assert not s3.exists(dataset.dest_bucket, dataset.marker_key)


def test_during_write_kills_duckdb_once_an_upload_exists(s3, duck, dataset, monkeypatch):
    monkeypatch.setattr(type(s3), "pending_uploads", lambda self, bucket, prefix="": 1)
    with pytest.raises(InjectedFault, match="during_write@day=0"):
        job.run(dataset, s3, duck, Faults(Fault.parse("during_write@day=0", "raise")))


def test_during_write_reports_a_missed_fault(s3, duck, dataset, monkeypatch):
    monkeypatch.setattr(type(s3), "pending_uploads", lambda self, bucket, prefix="": 0)
    with pytest.raises(FaultMissed):
        job.run(dataset, s3, duck, Faults(Fault.parse("during_write@day=0", "raise")))


def test_a_row_count_mismatch_stops_before_anything_is_published(s3, duck, dataset, monkeypatch):
    real = DuckDB.count

    def short_count(self, url):
        rows = real(self, url)
        return rows - 1 if "_staging" in url else rows

    monkeypatch.setattr(DuckDB, "count", short_count)
    with pytest.raises(job.CheckFailed, match="day=0"):
        job.run(dataset, s3, duck, Faults(None))
    assert visible_files(s3, dataset) == []


def test_duckdb_errors_and_stop_conditions(duck):
    with pytest.raises(DuckDBError):
        duck.run("SELECT * FROM no_such_table;")
    with pytest.raises(ChildStopped):
        duck.run("SELECT sum(i) FROM range(100000000000) t(i);", stop_when=lambda: True)


def test_generate_writes_the_requested_rows(duck, make_bucket):
    bucket = make_bucket()
    assert datagen.generate(duck, bucket, "d", partitions=2, rows=50, seed=1) == 100
    assert duck.count(f"s3://{bucket}/d/**/*.parquet") == 100


def test_s3_helpers(s3, make_bucket):
    bucket = make_bucket()
    s3.put(bucket, "a/1", b"x")
    s3.copy(bucket, "a/1", "b/1")
    assert s3.exists(bucket, "b/1")
    assert not s3.exists(bucket, "missing")
    upload = s3.client.create_multipart_upload(Bucket=bucket, Key="a/big")
    assert s3.pending_uploads(bucket, "a/") == 1
    assert s3.abort_uploads(bucket) == 1
    assert upload["UploadId"]
    assert s3.delete_prefix(bucket, "a/") == 1
    assert list(s3.keys(bucket)) == ["b/1"]
    s3.reset_bucket(bucket)
    assert list(s3.keys(bucket)) == []
