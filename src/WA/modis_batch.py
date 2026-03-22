from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from WA.comparison.focus_areas import RoughFocusArea
from WA.config import AppConfig, load_config
from WA.loader_probe import make_json_safe
from WA.utils.progress import tqdm
from WA.validation import EarthEngineClient, download_modis_reference


@dataclass(frozen=True)
class Phase2ModisRunOutput:
    region_id: str
    target_time: pd.Timestamp
    focus_areas_path: Path
    artifact_manifest_path: Path
    aoi_count: int
    status_counts: dict[str, int]


def discover_phase2_focus_area_files(
    phase2_root: str | Path,
    *,
    region_ids: list[str] | None = None,
    target_times: list[str | pd.Timestamp] | None = None,
) -> list[Path]:
    root = Path(phase2_root)
    requested_regions = set(region_ids or [])
    requested_months = {
        _target_month_slug(timestamp) for timestamp in (target_times or [])
    }

    discovered: list[Path] = []
    for path in sorted(root.glob("*/*/focus_areas.csv")):
        region_id = path.parent.parent.name
        month_slug = path.parent.name
        if requested_regions and region_id not in requested_regions:
            continue
        if requested_months and month_slug not in requested_months:
            continue
        discovered.append(path)
    return discovered


def load_focus_areas_csv(
    path: str | Path,
    *,
    region_id: str,
) -> list[dict[str, Any]]:
    csv_path = Path(path)
    try:
        frame = pd.read_csv(csv_path)
    except EmptyDataError:
        return []

    if frame.empty:
        return []

    required_columns = {
        "aoi_id",
        "region_slug",
        "target_time",
        "bbox",
        "center_lon",
        "center_lat",
        "disagreement_score",
        "participant_count",
        "wetland_vote_fraction",
    }
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(
            f"focus_areas.csv at {csv_path} is missing required columns: {', '.join(missing)}"
        )

    records: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        original_aoi_id = str(row["aoi_id"])
        materialized_aoi_id = f"{region_id}__{original_aoi_id}"
        focus_area = RoughFocusArea(
            aoi_id=materialized_aoi_id,
            region_slug=str(row["region_slug"]),
            target_time=pd.Timestamp(row["target_time"]),
            bbox=_parse_bbox(row["bbox"]),
            center_lon=float(row["center_lon"]),
            center_lat=float(row["center_lat"]),
            disagreement_score=float(row["disagreement_score"]),
            participant_count=int(row["participant_count"]),
            wetland_vote_fraction=_optional_float(row["wetland_vote_fraction"]),
        )
        records.append(
            {
                "original_aoi_id": original_aoi_id,
                "focus_area": focus_area,
            }
        )
    return records


def download_phase2_modis_batch(
    app_config: AppConfig,
    *,
    phase2_root: str | Path = "results/phase2/rough",
    results_root: str | Path = "results",
    region_ids: list[str] | None = None,
    target_times: list[str | pd.Timestamp] | None = None,
    allow_interactive_auth: bool = False,
    skip_existing: bool = True,
) -> list[Phase2ModisRunOutput]:
    focus_files = discover_phase2_focus_area_files(
        phase2_root,
        region_ids=region_ids,
        target_times=target_times,
    )
    gee_client = EarthEngineClient.from_config(app_config.gee)
    outputs: list[Phase2ModisRunOutput] = []
    batch_manifest_runs: list[dict[str, Any]] = []

    print(
        f"[modis-batch] discovered {len(focus_files)} focus_areas.csv file(s) under {phase2_root}",
        flush=True,
    )
    run_progress = tqdm(
        focus_files,
        desc="Phase2 MODIS runs",
        unit="run",
        dynamic_ncols=True,
    )
    for focus_areas_path in run_progress:
        region_id = focus_areas_path.parent.parent.name
        target_time = _month_slug_to_timestamp(focus_areas_path.parent.name)
        run_progress.set_postfix_str(f"{region_id}/{target_time:%Y%m}", refresh=False)
        focus_area_records = load_focus_areas_csv(
            focus_areas_path,
            region_id=region_id,
        )

        artifacts_payload: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        aoi_progress = tqdm(
            focus_area_records,
            desc=f"MODIS {region_id} {target_time:%Y%m}",
            unit="aoi",
            dynamic_ncols=True,
            leave=False,
        )
        for record in aoi_progress:
            focus_area = record["focus_area"]
            artifact = download_modis_reference(
                focus_area,
                gee_client,
                results_root=results_root,
                allow_interactive_auth=allow_interactive_auth,
                skip_existing=skip_existing,
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

        artifact_manifest_path = focus_areas_path.parent / "modis_artifacts.json"
        manifest_payload = {
            "region_id": region_id,
            "target_time": target_time,
            "focus_areas_path": focus_areas_path,
            "results_root": Path(results_root),
            "allow_interactive_auth": allow_interactive_auth,
            "skip_existing": skip_existing,
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

        output = Phase2ModisRunOutput(
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
            "[modis-batch] "
            f"{region_id}/{target_time:%Y%m}: "
            f"{len(focus_area_records)} AOI(s), status_counts={dict(status_counts)}",
            flush=True,
        )

    run_progress.close()

    batch_manifest_path = Path(phase2_root) / "modis_download_manifest.json"
    batch_manifest_path.write_text(
        json.dumps(
            make_json_safe(
                {
                    "phase2_root": Path(phase2_root),
                    "results_root": Path(results_root),
                    "allow_interactive_auth": allow_interactive_auth,
                    "skip_existing": skip_existing,
                    "runs": batch_manifest_runs,
                }
            ),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ),
            encoding="utf-8",
    )
    print(f"[modis-batch] wrote batch manifest: {batch_manifest_path}", flush=True)
    return outputs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Batch-download MODIS rough-truth artifacts from Phase 2 focus_areas.csv outputs."
        )
    )
    parser.add_argument("--phase2-root", default="results/phase2/rough")
    parser.add_argument("--results-root", default="results")
    parser.add_argument("--region", action="append", default=[])
    parser.add_argument("--target-time", action="append", default=[])
    parser.add_argument("--allow-interactive-auth", action="store_true")
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
    download_phase2_modis_batch(
        app_config,
        phase2_root=args.phase2_root,
        results_root=args.results_root,
        region_ids=args.region,
        target_times=args.target_time,
        allow_interactive_auth=args.allow_interactive_auth,
        skip_existing=args.skip_existing,
    )
    return 0


def _parse_bbox(value: object) -> tuple[float, float, float, float]:
    if isinstance(value, str):
        parsed = ast.literal_eval(value)
    else:
        parsed = value
    if not isinstance(parsed, (list, tuple)) or len(parsed) != 4:
        raise ValueError(f"Invalid bbox literal: {value!r}")
    return (
        float(parsed[0]),
        float(parsed[1]),
        float(parsed[2]),
        float(parsed[3]),
    )


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _target_month_slug(value: str | pd.Timestamp) -> str:
    return f"{pd.Timestamp(value):%Y%m}"


def _month_slug_to_timestamp(month_slug: str) -> pd.Timestamp:
    return pd.Timestamp(f"{month_slug[:4]}-{month_slug[4:6]}-01")
