"""Shared download utilities for GEE-backed reference imagery workflows."""

from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, cast
from urllib.request import urlopen

import pandas as pd

DEFAULT_DOWNLOAD_TIMEOUT = 300


def download_file(url: str, destination: Path, *, timeout: int = DEFAULT_DOWNLOAD_TIMEOUT) -> None:
    """Atomic file download with streaming write and configurable timeout."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        with urlopen(url, timeout=timeout) as response:
            with open(temp_path, "wb") as f:
                shutil.copyfileobj(response, f)
        temp_path.replace(destination)
    finally:
        temp_path.unlink(missing_ok=True)


def collection_size(collection: object) -> int:
    """Count images in an Earth Engine collection."""

    size_value = cast(Any, collection).size()
    if hasattr(size_value, "getInfo"):
        return int(size_value.getInfo())
    return int(size_value)


def format_date(timestamp: pd.Timestamp) -> str:
    """Format timestamp for GEE date filter."""

    return timestamp.strftime("%Y-%m-%d")


def month_window(target_time: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Compute month-boundary window from target time."""

    month_start = pd.Timestamp(target_time).normalize().replace(day=1)
    month_end = month_start + pd.offsets.MonthBegin(1)
    return month_start, pd.Timestamp(month_end)


def classify_failure(exc: Exception) -> str:
    """Classify a GEE download failure into a terminal status string."""

    message = str(exc).lower()
    if "32 mb" in message or "10000" in message or "request too large" in message:
        return "download_limit_exceeded"
    return "download_failed"
