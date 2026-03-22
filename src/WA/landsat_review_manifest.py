from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from WA.loader_probe import make_json_safe
from WA.modis_batch import discover_phase2_focus_area_files, load_focus_areas_csv


@dataclass(frozen=True)
class LandsatReviewRow:
    run_id: str
    region_id: str
    run_status: str
    target_time: pd.Timestamp
    aoi_type: str
    original_aoi_id: str
    materialized_aoi_id: str | None
    region_slug: str
    bbox: tuple[float, float, float, float]
    center_lon: float
    center_lat: float
    disagreement_score: float
    participant_count: int
    wetland_vote_fraction: float | None
    data_source: str
    image_status: str | None
    window_start: pd.Timestamp | None
    window_end: pd.Timestamp | None
    quicklook_path: str | None
    chip_path: str | None
    download_mode: str | None
    message: str | None
    collection_ids: tuple[str, ...]
    focus_areas_path: str
    metrics_path: str | None
    comparison_grids_path: str | None
    participant_surfaces_path: str | None
    metrics_row_count: int | None
    participant_dataset_ids: tuple[str, ...]
    mean_iou: float | None
    max_iou: float | None
    mean_f1_score: float | None
    min_kappa: float | None


def build_phase2_landsat_review_manifests(
    *,
    phase2_root: str | Path = "results/phase2/rough",
    region_ids: list[str] | None = None,
    target_times: list[str | pd.Timestamp] | None = None,
) -> list[LandsatReviewRow]:
    focus_files = discover_phase2_focus_area_files(
        phase2_root,
        region_ids=region_ids,
        target_times=target_times,
    )
    all_rows: list[LandsatReviewRow] = []

    for focus_areas_path in focus_files:
        run_dir = focus_areas_path.parent
        region_id = run_dir.parent.name
        target_time = pd.Timestamp(f"{run_dir.name[:4]}-{run_dir.name[4:6]}-01")
        run_summary = _load_json_if_exists(run_dir / "run_summary.json") or {}
        landsat_manifest = _load_json_if_exists(run_dir / "landsat_artifacts.json") or {}
        artifact_by_original = {
            record["original_aoi_id"]: record["artifact"]
            for record in landsat_manifest.get("artifacts", [])
            if isinstance(record, dict)
            and isinstance(record.get("original_aoi_id"), str)
            and isinstance(record.get("artifact"), dict)
        }
        metrics_summary = _summarize_metrics(run_dir / "pairwise_metrics.csv")
        focus_area_records = load_focus_areas_csv(focus_areas_path, region_id=region_id)

        run_rows: list[LandsatReviewRow] = []
        for record in focus_area_records:
            focus_area = record["focus_area"]
            artifact = artifact_by_original.get(record["original_aoi_id"], {})
            row = LandsatReviewRow(
                run_id=f"{region_id}_{target_time:%Y%m}",
                region_id=region_id,
                run_status=str(run_summary.get("status", "unknown")),
                target_time=target_time,
                aoi_type="rough",
                original_aoi_id=str(record["original_aoi_id"]),
                materialized_aoi_id=_optional_str(artifact.get("aoi_id")),
                region_slug=focus_area.region_slug,
                bbox=focus_area.bbox,
                center_lon=focus_area.center_lon,
                center_lat=focus_area.center_lat,
                disagreement_score=focus_area.disagreement_score,
                participant_count=focus_area.participant_count,
                wetland_vote_fraction=focus_area.wetland_vote_fraction,
                data_source="LANDSAT_C2_L2_MULTI",
                image_status=_optional_str(artifact.get("status")),
                window_start=_optional_timestamp(artifact.get("window_start")),
                window_end=_optional_timestamp(artifact.get("window_end")),
                quicklook_path=_optional_str(artifact.get("quicklook_path")),
                chip_path=_optional_str(artifact.get("chip_path")),
                download_mode=_optional_str(artifact.get("download_mode")),
                message=_optional_str(artifact.get("message")),
                collection_ids=tuple(str(item) for item in artifact.get("collection_ids", [])),
                focus_areas_path=str(focus_areas_path),
                metrics_path=_optional_str(_nested(run_summary, "output_files", "metrics_path")),
                comparison_grids_path=_optional_str(
                    _nested(run_summary, "output_files", "comparison_grids_path")
                ),
                participant_surfaces_path=_optional_str(
                    _nested(run_summary, "output_files", "participant_surfaces_path")
                ),
                metrics_row_count=metrics_summary["metrics_row_count"],
                participant_dataset_ids=tuple(
                    str(item) for item in run_summary.get("participant_dataset_ids", [])
                ),
                mean_iou=metrics_summary["mean_iou"],
                max_iou=metrics_summary["max_iou"],
                mean_f1_score=metrics_summary["mean_f1_score"],
                min_kappa=metrics_summary["min_kappa"],
            )
            run_rows.append(row)

        _write_run_review_manifest(run_dir, run_rows)
        all_rows.extend(run_rows)

    _write_batch_review_manifest(Path(phase2_root), all_rows)
    return all_rows


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build review manifests by merging rough outputs with Landsat artifacts."
    )
    parser.add_argument("--phase2-root", default="results/phase2/rough")
    parser.add_argument("--region", action="append", default=[])
    parser.add_argument("--target-time", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    rows = build_phase2_landsat_review_manifests(
        phase2_root=args.phase2_root,
        region_ids=args.region,
        target_times=args.target_time,
    )
    print(
        f"[landsat-review] wrote review manifest rows={len(rows)} under {args.phase2_root}",
        flush=True,
    )
    return 0


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return payload


def _summarize_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "metrics_row_count": None,
            "mean_iou": None,
            "max_iou": None,
            "mean_f1_score": None,
            "min_kappa": None,
        }
    frame = pd.read_csv(path)
    return {
        "metrics_row_count": int(len(frame)),
        "mean_iou": _float_or_none(frame["iou"].mean()) if "iou" in frame else None,
        "max_iou": _float_or_none(frame["iou"].max()) if "iou" in frame else None,
        "mean_f1_score": _float_or_none(frame["f1_score"].mean()) if "f1_score" in frame else None,
        "min_kappa": _float_or_none(frame["kappa"].min()) if "kappa" in frame else None,
    }


def _write_run_review_manifest(run_dir: Path, rows: list[LandsatReviewRow]) -> None:
    frame = pd.DataFrame([_row_to_record(row) for row in rows])
    csv_path = run_dir / "landsat_review_manifest.csv"
    json_path = run_dir / "landsat_review_manifest.json"
    frame.to_csv(csv_path, index=False)
    payload = make_json_safe({"rows": [_row_to_record(row) for row in rows]})
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _write_batch_review_manifest(root: Path, rows: list[LandsatReviewRow]) -> None:
    frame = pd.DataFrame([_row_to_record(row) for row in rows])
    csv_path = root / "landsat_review_manifest.csv"
    json_path = root / "landsat_review_manifest.json"
    frame.to_csv(csv_path, index=False)
    payload = make_json_safe({"rows": [_row_to_record(row) for row in rows]})
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _row_to_record(row: LandsatReviewRow) -> dict[str, Any]:
    return asdict(row)


def _nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_timestamp(value: object) -> pd.Timestamp | None:
    if value is None:
        return None
    return pd.Timestamp(value)


def _float_or_none(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)
