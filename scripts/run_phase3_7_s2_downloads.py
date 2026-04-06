#!/usr/bin/env python3
"""Batch-download Sentinel-2 artifacts from Phase 3.7 hotspot outputs."""

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
        from WA.s2_batch import (
            DEFAULT_PHASE37_HOTSPOTS_MANIFEST,
            DEFAULT_PHASE37_S2_RESULTS_ROOT,
            DEFAULT_PHASE37_S2_TARGET_TIME,
        )

        parser = argparse.ArgumentParser(
            description="Batch-download Sentinel-2 reference for Phase 3.7 hotspots."
        )
        parser.add_argument(
            "--hotspots-manifest",
            default=str(DEFAULT_PHASE37_HOTSPOTS_MANIFEST),
        )
        parser.add_argument(
            "--results-root",
            default=str(DEFAULT_PHASE37_S2_RESULTS_ROOT),
        )
        parser.add_argument(
            "--target-time",
            default=str(DEFAULT_PHASE37_S2_TARGET_TIME.date()),
        )
        parser.add_argument("--allow-interactive-auth", action="store_true")
        parser.add_argument(
            "--no-skip",
            action="store_false",
            dest="skip_existing",
            help="即使本地已存在 quicklook/chip 也重新下载",
        )
        parser.add_argument("--dataset-config", default="config/datasets.yaml")
        parser.add_argument("--gee-config", default="config/gee_config.yaml")
        args = parser.parse_args()

        from WA.config import load_config
        from WA.s2_batch import download_phase37_s2_batch

        app_config = load_config(args.dataset_config, args.gee_config)
        download_phase37_s2_batch(
            app_config,
            hotspots_manifest=args.hotspots_manifest,
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
