"""Where the data lives and how to reach it."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


def sql_literal(value: str) -> str:
    """A SQL string literal with embedded quotes escaped."""
    return "'" + value.replace("'", "''") + "'"


@dataclass(frozen=True)
class Store:
    """An S3-compatible store. Values come from the environment, as the AWS SDK reads them."""

    endpoint: str | None
    region: str
    access_key: str
    secret_key: str

    @classmethod
    def from_env(cls) -> Store:
        try:
            access_key = os.environ["AWS_ACCESS_KEY_ID"]
            secret_key = os.environ["AWS_SECRET_ACCESS_KEY"]
        except KeyError as missing:
            raise SystemExit(f"{missing.args[0]} is not set") from None
        return cls(
            endpoint=os.environ.get("S3_ENDPOINT") or None,
            region=os.environ.get("S3_REGION", "us-east-1"),
            access_key=access_key,
            secret_key=secret_key,
        )

    def duckdb_secret_sql(self) -> str:
        """The CREATE SECRET statement that lets DuckDB reach this store."""
        options = [
            "TYPE s3",
            f"KEY_ID {sql_literal(self.access_key)}",
            f"SECRET {sql_literal(self.secret_key)}",
            f"REGION {sql_literal(self.region)}",
        ]
        if self.endpoint:
            url = urlparse(self.endpoint)
            options += [
                f"ENDPOINT {sql_literal(url.netloc)}",
                "URL_STYLE 'path'",
                f"USE_SSL {'true' if url.scheme == 'https' else 'false'}",
            ]
        return f"CREATE SECRET store ({', '.join(options)});"


@dataclass(frozen=True)
class Job:
    """One conversion of a partitioned Parquet dataset from a source prefix to a destination."""

    job_id: str
    source_bucket: str
    source_prefix: str
    dest_bucket: str
    dest_prefix: str
    ledger_path: Path

    @property
    def staging_prefix(self) -> str:
        return f"_staging/{self.job_id}/"

    @property
    def marker_key(self) -> str:
        return f"{self.dest_prefix}/_SUCCESS"

    def source_url(self, unit: str) -> str:
        return f"s3://{self.source_bucket}/{self.source_prefix}/{unit}/*.parquet"

    def staged_key(self, attempt: str, unit: str) -> str:
        return f"{self.staging_prefix}{attempt}/{unit}/part-0.parquet"

    def final_key(self, unit: str) -> str:
        return f"{self.dest_prefix}/{unit}/part-0.parquet"
