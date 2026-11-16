"""Fixtures. Integration tests need an S3-compatible store; see the README for how to start one."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from refconf import datagen
from refconf.config import Job, Store
from refconf.duckdb_cli import DuckDB, ensure
from refconf.s3 import S3

PROJECT = Path(__file__).resolve().parent.parent


def pytest_configure(config: pytest.Config) -> None:
    missing = [
        v
        for v in ("S3_ENDPOINT", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
        if not os.environ.get(v)
    ]
    if missing:
        raise pytest.UsageError(
            f"{', '.join(missing)} not set. Start tools/s3/compose.yml; see the README."
        )


@pytest.fixture(scope="session")
def store() -> Store:
    return Store.from_env()


@pytest.fixture(scope="session")
def duckdb_binary() -> Path:
    configured = os.environ.get("REFCONF_DUCKDB")
    return Path(configured) if configured else ensure(PROJECT / ".bin")


@pytest.fixture(scope="session")
def duck(duckdb_binary: Path, store: Store) -> DuckDB:
    return DuckDB(duckdb_binary, store)


@pytest.fixture(scope="session")
def s3(store: Store) -> S3:
    return S3(store)


@pytest.fixture
def make_bucket(s3: S3) -> Iterator[Callable[[], str]]:
    created: list[str] = []

    def make() -> str:
        name = f"rc-{uuid.uuid4().hex[:16]}"
        s3.reset_bucket(name)
        created.append(name)
        return name

    yield make
    for name in created:
        s3.delete_bucket(name)


@pytest.fixture
def dataset(make_bucket, duck: DuckDB, tmp_path: Path) -> Job:
    """A job over a fresh 4-partition source and an empty destination."""
    source, dest = make_bucket(), make_bucket()
    datagen.generate(duck, source, "dataset", partitions=4, rows=1000)
    return Job(
        job_id=f"test-{uuid.uuid4().hex[:8]}",
        source_bucket=source,
        source_prefix="dataset",
        dest_bucket=dest,
        dest_prefix="dataset",
        ledger_path=tmp_path / "ledger.jsonl",
    )
