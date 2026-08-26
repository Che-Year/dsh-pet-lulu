"""dsh integration: status sources and the status bubble.

The pet shows a small speech bubble with realtime information about a dsh
task (task name, phase, progress, GPU temperature).  The default source is
a deterministic mock so the feature works out of the box; a file source
reads a JSON status file that the dsh integration (or any script) can
write; a real dsh source can be plugged in by subclassing
:class:`StatusSource`.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class StatusInfo:
    """A snapshot of dsh task status."""

    task_name: Optional[str] = None
    phase: Optional[str] = None
    progress: Optional[float] = None  # 0..100, or None when unknown
    gpu_temp: Optional[float] = None  # degrees Celsius, or None
    message: Optional[str] = None

    @classmethod
    def from_mapping(cls, data: dict) -> "StatusInfo":
        def num(key: str) -> Optional[float]:
            value = data.get(key)
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        return cls(
            task_name=data.get("task_name") or data.get("task") or None,
            phase=data.get("phase") or None,
            progress=num("progress"),
            gpu_temp=num("gpu_temp") or num("gpu"),
            message=data.get("message") or None,
        )

    @property
    def empty(self) -> bool:
        return not (self.task_name or self.phase or self.progress is not None
                    or self.gpu_temp is not None or self.message)


class StatusSource:
    """Base class for status providers."""

    name = "base"

    def poll(self) -> Optional[StatusInfo]:
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - trivial hook
        pass


class MockStatusSource(StatusSource):
    """Deterministic simulated dsh task that cycles 0 -> 100%.

    Used for demos and acceptance testing without a real dsh task.
    """

    name = "mock"

    def __init__(self, cycle_seconds: float = 60.0) -> None:
        self.cycle_seconds = max(1.0, cycle_seconds)
        self._start = time.monotonic()
        self._last = time.monotonic()
        self._current = 0.0

    def poll(self) -> StatusInfo:
        now = time.monotonic()
        elapsed = now - self._start
        progress = (elapsed % self.cycle_seconds) / self.cycle_seconds * 100.0
        phase = _phase_for(progress)
        temp = 52.0 + (progress / 100.0) * 10.0  # 52..62 C
        return StatusInfo(
            task_name="demo-task",
            phase=phase,
            progress=progress,
            gpu_temp=temp,
            message="mock status source — write your own StatusSource for real dsh data",
        )


class FileStatusSource(StatusSource):
    """Reads a JSON status file written by the dsh integration.

    Expected shape::

        {"task_name": "...", "phase": "...", "progress": 42.0,
         "gpu_temp": 61.0, "message": "..."}

    The file is re-read only when its mtime changes, so an idle pet does not
    hammer the disk.
    """

    name = "file"

    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)
        self._mtime: Optional[float] = None
        self._cache: Optional[StatusInfo] = None

    def poll(self) -> Optional[StatusInfo]:
        try:
            stat = os.stat(self.path)
        except OSError:
            self._mtime = None
            return None
        if stat.st_mtime == self._mtime:
            return self._cache
        self._mtime = stat.st_mtime
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            info = StatusInfo.from_mapping(data) if isinstance(data, dict) else None
            self._cache = info
            return info
        except (OSError, ValueError):
            self._cache = None
            return None


class NoneStatusSource(StatusSource):
    """Always reports no status (bubble shows nothing)."""

    name = "none"

    def poll(self) -> Optional[StatusInfo]:
        return None


def make_status_source(kind: str, status_file: str = ".dsh_pet_status.json") -> StatusSource:
    kind = (kind or "mock").strip().lower()
    if kind == "file":
        return FileStatusSource(status_file)
    if kind == "none":
        return NoneStatusSource()
    return MockStatusSource()


# --------------------------------------------------------------------------- #
# bubble rendering
# --------------------------------------------------------------------------- #

_BAR_CHARS = "▏▎▍▌▋▊▉█"  # 1/8 steps


def _phase_for(progress: float) -> str:
    if progress < 1:
        return "warming up"
    if progress < 60:
        return "running"
    if progress < 95:
        return "almost done"
    return "finishing"


def progress_bar(progress: Optional[float], width: int) -> str:
    """Render a progress bar of exactly ``width`` characters, e.g. '[██░░] 42%'."""
    width = max(8, width)
    if progress is None:
        return "[" + "?" * (width - 2) + "]"
    progress = max(0.0, min(100.0, progress))
    # total = '[' + bar + '] ' + '100%'  (5 chars for the suffix)
    inner = max(1, width - 7)
    filled = progress / 100.0 * inner
    whole = int(filled)
    frac = filled - whole
    bar = "█" * whole
    if frac > 0 and whole < inner:
        bar += _BAR_CHARS[int(frac * 8) % 8]
    bar += "░" * (inner - len(bar))
    return f"[{bar}] {progress:3.0f}%"


def format_status(info: Optional[StatusInfo], width: int = 40) -> List[str]:
    """Turn a StatusInfo into bubble lines (list of plain strings)."""
    if info is None or info.empty:
        return []
    lines: List[str] = []
    if info.task_name:
        lines.append(_clip(info.task_name, width))
    if info.phase:
        lines.append(_clip(f"· {info.phase}", width))
    if info.progress is not None or info.message:
        lines.append(progress_bar(info.progress, min(width, 24)))
    if info.message:
        lines.append(_clip("· " + info.message, width))
    if info.gpu_temp is not None:
        lines.append(_clip(f"· GPU {info.gpu_temp:.0f}°C", width))
    return lines


def _clip(text: str, width: int) -> str:
    if width <= 0:
        return ""
    return text if len(text) <= width else text[: max(0, width - 1)] + "…"
