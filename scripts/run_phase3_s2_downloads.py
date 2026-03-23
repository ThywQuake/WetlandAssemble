#!/usr/bin/env python3
"""Batch-download Sentinel-2 artifacts from Phase 3 hotspot outputs."""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _coerce_exit_code(code: object) -> int:
    if code is None:
        return 0
    if isinstance(code, bool):
        return int(code)
    if isinstance(code, int):
        return code
    return 1


def _main() -> int:
    try:
        parser = argparse.ArgumentParser(
            description="Batch-download Sentinel-2 reference for Phase 3 hotspots."
        )
        parser.add_argument("--phase3-root", default="results/phase3/fine")
        parser.add_argument("--results-root", default="results")
        parser.add_argument("--target-time", default="2016-07-01")
        parser.add_argument("--allow-interactive-auth", action="store_true")
        parser.add_argument(
            "--skip-existing",
            action=argparse.BooleanOptionalAction,
            default=True,
        )
        parser.add_argument("--dataset-config", default="config/datasets.yaml")
        parser.add_argument("--gee-config", default="config/gee_config.yaml")
        args = parser.parse_args()

        from WA.config import load_config
        from WA.s2_batch import download_phase3_s2_batch

        app_config = load_config(args.dataset_config, args.gee_config)
        download_phase3_s2_batch(
            app_config,
            phase3_root=args.phase3_root,
            results_root=args.results_root,
            target_time=args.target_time,
            allow_interactive_auth=args.allow_interactive_auth,
            skip_existing=args.skip_existing,
        )
        return 0
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
