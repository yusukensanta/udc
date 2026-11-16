"""A ledger of completed units: one JSON object per line, flushed and fsynced per entry."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Entry:
    unit: str
    attempt: str
    staged_key: str
    rows: int


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Entry]:
        """Completed units by name.

        A line that does not parse can only be a write torn by a kill, because every entry is
        fsynced before the job moves on; such a line is skipped.
        """
        if not self.path.exists():
            return {}
        entries: dict[str, Entry] = {}
        for line in self.path.read_text().splitlines():
            try:
                entry = Entry(**json.loads(line))
            except (json.JSONDecodeError, TypeError):
                continue
            entries[entry.unit] = entry
        return entries

    def append(self, entry: Entry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.path.read_bytes() if self.path.exists() else b""
        separator = "\n" if existing and not existing.endswith(b"\n") else ""
        with self.path.open("a") as f:
            f.write(separator + json.dumps(asdict(entry), sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
