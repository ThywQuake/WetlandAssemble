#!/usr/bin/env python3
"""Run verbose rough binary diagnostics against the real HPC dataset paths."""

from __future__ import annotations

import logging
import os
import sys
import traceback
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
    from WA.rough_probe import main

    return main()


def _coerce_exit_code(code: object) -> int:
    """Normalize arbitrary exit payloads into a shell-safe integer code."""

    if code is None:
        return 0
    if isinstance(code, bool):
        return int(code)
    if isinstance(code, int):
        return code
    return 1


def _main() -> int:
    """Run the CLI without delegating exception rendering to ambient hooks."""

    try:
        return _coerce_exit_code(_run())
    except SystemExit as exc:
        return _coerce_exit_code(exc.code)
    except BaseException as exc:
        traceback.print_exception(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = _main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
