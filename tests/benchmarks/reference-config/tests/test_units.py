"""Tests that need no store: configuration, faults, ledger, DuckDB helpers, and rendering."""

from __future__ import annotations

import hashlib
import io
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from refconf import datagen, duckdb_cli, harness
from refconf.config import Job, Store, sql_literal
from refconf.faults import Fault, Faults, InjectedFault
from refconf.ledger import Entry, Ledger
from refconf.observe import Snapshot


def test_sql_literal_escapes_quotes():
    assert sql_literal("it's") == "'it''s'"


def test_secret_sql_for_a_local_endpoint():
    sql = Store("http://127.0.0.1:19000", "us-east-1", "k", "s").duckdb_secret_sql()
    assert "ENDPOINT '127.0.0.1:19000'" in sql
    assert "USE_SSL false" in sql
    assert "URL_STYLE 'path'" in sql


def test_secret_sql_for_tls_and_for_the_default_endpoint():
    assert "USE_SSL true" in Store("https://s3.example", "eu-west-1", "k", "s").duckdb_secret_sql()
    default = Store(None, "eu-west-1", "k", "s").duckdb_secret_sql()
    assert "ENDPOINT" not in default
    assert "REGION 'eu-west-1'" in default


def test_store_from_env_requires_credentials(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID")
    with pytest.raises(SystemExit, match="AWS_ACCESS_KEY_ID"):
        Store.from_env()


def test_job_keys():
    job = Job("j1", "src", "data", "dst", "out", Path("ledger"))
    assert job.staging_prefix == "_staging/j1/"
    assert job.marker_key == "out/_SUCCESS"
    assert job.source_url("day=0") == "s3://src/data/day=0/*.parquet"
    assert job.staged_key("a", "day=0") == "_staging/j1/a/day=0/part-0.parquet"
    assert job.final_key("day=0") == "out/day=0/part-0.parquet"


def test_fault_parse_without_a_spec_or_location():
    assert Fault.parse(None) is None
    assert Fault.parse("") is None
    assert Fault.parse("before_marker") == Fault("before_marker", None, "kill")


def test_fault_parse_with_location_and_rejections():
    fault = Fault.parse("after_write@day=1", "raise")
    assert (fault.point, fault.where, fault.action) == ("after_write", "day=1", "raise")
    assert str(fault) == "after_write@day=1"
    with pytest.raises(ValueError, match="unknown fault point"):
        Fault.parse("nowhere")
    with pytest.raises(ValueError, match="unknown fault action"):
        Fault.parse("after_write", "explode")  # type: ignore[arg-type]


def test_fault_from_env(monkeypatch):
    monkeypatch.setenv("REFCONF_FAULT", "after_check@day=2")
    monkeypatch.setenv("REFCONF_FAULT_ACTION", "raise")
    assert Fault.from_env() == Fault("after_check", "day=2", "raise")


def test_faults_fire_only_where_armed():
    faults = Faults(Fault("after_write", "day=1", "raise"))
    faults.at("after_write", "day=0")
    faults.at("after_check", "day=1")
    assert not faults.fired
    with pytest.raises(InjectedFault, match="after_write@day=1"):
        faults.at("after_write", "day=1")
    assert faults.fired
    assert Faults(Fault("before_marker", None, "raise")).armed("before_marker")
    assert not Faults(None).armed("before_marker")


def test_kill_action_sends_sigkill():
    code = (
        "from refconf.faults import Fault, Faults\n"
        "Faults(Fault('before_marker', None, 'kill')).at('before_marker')\n"
        "print('survived')\n"
    )
    project = Path(__file__).resolve().parent.parent
    done = subprocess.run([sys.executable, "-c", code], cwd=project, capture_output=True, text=True)
    assert done.returncode == -9
    assert "survived" not in done.stdout


def test_ledger_round_trip_and_torn_line(tmp_path):
    ledger = Ledger(tmp_path / "sub" / "ledger.jsonl")
    assert ledger.load() == {}
    ledger.append(Entry("day=0", "a0", "k0", 10))
    with ledger.path.open("a") as f:
        f.write('{"unit": "day=1", "att')  # a write torn by a kill
    ledger.append(Entry("day=2", "a2", "k2", 30))
    assert set(ledger.load()) == {"day=0", "day=2"}
    assert ledger.load()["day=2"].rows == 30


def _archive(tmp_path: Path, name: str = "duckdb", body: bytes = b"#!/bin/sh\n") -> Path:
    archive = tmp_path / "cli.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo(name)
        info.size = len(body)
        tar.addfile(info, io.BytesIO(body))
    return archive


def test_verify_and_extract(tmp_path):
    archive = _archive(tmp_path)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    binary = duckdb_cli.verify_and_extract(archive, digest, tmp_path / "bin" / "duckdb")
    assert binary.read_bytes() == b"#!/bin/sh\n"
    assert binary.stat().st_mode & 0o111
    with pytest.raises(RuntimeError, match="does not match"):
        duckdb_cli.verify_and_extract(archive, "0" * 64, tmp_path / "other")


def test_verify_and_extract_rejects_a_non_file_member(tmp_path):
    archive = tmp_path / "cli.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("duckdb")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with pytest.raises(RuntimeError, match="not a regular file"):
        duckdb_cli.verify_and_extract(archive, digest, tmp_path / "duckdb")


def test_ensure_reuses_an_existing_binary_and_rejects_unknown_platforms(tmp_path):
    existing = tmp_path / f"duckdb-{duckdb_cli.VERSION}"
    existing.write_text("x")
    assert duckdb_cli.ensure(tmp_path) == existing
    with pytest.raises(RuntimeError, match="no pinned DuckDB"):
        duckdb_cli.ensure(tmp_path / "empty", system="Plan9", machine="mips")


def test_child_env_drops_ai_agent(monkeypatch):
    monkeypatch.setenv("AI_AGENT", "1")
    monkeypatch.setenv("KEEP_ME", "1")
    env = duckdb_cli.child_env()
    assert "AI_AGENT" not in env
    assert env["KEEP_ME"] == "1"


def test_result_after_marker():
    out = f"Success\ntrue\n{duckdb_cli.RESULT_MARKER}\nn\n42\n"
    assert duckdb_cli.result_after_marker(out) == [{"n": "42"}]
    with pytest.raises(duckdb_cli.DuckDBError, match="no result marker"):
        duckdb_cli.result_after_marker("n\n1\n")


def test_partition_sql_is_deterministic():
    one = datagen.partition_sql("b", "p", 2, 10, seed=3)
    assert one == datagen.partition_sql("b", "p", 2, 10, seed=3)
    assert "s3://b/p/day=2/data_0.parquet" in one
    assert "range(10)" in one


def _snapshot(**overrides) -> Snapshot:
    values = dict(
        marker=True,
        visible_files=4,
        reader_rows=100,
        source_rows=100,
        staging_objects=0,
        pending_uploads=0,
        ledger_units=4,
    )
    values.update(overrides)
    return Snapshot(**values)


def test_snapshot_properties():
    assert _snapshot().complete_and_correct
    assert not _snapshot(marker=False).complete_and_correct
    assert not _snapshot(reader_rows=50).complete_and_correct
    assert _snapshot(pending_uploads=1).leftovers
    assert not _snapshot().leftovers
    assert _snapshot().as_dict()["reader_rows"] == 100


def test_describe_and_render():
    scenario = harness.Scenario("x", "Killed somewhere", "before_marker")
    outcome = harness.Outcome(
        scenario,
        -9,
        _snapshot(marker=False, visible_files=2, reader_rows=50, pending_uploads=1),
        0,
        _snapshot(reader_rows=120, pending_uploads=1, staging_objects=2),
    )
    notes = harness.describe(outcome)
    joined = " ".join(notes)
    assert "see 2 file(s), 50 of 100 rows" in joined
    assert "1 multipart upload(s) are pending" in joined
    assert "readers see 120 rows" in joined
    assert "1 pending upload(s) remain" in joined
    assert "2 staging object(s) remain" in joined
    outcome.notes = notes
    clean = harness.Outcome(harness.Scenario("b", "Baseline"), 0, None, None, _snapshot())
    clean.notes = harness.describe(clean)
    table = harness.render([outcome, clean])
    assert "| Killed somewhere | no, 2, 50 / 100, 0, 1 | no, staging 2, uploads 1 |" in table
    assert "| Baseline | — | yes, staging 0, uploads 0 | Nothing visible" in table
    assert outcome.as_dict()["interrupted"]["visible_files"] == 2
    assert clean.as_dict()["interrupted"] is None
