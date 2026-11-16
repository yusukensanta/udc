"""Command line for the reference configuration.

    python -m refconf fetch-duckdb
    python -m refconf generate --dest s3://bucket/prefix --partitions 4 --rows 20000 [--seed 0]
    python -m refconf run --job-id ID --source s3://b/p --dest s3://b/p --ledger PATH
    python -m refconf h2 [--out results.md] [--json results.json]

The store comes from S3_ENDPOINT, S3_REGION, AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY. Faults
for `run` come from REFCONF_FAULT and REFCONF_FAULT_ACTION (see refconf.faults).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from refconf import datagen, harness, job
from refconf.config import Job, Store
from refconf.duckdb_cli import DuckDB, ensure
from refconf.faults import Fault, Faults
from refconf.s3 import S3

BIN_DIR = Path(__file__).resolve().parent.parent / ".bin"


def split_s3_url(url: str) -> tuple[str, str]:
    if not url.startswith("s3://"):
        raise SystemExit(f"not an s3:// URL: {url}")
    bucket, _, prefix = url[len("s3://") :].partition("/")
    return bucket, prefix.strip("/")


def duckdb_path() -> Path:
    configured = os.environ.get("REFCONF_DUCKDB")
    return Path(configured) if configured else ensure(BIN_DIR)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m refconf")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fetch-duckdb")
    gen = commands.add_parser("generate")
    gen.add_argument("--dest", required=True)
    gen.add_argument("--partitions", type=int, default=harness.PARTITIONS)
    gen.add_argument("--rows", type=int, default=harness.ROWS)
    gen.add_argument("--seed", type=int, default=0)
    run = commands.add_parser("run")
    run.add_argument("--job-id", required=True)
    run.add_argument("--source", required=True)
    run.add_argument("--dest", required=True)
    run.add_argument("--ledger", required=True, type=Path)
    h2 = commands.add_parser("h2")
    h2.add_argument("--out", type=Path)
    h2.add_argument("--json", type=Path)
    args = parser.parse_args(argv)

    if args.command == "fetch-duckdb":
        print(ensure(BIN_DIR))
        return 0

    store = Store.from_env()
    binary = duckdb_path()
    duck, s3 = DuckDB(binary, store), S3(store)
    if args.command == "generate":
        bucket, prefix = split_s3_url(args.dest)
        print(datagen.generate(duck, bucket, prefix, args.partitions, args.rows, args.seed))
        return 0
    if args.command == "run":
        source_bucket, source_prefix = split_s3_url(args.source)
        dest_bucket, dest_prefix = split_s3_url(args.dest)
        spec = Job(args.job_id, source_bucket, source_prefix, dest_bucket, dest_prefix, args.ledger)
        result = job.run(spec, s3, duck, Faults(Fault.from_env()))
        print(f"{result.status}: {result.units} unit(s)")
        return 0
    return harness.main(args.out, args.json, harness.context(s3, duck, binary))


if __name__ == "__main__":
    sys.exit(main())
