# Reference configuration (H2)

The baseline that UDC is measured against in the evidence gates of [PRD §13.3](../../../docs/PRD.md#133-value-hypotheses-and-evidence-gates): an existing single-binary engine, the DuckDB CLI, driven by a script that adds the four things a careful engineer would add around it.

1. **A per-attempt staging prefix.** Each unit is written by DuckDB to `_staging/<job>/<attempt>/` in the destination bucket.
2. **A row-count check with read-back.** The staged file is read back and its row count compared with the source's.
3. **A ledger of completed units.** One fsynced JSON line per unit, so a re-run with the same job ID skips them.
4. **A completion marker.** Staged files are copied to their final keys, then `_SUCCESS` is written, then staging is deleted. A run that finds `_SUCCESS` only removes leftover staging.

It is meant to be an ordinary, fair implementation, not a straw man. It deliberately does not add what UDC's design adds, because whether a script needs those is what hypothesis H2 asks: aborting pending multipart uploads, checking source identity (ADR-0012), requiring an empty destination or claiming it (ADR-0017), and validating values rather than counts (ADR-0006).

The job logic (`job.py`, `ledger.py`, `s3.py`, `duckdb_cli.py`, `config.py`) is about 470 lines of Python, including docstrings.

## H2 interruption tests

`python -m refconf h2` runs each scenario from empty buckets: it runs the job in a subprocess, kills it with SIGKILL at one point, takes a snapshot, runs it again with the same job ID and ledger, and takes a second snapshot. Faults are injected with `REFCONF_FAULT=<point>[@<where>]` (see `refconf/faults.py`). The harness reports what it observed; whether that meets the H2 bar is decided by a person and recorded in the PRD.

Results on 2026-11-17, against RustFS 1.0.6 ([tools/s3](../../../tools/s3/README.md)) with DuckDB 2.0.0. "Rows seen" is what a reader that lists the destination prefix reads:

| Scenario | After the kill: marker, files visible, rows seen / source, staging, pending uploads | After the re-run: complete and correct, leftovers | Observations |
|---|---|---|---|
| No interruption | — | yes, staging 0, uploads 0 | Nothing visible before _SUCCESS; nothing left behind. |
| Killed while DuckDB uploads a unit | no, 0, 0 / 2400000, 1, 1 | yes, staging 0, uploads 1 | After the kill, 1 multipart upload(s) are pending. After a successful re-run, 1 pending upload(s) remain; the script never learns of them. |
| Killed after a unit is staged, before its check | no, 0, 0 / 80000, 2, 0 | yes, staging 0, uploads 0 | Nothing visible before _SUCCESS; nothing left behind. |
| Killed after the check, before the ledger entry | no, 0, 0 / 80000, 2, 0 | yes, staging 0, uploads 0 | Nothing visible before _SUCCESS; nothing left behind. |
| Killed between units | no, 0, 0 / 80000, 2, 0 | yes, staging 0, uploads 0 | Nothing visible before _SUCCESS; nothing left behind. |
| Killed after 2 of 4 files are promoted | no, 2, 40000 / 80000, 4, 0 | yes, staging 0, uploads 0 | After the kill, readers that list the prefix see 2 file(s), 40000 of 80000 rows, with no _SUCCESS. |
| Killed after promotion, before _SUCCESS | no, 4, 80000 / 80000, 4, 0 | yes, staging 0, uploads 0 | After the kill, readers that list the prefix see 4 file(s), 80000 of 80000 rows, with no _SUCCESS. |
| Killed after _SUCCESS, before staging cleanup | yes, 4, 80000 / 80000, 4, 0 | yes, staging 0, uploads 0 | Nothing visible before _SUCCESS; nothing left behind. |
| A converted source partition is replaced before the re-run | no, 0, 0 / 80000, 2, 0 | no, staging 0, uploads 0 | The job reported success, but readers see 80000 rows; the source now has 100000. |
| The destination already holds a partition from an earlier run | — | no, staging 0, uploads 0 | The job reported success, but readers see 100000 rows; the source now has 80000. |
| Two jobs write the same destination at once | — | no, staging 0, uploads 0 | Both jobs reported success, but only the last writer's output remains; the other job's reported output is gone. Which one wins depends on timing. |
| A different job writes to a destination that an earlier job completed | — | no, staging 0, uploads 0 | The job reported success, but readers see 20000 rows; the source now has 80000. |

The concurrent scenario's outcome depends on timing: in some runs the partitions of both jobs are mixed, in others the last writer's output replaces the first's whole.

## Running it

```sh
cd tools/s3 && docker compose up -d --wait && cd -
export S3_ENDPOINT=http://127.0.0.1:19000 AWS_ACCESS_KEY_ID=udc-local-access AWS_SECRET_ACCESS_KEY=udc-local-secret
uv run python -m refconf fetch-duckdb       # downloads DuckDB 2.0.0 into .bin/ and checks its SHA-256
uv run python -m refconf h2 --out h2.md      # all scenarios, about 20 seconds
uv run pytest                                # tests; coverage must stay at 80% or more
```

Set `REFCONF_DUCKDB` to use a DuckDB binary you already have. The CLI is run with `AI_AGENT` removed from its environment, because DuckDB 2.0 changes its output format when that variable is set.

Other commands: `python -m refconf generate --dest s3://bucket/prefix` writes the deterministic test dataset, and `python -m refconf run --job-id ID --source s3://... --dest s3://... --ledger PATH` runs one job.
