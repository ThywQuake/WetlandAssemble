#!/usr/bin/env python3
# ruff: noqa: I001
"""Thin CLI wrapper for the shared Phase 4 percentage surface backbone."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.comparison.percentage_backbone import main  # noqa: E402


if __name__ == "__main__":
    main()
