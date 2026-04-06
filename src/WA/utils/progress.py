"""Progress helpers with a safe no-op fallback.

The project primarily runs on HPC and local Python 3.13 environments where
`tqdm` can be unavailable or can crash while initializing multiprocessing
locks. Progress reporting is non-essential, so the default is a safe wrapper
that degrades to a no-op progress object when `tqdm` is missing or unsafe.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Iterable, Iterator
from typing import Any, TypeVar

try:
    from tqdm.auto import tqdm as _real_tqdm
except Exception:  # pragma: no cover
    _real_tqdm = None

_TQDM_FORCE_ENV = "WA_FORCE_TQDM"
_PROGRESS_LOGGER = logging.getLogger("WA.progress")

_Item = TypeVar("_Item")


class _NoOpProgress:
    """Iterable progress object compatible with the subset of `tqdm` we use."""

    def __init__(self, iterable: Iterable[Any] | None = None) -> None:
        self._iterable = iterable

    def __iter__(self) -> Iterator[Any]:
        if self._iterable is None:
            return iter(())
        return iter(self._iterable)

    def update(self, _count: int = 1) -> None:
        return None

    def set_postfix_str(self, _value: str, refresh: bool = True) -> None:
        return None

    def close(self) -> None:
        return None


class _LogProgress:
    """Fallback progress reporter that emits periodic log lines."""

    def __init__(
        self,
        iterable: Iterable[Any] | None = None,
        *,
        total: int | None = None,
        desc: str | None = None,
        unit: str = "item",
        mininterval: float = 5.0,
    ) -> None:
        self._iterable = iterable
        self._total = total if total is not None else _iterable_length(iterable)
        self._desc = desc or "Progress"
        self._unit = unit
        self._mininterval = float(mininterval)
        self._count = 0
        self._postfix = ""
        self._last_emit = 0.0
        self._started = False
        self._closed = False

    def __iter__(self) -> Iterator[Any]:
        if self._iterable is None:
            return iter(())
        self._emit(force=True)
        try:
            for item in self._iterable:
                yield item
                self.update(1)
        finally:
            self.close()

    def update(self, count: int = 1) -> None:
        self._count += count
        self._emit()

    def set_postfix_str(self, value: str, refresh: bool = True) -> None:
        self._postfix = value
        if refresh:
            self._emit(force=True)

    def close(self) -> None:
        if self._closed:
            return
        self._emit(force=True)
        self._closed = True

    def _emit(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not self._started:
            self._started = True
            force = True
        if not force and now - self._last_emit < self._mininterval:
            return
        _PROGRESS_LOGGER.info(self._message())
        self._last_emit = now

    def _message(self) -> str:
        message = self._desc
        if self._total is not None and self._total > 0:
            ratio = min(max(self._count / self._total, 0.0), 1.0)
            width = 20
            filled = min(width, int(round(ratio * width)))
            bar = "#" * filled + "-" * (width - filled)
            message += f" [{bar}] {self._count}/{self._total} {self._unit}"
            message += f" ({ratio:.0%})"
        else:
            message += f" {self._count} {self._unit}"
        if self._postfix:
            message += f" | {self._postfix}"
        return message


def _iterable_length(iterable: Iterable[Any] | None) -> int | None:
    if iterable is None:
        return None
    try:
        return len(iterable)  # type: ignore[arg-type]
    except Exception:
        return None


def _tqdm_enabled() -> bool:
    forced = os.environ.get(_TQDM_FORCE_ENV, "").strip().lower()
    if forced in {"1", "true", "yes", "on"}:
        return _real_tqdm is not None
    if _real_tqdm is None:
        return False
    return sys.version_info < (3, 13)


def tqdm(iterable: Iterable[Any] | None = None, *args: Any, **kwargs: Any) -> Any:
    """Return a real or no-op progress object.

    On Python 3.13, the local test environment can segfault while `tqdm`
    initializes multiprocessing locks. We therefore disable `tqdm` by default
    on 3.13+ unless explicitly re-enabled with `WA_FORCE_TQDM=1`.
    """

    if not _tqdm_enabled():
        total = kwargs.get("total")
        desc = kwargs.get("desc")
        unit = kwargs.get("unit", "item")
        mininterval = kwargs.get("mininterval", 5.0)
        if total is None:
            total = _iterable_length(iterable)
        if total is None and iterable is None:
            return _NoOpProgress(iterable)
        return _LogProgress(
            iterable,
            total=total,
            desc=desc,
            unit=unit,
            mininterval=mininterval,
        )
    return _real_tqdm(iterable, *args, **kwargs)
