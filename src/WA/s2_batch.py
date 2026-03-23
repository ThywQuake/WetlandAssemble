"""Batch Sentinel-2 reference downloads driven by entropy hotspot CSV files."""

from __future__ import annotations

import ast
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from WA.comparison.hotspots import EntropyHotspot
from WA.config import AppConfig
from WA.loader_probe import make_json_safe
from WA.utils.progress import tqdm
from WA.validation import EarthEngineClient
from WA.validation.s2_reference import download_s2_reference


@dataclass(frozen=True)
class Phase3S2RunOutput:
    """Summary of one batch S2 download run."""

    hotspot_csv_path: Path
    target_time: pd.Timestamp
    artifact_manifest_path: Path
    hotspot_count: int
    status_counts: dict[str, int]


def discover_hotspot_csv_files(
    phase3_root: str | Path,
) -> list[Path]:
    """Find hotspot CSV files written by fine-grained probe scripts."""
    root = Path(phase3_root)
    return sorted(root.glob("**/hotspots.csv"))


def load_hotspots_csv(path: str | Path) -> list[EntropyHotspot]:
    """Parse a hotspots.csv into EntropyHotspot instances."""
    csv_path = Path(path)
    try:
        frame = pd.read_csv(csv_path)
    except EmptyDataError:
        return []

    if frame.empty:
        return []

    hotspots: list[EntropyHotspot] = []
    for row in frame.to_dict("records"):
        hotspots.append(
            EntropyHotspot(
                hotspot_id=str(row["hotspot_id"]),
                region_slug=str(row["region_slug"]),
                bbox=_parse_bbox(row["bbox"]),
                center_lon=float(row["center_lon"]),
                center_lat=float(row["center_lat"]),
                mean_entropy=float(row["mean_entropy"]),
                max_entropy=float(row["max_entropy"]),
                cell_count=int(row["cell_count"]),
                class_disagreement_summary=_parse_summary(
                    row.get("class_disagreement_summary", "{}")
                ),
            )
        )
    return hotspots


def download_phase3_s2_batch(
    app_config: AppConfig,
    *,
    phase3_root: str | Path = "results/phase3/fine",
    results_root: str | Path = "results",
    target_time: str | pd.Timestamp = "2019-07-01",
    allow_interactive_auth: bool = False,
    skip_existing: bool = True,
) -> list[Phase3S2RunOutput]:
    """Discover hotspot CSVs and download S2 reference for each hotspot."""
    csv_files = discover_hotspot_csv_files(phase3_root)
    gee_client = EarthEngineClient.from_config(app_config.gee)
    outputs: list[Phase3S2RunOutput] = []
    timestamp = pd.Timestamp(target_time)

    print(
        f"[s2-batch] discovered {len(csv_files)} hotspots.csv file(s) under {phase3_root}",
        flush=True,
    )

    run_progress = tqdm(csv_files, desc="Phase3 S2 runs", unit="file", dynamic_ncols=True)
    for csv_path in run_progress:
        hotspots = load_hotspots_csv(csv_path)
        run_progress.set_postfix_str(f"{csv_path.parent.name}", refresh=False)

        artifacts_payload: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        aoi_progress = tqdm(
            hotspots,
            desc=f"S2 {csv_path.parent.name}",
            unit="aoi",
            dynamic_ncols=True,
            leave=False,
        )

        for hotspot in aoi_progress:
            artifact = download_s2_reference(
                hotspot,
                gee_client,
                target_time=timestamp,
                results_root=results_root,
                allow_interactive_auth=allow_interactive_auth,
                skip_existing=skip_existing,
            )
            status_counts[artifact.status] += 1
            artifacts_payload.append(
                {
                    "hotspot_id": hotspot.hotspot_id,
                    "artifact": asdict(artifact),
                }
            )
            aoi_progress.set_postfix_str(
                f"{hotspot.region_slug}:{artifact.status}", refresh=False
            )
        aoi_progress.close()

        manifest_path = csv_path.parent / "s2_artifacts.json"
        manifest_path.write_text(
            json.dumps(
                make_json_safe(
                    {
                        "hotspot_csv_path": csv_path,
                        "target_time": timestamp,
                        "results_root": Path(results_root),
                        "hotspot_count": len(hotspots),
                        "status_counts": dict(status_counts),
                        "artifacts": artifacts_payload,
                    }
                ),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            ),
            encoding="utf-8",
        )

        output = Phase3S2RunOutput(
            hotspot_csv_path=csv_path,
            target_time=timestamp,
            artifact_manifest_path=manifest_path,
            hotspot_count=len(hotspots),
            status_counts=dict(status_counts),
        )
        outputs.append(output)
        print(
            f"[s2-batch] {csv_path.parent.name}: "
            f"{len(hotspots)} hotspot(s), status_counts={dict(status_counts)}",
            flush=True,
        )

    run_progress.close()
    return outputs


def _parse_bbox(value: object) -> tuple[float, float, float, float]:
    if isinstance(value, str):
        parsed = ast.literal_eval(value)
    else:
        parsed = value
    if not isinstance(parsed, (list, tuple)) or len(parsed) != 4:
        raise ValueError(f"Invalid bbox literal: {value!r}")
    return (float(parsed[0]), float(parsed[1]), float(parsed[2]), float(parsed[3]))


def _parse_summary(value: object) -> dict[str, float]:
    if isinstance(value, dict):
        return {str(k): float(v) for k, v in value.items()}
    if isinstance(value, str):
        parsed = ast.literal_eval(value)
        if isinstance(parsed, dict):
            return {str(k): float(v) for k, v in parsed.items()}
    return {}
