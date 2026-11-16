"""Fetch a pinned DuckDB CLI and run SQL with it."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import platform
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

from refconf.config import Store, sql_literal

VERSION = "2.0.0"
# Release assets and the SHA-256 digests GitHub publishes for them.
ASSETS = {
    ("Linux", "x86_64"): (
        "duckdb-cli-linux-amd64.tar.gz",
        "c6507206baf7793c6013dbd82368469a45f20dc0e17a6f92f204602f652ed2bc",
    ),
    ("Linux", "aarch64"): (
        "duckdb-cli-linux-arm64.tar.gz",
        "859e1875d2a9515fbb4bf8871061437a14af82320da68c753f094c4b776348fe",
    ),
    ("Darwin", "arm64"): (
        "duckdb-cli-osx-arm64.tar.gz",
        "188a36fe8883ef52e69165a0cbb6031ef679c8e6c448a1ce22951964149b7f96",
    ),
    ("Darwin", "x86_64"): (
        "duckdb-cli-osx-amd64.tar.gz",
        "fbc7013ba09d117396dabf16783281c2add47fc01cdac4855464a03526dc96ee",
    ),
}
RELEASES = "https://github.com/duckdb/duckdb/releases/download"


class DuckDBError(RuntimeError):
    """The CLI exited with an error."""


class ChildStopped(RuntimeError):
    """The CLI was killed because a stop condition became true."""


def verify_and_extract(archive: Path, expected_sha256: str, dest: Path) -> Path:
    """Check the archive digest and extract only the `duckdb` executable."""
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise RuntimeError(f"{archive.name}: SHA-256 {digest} does not match {expected_sha256}")
    with tarfile.open(archive) as tar:
        member = tar.getmember("duckdb")
        if not member.isfile():
            raise RuntimeError(f"{archive.name}: 'duckdb' is not a regular file")
        source = tar.extractfile(member)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read())
    dest.chmod(0o755)
    return dest


def ensure(bin_dir: Path, system: str | None = None, machine: str | None = None) -> Path:
    """Return the pinned DuckDB CLI under bin_dir, downloading and verifying it if needed."""
    binary = bin_dir / f"duckdb-{VERSION}"
    if binary.exists():
        return binary
    key = (system or platform.system(), machine or platform.machine())
    if key not in ASSETS:
        raise RuntimeError(f"no pinned DuckDB {VERSION} CLI for {key[0]} {key[1]}")
    asset, sha256 = ASSETS[key]
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / asset
        urllib.request.urlretrieve(f"{RELEASES}/v{VERSION}/{asset}", archive)  # noqa: S310
        return verify_and_extract(archive, sha256, binary)


def child_env() -> dict[str, str]:
    """The environment for the CLI.

    DuckDB 2.0 switches to an "agent mode" output format when AI_AGENT is set and stdout is not a
    terminal; the reference configuration must behave the same whoever runs it.
    """
    return {k: v for k, v in os.environ.items() if k != "AI_AGENT"}


class DuckDB:
    """Runs SQL through the DuckDB CLI, as a shell script around it would."""

    def __init__(self, binary: Path, store: Store, poll_interval: float = 0.05) -> None:
        self.binary = binary
        self.store = store
        self.poll_interval = poll_interval

    def run(self, sql: str, stop_when: Callable[[], bool] | None = None) -> str:
        """Run SQL after creating the store secret, and return the CLI's standard output.

        If stop_when is given, it is polled while the CLI runs; when it returns True the CLI is
        killed and ChildStopped is raised.
        """
        script = self.store.duckdb_secret_sql() + "\n" + sql + "\n"
        # Output goes to files, not pipes, so a long-running statement can never block on a full
        # pipe while it is being polled.
        with tempfile.TemporaryFile("w+") as out, tempfile.TemporaryFile("w+") as err:
            process = subprocess.Popen(
                [str(self.binary), "-no-agent", "-csv", "-bail"],
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                env=child_env(),
                text=True,
            )
            assert process.stdin is not None
            process.stdin.write(script)
            process.stdin.close()
            while process.poll() is None:
                if stop_when is not None and stop_when():
                    process.kill()
                    process.wait()
                    raise ChildStopped("DuckDB was killed by a stop condition")
                time.sleep(self.poll_interval)
            out.seek(0)
            err.seek(0)
            stdout, stderr = out.read(), err.read()
        if process.returncode != 0:
            raise DuckDBError(stderr.strip() or f"exit status {process.returncode}")
        return stdout

    def query(self, select: str) -> list[dict[str, str]]:
        """Run one SELECT and return its rows."""
        return result_after_marker(self.run(f".print {RESULT_MARKER}\n{select}"))

    def count(self, url: str) -> int:
        rows = self.query(f"SELECT count(*) AS n FROM read_parquet({sql_literal(url)});")
        return int(rows[0]["n"])

    def copy(
        self, source_url: str, dest_url: str, stop_when: Callable[[], bool] | None = None
    ) -> None:
        self.run(
            f"COPY (SELECT * FROM read_parquet({sql_literal(source_url)})) "
            f"TO {sql_literal(dest_url)} (FORMAT parquet, COMPRESSION zstd);",
            stop_when=stop_when,
        )


RESULT_MARKER = "__refconf_result__"


def result_after_marker(stdout: str) -> list[dict[str, str]]:
    """Parse the CSV result printed after the marker line."""
    lines = stdout.splitlines()
    if RESULT_MARKER not in lines:
        raise DuckDBError("no result marker in DuckDB output")
    block = lines[lines.index(RESULT_MARKER) + 1 :]
    return list(csv.DictReader(io.StringIO("\n".join(block))))
