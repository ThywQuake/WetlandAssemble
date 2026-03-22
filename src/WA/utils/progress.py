"""Progress helpers with a safe no-op fallback.

The project primarily runs on HPC and local Python 3.13 environments where
`tqdm` can be unavailable or can crash while initializing multiprocessing
locks. Progress reporting is non-essential, so the default is a safe wrapper
that degrades to a no-op progress object when `tqdm` is missing or unsafe.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable, Iterator
from typing import Any

try:
    from tqdm.auto import tqdm as _real_tqdm
except Exception:  # pragma: no cover
    _real_tqdm = None

_TQDM_FORCE_ENV = "WA_FORCE_TQDM"


class _NoOpProgress[Item]:
    """Iterable progress object compatible with the subset of `tqdm` we use."""

    def __init__(self, iterable: Iterable[Item] | None = None) -> None:
        self._iterable = iterable

    def __iter__(self) -> Iterator[Item]:
        if self._iterable is None:
            return iter(())
        return iter(self._iterable)

    def update(self, _count: int = 1) -> None:
        return None

    def set_postfix_str(self, _value: str, refresh: bool = True) -> None:
        return None

    def close(self) -> None:
        return None


def _tqdm_enabled() -> bool:
    forced = os.environ.get(_TQDM_FORCE_ENV, "").strip().lower()
    if forced in {"1", "true", "yes", "on"}:
        return _real_tqdm is not None
    if _real_tqdm is None:
        return False
    return sys.version_info < (3, 13)


def tqdm[Item](iterable: Iterable[Item] | None = None, *args: Any, **kwargs: Any) -> Any:
    """Return a real or no-op progress object.

    On Python 3.13, the local test environment can segfault while `tqdm`
    initializes multiprocessing locks. We therefore disable `tqdm` by default
    on 3.13+ unless explicitly re-enabled with `WA_FORCE_TQDM=1`.
    """

    if not _tqdm_enabled():
        return _NoOpProgress(iterable)
    return _real_tqdm(iterable, *args, **kwargs)
