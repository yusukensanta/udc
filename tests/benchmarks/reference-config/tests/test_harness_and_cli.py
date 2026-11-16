"""The H2 harness and the command line, run against the store with a few quick scenarios."""

from __future__ import annotations

import json

import pytest

from refconf import __main__ as cli
from refconf import harness

QUICK = tuple(
    s
    for s in harness.SCENARIOS
    if s.key in ("baseline", "during_promotion", "source_changed", "concurrent", "other_job_marker")
)


@pytest.fixture
def quick(monkeypatch):
    monkeypatch.setattr(harness, "SCENARIOS", QUICK)


def test_harness_reports_what_it_observed(quick, s3, duck, duckdb_binary, tmp_path):
    ctx = harness.context(s3, duck, duckdb_binary)
    outcomes = harness.run_all(ctx)
    by_key = {o.scenario.key: o for o in outcomes}

    assert by_key["baseline"].final.complete_and_correct
    promotion = by_key["during_promotion"]
    assert promotion.first_exit == -9
    assert promotion.interrupted.visible_files == 2
    assert not promotion.interrupted.marker
    assert promotion.final.complete_and_correct
    assert not by_key["source_changed"].final.complete_and_correct
    concurrent = by_key["concurrent"]
    assert (concurrent.first_exit, concurrent.second_exit) == (0, 0)
    assert "Both jobs reported success" in " ".join(concurrent.notes)
    other = by_key["other_job_marker"]
    assert other.final.marker
    assert not other.final.complete_and_correct

    out, json_out = tmp_path / "h2.md", tmp_path / "h2.json"
    assert harness.main(out, json_out, ctx) == 0
    assert "| No interruption |" in out.read_text()
    assert len(json.loads(json_out.read_text())) == len(QUICK)


def test_a_failing_job_is_reported(s3, duck, duckdb_binary):
    ctx = harness.context(s3, duck, duckdb_binary)
    harness.reset(ctx)
    job = ctx.job("missing-source", source_bucket="no-such-bucket-for-refconf")
    with pytest.raises(RuntimeError, match="job failed"):
        harness.finish(harness.run_job(ctx, job, None))


def test_cli(quick, monkeypatch, tmp_path, duckdb_binary, capsys, make_bucket):
    monkeypatch.setenv("REFCONF_DUCKDB", str(duckdb_binary))
    assert cli.split_s3_url("s3://b/a/b/") == ("b", "a/b")
    with pytest.raises(SystemExit, match="not an s3"):
        cli.split_s3_url("gs://b/p")

    source, dest = make_bucket(), make_bucket()
    assert cli.main(["generate", "--dest", f"s3://{source}/data", "--rows", "100"]) == 0
    assert capsys.readouterr().out.strip() == "400"
    argv = ["run", "--job-id", "cli", "--source", f"s3://{source}/data"]
    argv += ["--dest", f"s3://{dest}/out", "--ledger", str(tmp_path / "l.jsonl")]
    assert cli.main(argv) == 0
    assert "completed: 4 unit(s)" in capsys.readouterr().out

    monkeypatch.setattr(harness, "SCENARIOS", QUICK[:1])
    assert cli.main(["h2", "--out", str(tmp_path / "h2.md")]) == 0
    assert (tmp_path / "h2.md").exists()

    monkeypatch.setattr(cli, "ensure", lambda bin_dir: tmp_path / "duckdb")
    assert cli.main(["fetch-duckdb"]) == 0
    monkeypatch.delenv("REFCONF_DUCKDB")
    assert cli.duckdb_path() == tmp_path / "duckdb"
