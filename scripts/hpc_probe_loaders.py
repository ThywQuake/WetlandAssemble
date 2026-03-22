#!/usr/bin/env python3
"""Run verbose loader diagnostics against the real HPC dataset paths."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logging.getLogger("rasterio").setLevel(logging.WARNING)
    logging.getLogger("rioxarray").setLevel(logging.WARNING)
    logging.getLogger("pyproj").setLevel(logging.WARNING)


def _run() -> int:
    _configure_logging()
    print("[bootstrap] configure WA geospatial runtime", flush=True)
    from WA._geo_env import configure_geospatial_runtime

    configure_geospatial_runtime()
    from WA.loader_probe import main

    return main()


if __name__ == "__main__":
    raise SystemExit(_run())
