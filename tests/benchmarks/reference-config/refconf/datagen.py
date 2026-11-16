"""Deterministic source data: a Parquet dataset partitioned by `day`.

The same arguments always produce the same rows, so the reference configuration and UDC can be
compared on identical input.
"""

from __future__ import annotations

from refconf.config import sql_literal
from refconf.duckdb_cli import DuckDB


def partition_sql(bucket: str, prefix: str, day: int, rows: int, seed: int) -> str:
    url = f"s3://{bucket}/{prefix}/day={day}/data_0.parquet"
    return (
        "COPY (SELECT i AS id, "
        f"{day} AS day, "
        f"hash(i + {seed}) AS h, "
        f"sha256(CAST(i + {seed} AS VARCHAR)) AS payload "
        f"FROM range({rows}) t(i)) "
        f"TO {sql_literal(url)} (FORMAT parquet, COMPRESSION zstd);"
    )


def generate(
    duck: DuckDB, bucket: str, prefix: str, partitions: int, rows: int, seed: int = 0
) -> int:
    """Write `partitions` files of `rows` rows each; return the total row count."""
    duck.run("\n".join(partition_sql(bucket, prefix, d, rows, seed) for d in range(partitions)))
    return partitions * rows
