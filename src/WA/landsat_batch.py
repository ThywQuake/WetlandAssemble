from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from WA.config import AppConfig, load_config
from WA.loader_probe import make_json_safe
from WA.modis_batch import discover_phase2_focus_area_files, load_focus_areas_csv
from WA.utils.progress import tqdm
from WA.validation import EarthEngineClient, download_landsat_reference


@dataclass(frozen=True)
class Phase2LandsatRunOutput:
    region_id: str
    target_time: pd.Timestamp
    focus_areas_path: Path
    artifact_manifest_path: Path
    aoi_count: int
    status_counts: dict[str, int]


def download_phase2_landsat_batch(
    app_config: AppConfig,
    *,
    phase2_root: str | Path = "results/phase2/rough",
    results_root: str | Path = "results",
    region_ids: list[str] | None = None,
    target_times: list[str | pd.Timestamp] | None = None,
    allow_interactive_auth: bool = False,
    skip_existing: bool = True,
    scale_meters: int = 250,
) -> list[Phase2LandsatRunOutput]:
    focus_files = discover_phase2_focus_area_files(
        phase2_root,
        region_ids=region_ids,
        target_times=target_times,
    )
    gee_client = EarthEngineClient.from_config(app_config.gee)
    outputs: list[Phase2LandsatRunOutput] = []
    batch_manifest_runs: list[dict[str, Any]] = []

    print(
        "[landsat-batch] "
        f"discovered {len(focus_files)} focus_areas.csv file(s) under {phase2_root}",
        flush=True,
    )
    run_progress = tqdm(
        focus_files,
        desc="Phase2 Landsat runs",
        unit="run",
        dynamic_ncols=True,
    )
    for focus_areas_path in run_progress:
        region_id = focus_areas_path.parent.parent.name
        month_slug = focus_areas_path.parent.name
        target_time = pd.Timestamp(f"{month_slug[:4]}-{month_slug[4:6]}-01")
        run_progress.set_postfix_str(f"{region_id}/{target_time:%Y%m}", refresh=False)
        focus_area_records = load_focus_areas_csv(
            focus_areas_path,
            region_id=region_id,
        )

        artifacts_payload: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        aoi_progress = tqdm(
            focus_area_records,
            desc=f"Landsat {region_id} {target_time:%Y%m}",
            unit="aoi",
            dynamic_ncols=True,
            leave=False,
        )
        for record in aoi_progress:
            focus_area = record["focus_area"]
            artifact = download_landsat_reference(
                focus_area,
                gee_client,
                results_root=results_root,
                allow_interactive_auth=allow_interactive_auth,
                skip_existing=skip_existing,
                scale_meters=scale_meters,
            )
            status_counts[artifact.status] += 1
            artifacts_payload.append(
                {
                    "original_aoi_id": record["original_aoi_id"],
                    "materialized_aoi_id": focus_area.aoi_id,
                    "artifact": asdict(artifact),
                }
            )
            aoi_progress.set_postfix_str(
                f"{focus_area.region_slug}:{artifact.status}",
                refresh=False,
            )
        aoi_progress.close()

        artifact_manifest_path = focus_areas_path.parent / "landsat_artifacts.json"
        manifest_payload = {
            "region_id": region_id,
            "target_time": target_time,
            "focus_areas_path": focus_areas_path,
            "results_root": Path(results_root),
            "allow_interactive_auth": allow_interactive_auth,
            "skip_existing": skip_existing,
            "scale_meters": scale_meters,
            "aoi_count": len(focus_area_records),
            "status_counts": dict(status_counts),
            "artifacts": artifacts_payload,
        }
        artifact_manifest_path.write_text(
            json.dumps(
                make_json_safe(manifest_payload),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            ),
            encoding="utf-8",
        )

        output = Phase2LandsatRunOutput(
            region_id=region_id,
            target_time=target_time,
            focus_areas_path=focus_areas_path,
            artifact_manifest_path=artifact_manifest_path,
            aoi_count=len(focus_area_records),
            status_counts=dict(status_counts),
        )
        outputs.append(output)
        batch_manifest_runs.append(asdict(output))
        print(
            "[landsat-batch] "
            f"{region_id}/{target_time:%Y%m}: "
            f"{len(focus_area_records)} AOI(s), status_counts={dict(status_counts)}",
            flush=True,
        )

    run_progress.close()

    batch_manifest_path = Path(phase2_root) / "landsat_download_manifest.json"
    batch_manifest_path.write_text(
        json.dumps(
            make_json_safe(
                {
                    "phase2_root": Path(phase2_root),
                    "results_root": Path(results_root),
                    "allow_interactive_auth": allow_interactive_auth,
                    "skip_existing": skip_existing,
                    "scale_meters": scale_meters,
                    "runs": batch_manifest_runs,
                }
            ),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    print(f"[landsat-batch] wrote batch manifest: {batch_manifest_path}", flush=True)
    return outputs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Batch-download Landsat rough-truth artifacts from Phase 2 focus_areas.csv outputs."
        )
    )
    parser.add_argument("--phase2-root", default="results/phase2/rough")
    parser.add_argument("--results-root", default="results")
    parser.add_argument("--region", action="append", default=[])
    parser.add_argument("--target-time", action="append", default=[])
    parser.add_argument("--allow-interactive-auth", action="store_true")
    parser.add_argument("--scale-meters", type=int, default=250)
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--dataset-config", default="config/datasets.yaml")
    parser.add_argument("--gee-config", default="config/gee_config.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    app_config = load_config(args.dataset_config, args.gee_config)
    download_phase2_landsat_batch(
        app_config,
        phase2_root=args.phase2_root,
        results_root=args.results_root,
        region_ids=args.region,
        target_times=args.target_time,
        allow_interactive_auth=args.allow_interactive_auth,
        skip_existing=args.skip_existing,
        scale_meters=args.scale_meters,
    )
    return 0
