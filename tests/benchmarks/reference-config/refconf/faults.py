"""Fault injection: stop the job at a named point, the way a crash or a kill would.

A fault is written `point` or `point@where`, for example `after_write@day=1` or
`during_promotion@1`. The action is `kill`, which sends SIGKILL to the process so that no cleanup
code runs, or `raise`, which raises InjectedFault so that tests can run the job in-process.
"""

from __future__ import annotations

import os
import signal
from dataclasses import dataclass
from typing import Literal

POINTS = (
    "before_write",
    "during_write",
    "after_write",
    "after_check",
    "after_ledger",
    "during_promotion",
    "before_marker",
    "after_marker",
)
Action = Literal["kill", "raise"]


class InjectedFault(RuntimeError):
    """Raised in place of a kill when the action is `raise`."""


class FaultMissed(RuntimeError):
    """An armed fault never fired, so the scenario did not reproduce."""


@dataclass(frozen=True)
class Fault:
    point: str
    where: str | None
    action: Action = "kill"

    @classmethod
    def parse(cls, spec: str | None, action: Action = "kill") -> Fault | None:
        if not spec:
            return None
        point, _, where = spec.partition("@")
        if point not in POINTS:
            raise ValueError(f"unknown fault point {point!r}; expected one of {', '.join(POINTS)}")
        if action not in ("kill", "raise"):
            raise ValueError(f"unknown fault action {action!r}")
        return cls(point, where or None, action)

    @classmethod
    def from_env(cls) -> Fault | None:
        return cls.parse(
            os.environ.get("REFCONF_FAULT"), os.environ.get("REFCONF_FAULT_ACTION", "kill")
        )  # type: ignore[arg-type]

    def __str__(self) -> str:
        return self.point + (f"@{self.where}" if self.where else "")


class Faults:
    """Checks fault points as the job passes them."""

    def __init__(self, fault: Fault | None) -> None:
        self.fault = fault
        self.fired = False

    def armed(self, point: str, where: str | None = None) -> bool:
        f = self.fault
        return f is not None and f.point == point and (f.where is None or f.where == where)

    def at(self, point: str, where: str | None = None) -> None:
        if self.armed(point, where):
            self.fire()

    def fire(self) -> None:
        self.fired = True
        assert self.fault is not None
        if self.fault.action == "kill":
            os.kill(os.getpid(), signal.SIGKILL)
        raise InjectedFault(str(self.fault))
