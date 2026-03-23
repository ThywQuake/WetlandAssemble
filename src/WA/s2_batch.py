"""Batch Sentinel-2 reference downloads driven by fine-grained probe JSON manifests."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from WA.comparison.hotspots import EntropyHotspot
from WA.config import AppConfig
from WA.loader_probe import make_json_safe
from WA.utils.progress import tqdm
from WA.validation import EarthEngineClient
from WA.validation.s2_reference import download_s2_reference


@dataclass(frozen=True)
class Phase3S2RunOutput:
    """Summary of one batch S2 download run."""

    manifest_path: Path
    target_time: pd.Timestamp
    artifact_manifest_path: Path
    hotspot_count: int
    status_counts: dict[str, int]


def discover_probe_manifests(
    phase3_root: str | Path,
) -> list[Path]:
    """Find fine_grained_probe.json files written by probe scripts."""
    root = Path(phase3_root)
    return sorted(root.glob("**/fine_grained_probe.json"))


def load_hotspots_from_manifest(path: str | Path) -> list[EntropyHotspot]:
    """Parse hotspots from a fine_grained_probe.json manifest."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_hotspots = data.get("hotspots", [])
    hotspots: list[EntropyHotspot] = []
    for row in raw_hotspots:
        bbox = row["bbox"]
        if isinstance(bbox, dict):
            bbox = (bbox["left"], bbox["bottom"], bbox["right"], bbox["top"])
        hotspots.append(
            EntropyHotspot(
                hotspot_id=str(row["hotspot_id"]),
                region_slug=str(row["region_slug"]),
                bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                center_lon=float(row["center_lon"]),
                center_lat=float(row["center_lat"]),
                mean_entropy=float(row["mean_entropy"]),
                max_entropy=float(row["max_entropy"]),
                cell_count=int(row["cell_count"]),
                class_disagreement_summary={
                    str(k): float(v)
                    for k, v in row.get("class_disagreement_summary", {}).items()
                },
            )
        )
    return hotspots


def download_phase3_s2_batch(
    app_config: AppConfig,
    *,
    phase3_root: str | Path = "results/phase3/fine",
    results_root: str | Path = "results",
    target_time: str | pd.Timestamp = "2017-07-01",
    allow_interactive_auth: bool = False,
    skip_existing: bool = True,
) -> list[Phase3S2RunOutput]:
    """Discover probe manifests and download S2 reference for each hotspot."""
    manifests = discover_probe_manifests(phase3_root)
    gee_client = EarthEngineClient.from_config(app_config.gee)
    outputs: list[Phase3S2RunOutput] = []
    timestamp = pd.Timestamp(target_time)

    print(
        f"[s2-batch] discovered {len(manifests)} probe manifest(s) under {phase3_root}",
        flush=True,
    )

    run_progress = tqdm(manifests, desc="Phase3 S2 runs", unit="file", dynamic_ncols=True)
    for mf_path in run_progress:
        hotspots = load_hotspots_from_manifest(mf_path)
        run_progress.set_postfix_str(f"{mf_path.parent.name}", refresh=False)

        artifacts_payload: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        aoi_progress = tqdm(
            hotspots,
            desc=f"S2 {mf_path.parent.name}",
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

        artifact_path = mf_path.parent / "s2_artifacts.json"
        artifact_path.write_text(
            json.dumps(
                make_json_safe(
                    {
                        "probe_manifest_path": str(mf_path),
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
            manifest_path=mf_path,
            target_time=timestamp,
            artifact_manifest_path=artifact_path,
            hotspot_count=len(hotspots),
            status_counts=dict(status_counts),
        )
        outputs.append(output)
        print(
            f"[s2-batch] {mf_path.parent.name}: "
            f"{len(hotspots)} hotspot(s), status_counts={dict(status_counts)}",
            flush=True,
        )

    run_progress.close()
    return outputs
