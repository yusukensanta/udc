"""The interruption tests of hypothesis H2 (PRD §13.3).

Each scenario starts from empty buckets, runs the reference configuration in a subprocess, kills it
at one point with SIGKILL, takes a snapshot, runs it again with the same job ID and ledger, and
takes a second snapshot. A few scenarios probe gaps that are not interruptions: a source that
changes between the kill and the re-run, a destination that already holds data, and two jobs
writing to one destination.

The harness reports what it observed. Whether that meets the H2 bar is decided by a person.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from refconf import datagen
from refconf.config import Job
from refconf.duckdb_cli import DuckDB
from refconf.observe import Snapshot, snapshot
from refconf.s3 import S3

PARTITIONS = 4
ROWS = 20_000
# Large enough that DuckDB is still uploading when the harness looks for its multipart upload.
LARGE_ROWS = 600_000
SOURCE, SOURCE_B, DEST = "refconf-src", "refconf-src-b", "refconf-dst"
PREFIX = "dataset"


@dataclass
class Context:
    s3: S3
    duck: DuckDB
    duckdb_path: Path
    workdir: Path

    def job(self, name: str, source_bucket: str = SOURCE) -> Job:
        return Job(
            job_id=name,
            source_bucket=source_bucket,
            source_prefix=PREFIX,
            dest_bucket=DEST,
            dest_prefix=PREFIX,
            ledger_path=self.workdir / f"{name}.ledger",
        )


@dataclass(frozen=True)
class Scenario:
    key: str
    description: str
    fault: str | None = None
    rows: int = ROWS
    between: Callable[[Context], None] | None = None
    before: Callable[[Context], None] | None = None
    concurrent: bool = False


@dataclass
class Outcome:
    scenario: Scenario
    first_exit: int | None
    interrupted: Snapshot | None
    second_exit: int | None
    final: Snapshot
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "scenario": self.scenario.key,
            "description": self.scenario.description,
            "fault": self.scenario.fault,
            "first_exit": self.first_exit,
            "interrupted": self.interrupted.as_dict() if self.interrupted else None,
            "second_exit": self.second_exit,
            "final": self.final.as_dict(),
            "notes": self.notes,
        }


def replace_source_partition(ctx: Context) -> None:
    """Overwrite day=0, already converted, with different rows."""
    ctx.duck.run(datagen.partition_sql(SOURCE, PREFIX, 0, ROWS * 2, seed=7))


def seed_stale_partition(ctx: Context) -> None:
    """Leave a partition from an earlier run in the destination."""
    ctx.duck.run(datagen.partition_sql(DEST, PREFIX, 9, ROWS, seed=99))


def complete_an_earlier_job(ctx: Context) -> None:
    """An earlier job with another ID and another source left _SUCCESS in the destination."""
    datagen.generate(ctx.duck, SOURCE_B, PREFIX, 1, ROWS, seed=5)
    earlier = ctx.job("h2-earlier", source_bucket=SOURCE_B)
    earlier.ledger_path.unlink(missing_ok=True)
    finish(run_job(ctx, earlier, None))


SCENARIOS = (
    Scenario("baseline", "No interruption"),
    Scenario(
        "during_write",
        "Killed while DuckDB uploads a unit",
        "during_write@day=1",
        rows=LARGE_ROWS,
    ),
    Scenario("after_write", "Killed after a unit is staged, before its check", "after_write@day=1"),
    Scenario("after_check", "Killed after the check, before the ledger entry", "after_check@day=1"),
    Scenario("between_units", "Killed between units", "after_ledger@day=1"),
    Scenario("during_promotion", "Killed after 2 of 4 files are promoted", "during_promotion@1"),
    Scenario("before_marker", "Killed after promotion, before _SUCCESS", "before_marker"),
    Scenario("after_marker", "Killed after _SUCCESS, before staging cleanup", "after_marker"),
    Scenario(
        "source_changed",
        "A converted source partition is replaced before the re-run",
        "after_ledger@day=1",
        between=replace_source_partition,
    ),
    Scenario(
        "stale_destination",
        "The destination already holds a partition from an earlier run",
        before=seed_stale_partition,
    ),
    Scenario("concurrent", "Two jobs write the same destination at once", concurrent=True),
    Scenario(
        "other_job_marker",
        "A different job writes to a destination that an earlier job completed",
        before=complete_an_earlier_job,
    ),
)


def run_job(ctx: Context, job: Job, fault: str | None) -> subprocess.Popen[str]:
    """Start the reference configuration in a subprocess, as an operator would run it."""
    env = {k: v for k, v in os.environ.items() if k not in ("REFCONF_FAULT",)}
    env["REFCONF_DUCKDB"] = str(ctx.duckdb_path)
    env["REFCONF_FAULT_ACTION"] = "kill"
    if fault:
        env["REFCONF_FAULT"] = fault
    command = [
        sys.executable,
        "-m",
        "refconf",
        "run",
        "--job-id",
        job.job_id,
        "--source",
        f"s3://{job.source_bucket}/{job.source_prefix}",
        "--dest",
        f"s3://{job.dest_bucket}/{job.dest_prefix}",
        "--ledger",
        str(job.ledger_path),
    ]
    return subprocess.Popen(
        command,
        env=env,
        cwd=Path(__file__).resolve().parent.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def finish(process: subprocess.Popen[str], timeout: float = 600) -> int:
    output, _ = process.communicate(timeout=timeout)
    if process.returncode not in (0, -9):
        raise RuntimeError(f"job failed with exit status {process.returncode}:\n{output}")
    return process.returncode


def reset(ctx: Context) -> None:
    for bucket in (SOURCE, SOURCE_B, DEST):
        ctx.s3.reset_bucket(bucket)


def run_scenario(ctx: Context, scenario: Scenario) -> Outcome:
    reset(ctx)
    datagen.generate(ctx.duck, SOURCE, PREFIX, PARTITIONS, scenario.rows)
    job = ctx.job(f"h2-{scenario.key}")
    job.ledger_path.unlink(missing_ok=True)
    if scenario.before:
        scenario.before(ctx)

    if scenario.concurrent:
        datagen.generate(ctx.duck, SOURCE_B, PREFIX, PARTITIONS, scenario.rows * 3, seed=1)
        other = ctx.job(f"h2-{scenario.key}-b", source_bucket=SOURCE_B)
        other.ledger_path.unlink(missing_ok=True)
        first, second = run_job(ctx, job, None), run_job(ctx, other, None)
        exits = (finish(first), finish(second))
        final = snapshot(job, ctx.s3, ctx.duck)
        outcome = Outcome(scenario, exits[0], None, exits[1], final)
        a_rows, b_rows = PARTITIONS * scenario.rows, PARTITIONS * scenario.rows * 3
        if final.reader_rows not in (a_rows, b_rows):
            outcome.notes.append(
                f"Both jobs reported success; readers see {final.reader_rows} rows, which is "
                f"neither job's output ({a_rows} or {b_rows}): partitions from both are mixed."
            )
        else:
            outcome.notes.append(
                "Both jobs reported success, but only the last writer's output remains; "
                "the other job's reported output is gone. Which one wins depends on timing."
            )
        return outcome

    first_exit = finish(run_job(ctx, job, scenario.fault))
    interrupted = snapshot(job, ctx.s3, ctx.duck) if scenario.fault else None
    if scenario.between:
        scenario.between(ctx)
    second_exit = finish(run_job(ctx, job, None)) if scenario.fault else None
    final = snapshot(job, ctx.s3, ctx.duck)
    outcome = Outcome(scenario, first_exit, interrupted, second_exit, final)
    outcome.notes = describe(outcome)
    return outcome


def describe(outcome: Outcome) -> list[str]:
    notes = []
    i, f = outcome.interrupted, outcome.final
    if i and i.visible_files and not i.marker:
        notes.append(
            f"After the kill, readers that list the prefix see {i.visible_files} file(s), "
            f"{i.reader_rows} of {i.source_rows} rows, with no _SUCCESS."
        )
    if i and i.pending_uploads:
        notes.append(f"After the kill, {i.pending_uploads} multipart upload(s) are pending.")
    if f.marker and f.reader_rows != f.source_rows:
        notes.append(
            f"The job reported success, but readers see {f.reader_rows} rows; "
            f"the source now has {f.source_rows}."
        )
    if f.pending_uploads:
        notes.append(
            f"After a successful re-run, {f.pending_uploads} pending upload(s) remain; "
            "the script never learns of them."
        )
    if f.staging_objects:
        notes.append(f"After a successful re-run, {f.staging_objects} staging object(s) remain.")
    if not notes:
        notes.append("Nothing visible before _SUCCESS; nothing left behind.")
    return notes


def run_all(ctx: Context, scenarios: tuple[Scenario, ...] | None = None) -> list[Outcome]:
    return [run_scenario(ctx, scenario) for scenario in (scenarios or SCENARIOS)]


def render(outcomes: list[Outcome]) -> str:
    lines = [
        "| Scenario | After the kill: marker, files visible, rows seen / source, staging, "
        "pending uploads | After the re-run: complete and correct, leftovers | Observations |",
        "|---|---|---|---|",
    ]
    for o in outcomes:
        i, f = o.interrupted, o.final
        killed = (
            f"{'yes' if i.marker else 'no'}, {i.visible_files}, {i.reader_rows} / "
            f"{i.source_rows}, {i.staging_objects}, {i.pending_uploads}"
            if i
            else "—"
        )
        rerun = (
            f"{'yes' if f.complete_and_correct else 'no'}, "
            f"staging {f.staging_objects}, uploads {f.pending_uploads}"
        )
        lines.append(f"| {o.scenario.description} | {killed} | {rerun} | {' '.join(o.notes)} |")
    return "\n".join(lines) + "\n"


def main(out: Path | None, json_out: Path | None, ctx: Context) -> int:
    outcomes = run_all(ctx)
    table = render(outcomes)
    print(table)
    if out:
        out.write_text(table)
    if json_out:
        json_out.write_text(json.dumps([o.as_dict() for o in outcomes], indent=2) + "\n")
    return 0


def context(s3: S3, duck: DuckDB, duckdb_path: Path) -> Context:
    return Context(s3, duck, duckdb_path, Path(tempfile.mkdtemp(prefix="refconf-h2-")))
