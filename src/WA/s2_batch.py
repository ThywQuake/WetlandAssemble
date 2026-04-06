"""Batch Sentinel-2 reference downloads driven by fine-grained probe JSON manifests."""

from __future__ import annotations

import json
import re
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


DEFAULT_PHASE37_HOTSPOTS_MANIFEST = Path("results/phase3.7_hotspots/phase3_7_hotspots_2016.json")
DEFAULT_PHASE37_S2_RESULTS_ROOT = Path("results/phase3.7_s2")
DEFAULT_PHASE37_S2_TARGET_TIME = pd.Timestamp("2016-07-01")


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
                source=str(row.get("source", "entropy")),
            )
        )
    return hotspots


def default_s2_artifact_manifest_path(
    manifest_path: str | Path,
    *,
    target_time: str | pd.Timestamp,
) -> Path:
    """Return the legacy artifact manifest path for one hotspot manifest."""

    _ = pd.Timestamp(target_time)
    return Path(manifest_path).parent / "s2_artifacts.json"


def default_phase37_s2_artifact_manifest_path(
    hotspots_manifest_path: str | Path,
    *,
    target_time: str | pd.Timestamp,
) -> Path:
    """Return the Phase 3.7 artifact manifest path for one hotspot manifest."""

    manifest_path = Path(hotspots_manifest_path)
    timestamp = pd.Timestamp(target_time)
    match = re.fullmatch(r"phase3_7_hotspots_(\d{4})", manifest_path.stem)
    year_slug = match.group(1) if match else f"{timestamp:%Y}"
    return manifest_path.parent / f"phase3_7_s2_artifacts_{year_slug}_{timestamp:%Y%m%d}.json"


def download_s2_for_manifests(
    app_config: AppConfig,
    *,
    manifest_paths: list[str | Path],
    results_root: str | Path,
    target_time: str | pd.Timestamp,
    allow_interactive_auth: bool = False,
    skip_existing: bool = True,
    artifact_manifest_path_fn=default_s2_artifact_manifest_path,
) -> list[Phase3S2RunOutput]:
    """Download Sentinel-2 artifacts for one or more explicit hotspot manifests."""

    resolved_manifests = [Path(path) for path in manifest_paths]
    gee_client = EarthEngineClient.from_config(app_config.gee)
    outputs: list[Phase3S2RunOutput] = []
    timestamp = pd.Timestamp(target_time)

    print(
        f"[s2-batch] processing {len(resolved_manifests)} hotspot manifest(s)",
        flush=True,
    )

    run_progress = tqdm(
        resolved_manifests,
        desc="Phase3 S2 runs",
        unit="file",
        dynamic_ncols=True,
    )
    for manifest_path in run_progress:
        hotspots = load_hotspots_from_manifest(manifest_path)
        run_progress.set_postfix_str(manifest_path.name, refresh=False)

        artifacts_payload: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        aoi_progress = tqdm(
            hotspots,
            desc=f"S2 {manifest_path.stem}",
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
                f"{hotspot.region_slug}:{artifact.status}",
                refresh=False,
            )
        aoi_progress.close()

        artifact_manifest_path = artifact_manifest_path_fn(
            manifest_path,
            target_time=timestamp,
        )
        manifest_payload: dict[str, Any] = {
            "hotspots_manifest_path": str(manifest_path),
            "target_time": timestamp,
            "results_root": Path(results_root),
            "hotspot_count": len(hotspots),
            "status_counts": dict(status_counts),
            "artifacts": artifacts_payload,
        }
        if manifest_path.name == "fine_grained_probe.json":
            manifest_payload["probe_manifest_path"] = str(manifest_path)
        artifact_manifest_path.write_text(
            json.dumps(
                make_json_safe(manifest_payload),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            ),
            encoding="utf-8",
        )

        output = Phase3S2RunOutput(
            manifest_path=manifest_path,
            target_time=timestamp,
            artifact_manifest_path=artifact_manifest_path,
            hotspot_count=len(hotspots),
            status_counts=dict(status_counts),
        )
        outputs.append(output)
        print(
            f"[s2-batch] {manifest_path.name}: "
            f"{len(hotspots)} hotspot(s), status_counts={dict(status_counts)}",
            flush=True,
        )

    run_progress.close()
    return outputs


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
    print(
        f"[s2-batch] discovered {len(manifests)} probe manifest(s) under {phase3_root}",
        flush=True,
    )
    return download_s2_for_manifests(
        app_config,
        manifest_paths=manifests,
        results_root=results_root,
        target_time=target_time,
        allow_interactive_auth=allow_interactive_auth,
        skip_existing=skip_existing,
        artifact_manifest_path_fn=default_s2_artifact_manifest_path,
    )


def download_phase37_s2_batch(
    app_config: AppConfig,
    *,
    hotspots_manifest: str | Path = DEFAULT_PHASE37_HOTSPOTS_MANIFEST,
    results_root: str | Path = DEFAULT_PHASE37_S2_RESULTS_ROOT,
    target_time: str | pd.Timestamp = DEFAULT_PHASE37_S2_TARGET_TIME,
    allow_interactive_auth: bool = False,
    skip_existing: bool = True,
) -> Phase3S2RunOutput:
    """Download Sentinel-2 artifacts for one Phase 3.7 hotspot manifest."""

    outputs = download_s2_for_manifests(
        app_config,
        manifest_paths=[hotspots_manifest],
        results_root=results_root,
        target_time=target_time,
        allow_interactive_auth=allow_interactive_auth,
        skip_existing=skip_existing,
        artifact_manifest_path_fn=default_phase37_s2_artifact_manifest_path,
    )
    return outputs[0]
