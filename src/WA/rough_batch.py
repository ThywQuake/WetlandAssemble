from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import xarray as xr
import yaml

from WA.comparison import compute_rough_binary_metrics, create_comparison_grid, select_focus_areas
from WA.comparison.harmonize import BinaryAggregation
from WA.config import AppConfig, load_config
from WA.loader_probe import expand_dataset_ids, make_json_safe
from WA.rough_probe import (
    PreparedRoughDataset,
    RoughDatasetProbeResult,
    RoughProbeOptions,
    prepare_datasets,
    probe_prepared_dataset,
    summarize_disagreement,
    summarize_reference_grid,
)

DEFAULT_PHASE2_TARGET_TIMES = (
    pd.Timestamp("2000-03-01"),
    pd.Timestamp("2019-07-01"),
)
DEFAULT_PRIORITY_REGIONS_PATH = Path(
    "config/priority_regions.yaml"
)
DEFAULT_PRIORITY_REGION_DOCUMENT: dict[str, Any] = {
    "generated_at": "2026-03-19",
    "purpose": "Phase 2 rough-scale wetland comparison candidate basins and wetland regions",
    "bbox_convention": "[min_lon, min_lat, max_lon, max_lat] in EPSG:4326",
    "bbox_type": "working_analysis_bbox",
    "bbox_note": (
        "These are analysis windows curated from source-described extents and public map "
        "context; they are not official hydrological shapefile boundaries."
    ),
    "regions": {
        "amazon_basin": {
            "label": "Amazon Basin",
            "kind": "river_basin",
            "priority": 1,
            "continent": "South America",
            "bbox": [-79.5, -19.5, -44.0, 6.5],
            "rationale": (
                "Largest drainage basin in the world; the basin contains a complex mosaic "
                "of wetlands and forests and is the dominant tropical freshwater system in "
                "South America."
            ),
            "bbox_basis": (
                "Inferred working bbox from basin-wide extent described from the Andes of "
                "Peru to the Atlantic coast of Brazil, including the main lowland wetland belt."
            ),
            "source_urls": [
                "https://www.britannica.com/place/Amazon-Basin",
                "https://wwf.panda.org/discover/knowledge_hub/where_we_work/amazon/about_the_amazon",
            ],
        },
        "orinoco_basin_llanos": {
            "label": "Orinoco Basin and Llanos",
            "kind": "river_basin",
            "priority": 2,
            "continent": "South America",
            "bbox": [-73.5, 0.5, -58.0, 11.8],
            "rationale": (
                "One of South America's most intact large river systems, with flooded forests, "
                "vast grasslands, and a wide delta spanning Colombia and Venezuela."
            ),
            "bbox_basis": (
                "Inferred working bbox covering the Colombia-Venezuela Orinoco basin core, "
                "Llanos floodplains, and lower delta corridor."
            ),
            "source_urls": [
                "https://wwf.panda.org/discover/knowledge_hub/where_we_work/orinoco_river_basin/",
                "https://colombia.wcs.org/en-us/WHERE-WE-WORK/ORINOQUIA.aspx",
            ],
        },
        "pantanal_upper_paraguay": {
            "label": "Pantanal / Upper Paraguay Wetland",
            "kind": "wetland_system",
            "priority": 3,
            "continent": "South America",
            "bbox": [-61.5, -22.5, -54.0, -14.0],
            "rationale": (
                "World's largest tropical wetland; a seasonally flooded plain fed by the "
                "upper Paraguay system across Brazil, Bolivia, and Paraguay."
            ),
            "bbox_basis": (
                "Inferred working bbox covering the main Pantanal floodplain and upper Paraguay "
                "wetland core."
            ),
            "source_urls": [
                "https://www.worldwildlife.org/places/pantanal/",
                "https://www.nature.org/en-us/get-involved/how-to-help/places-we-protect/pantanal/",
            ],
        },
        "ngiri_tumba_maindombe": {
            "label": "Ngiri-Tumba-Maindombe / Cuvette Centrale Wetlands",
            "kind": "wetland_system",
            "priority": 4,
            "continent": "Africa",
            "bbox": [15.0, -3.5, 19.5, 1.5],
            "rationale": (
                "One of Africa's most important freshwater masses and one of the largest "
                "tropical wetland complexes in the Congo Basin."
            ),
            "bbox_basis": (
                "Inferred working bbox centered on the Ramsar wetland core east of the Congo "
                "River around Lake Tumba and the Ngiri-Maindombe system."
            ),
            "source_urls": [
                "https://www.ramsar.org/es/news/democratic-republic-congo-names-worlds-largest-ramsar-site",
                "https://rsis.ramsar.org/ris/1742",
            ],
        },
        "sudd": {
            "label": "Sudd Wetland",
            "kind": "wetland_system",
            "priority": 5,
            "continent": "Africa",
            "bbox": [28.5, 5.5, 33.5, 10.5],
            "rationale": (
                "One of the largest tropical freshwater wetlands in the world, formed along "
                "the lower Bahr el Jebel / White Nile system in South Sudan."
            ),
            "bbox_basis": (
                "Inferred working bbox spanning the core Sudd floodplain between Bor, Jonglei, "
                "and Malakal-side wetland sectors."
            ),
            "source_urls": [
                "https://whc.unesco.org/en/tentativelists/6276/",
                "https://rsis.ramsar.org/ris/1622",
            ],
        },
        "okavango_delta": {
            "label": "Okavango Delta",
            "kind": "wetland_system",
            "priority": 6,
            "continent": "Africa",
            "bbox": [20.0, -20.5, 24.5, -17.0],
            "rationale": (
                "One of the world's most intact inland deltas, with permanent marshlands and "
                "seasonally flooded plains in north-west Botswana."
            ),
            "bbox_basis": (
                "Inferred working bbox covering the UNESCO/Ramsar delta core and seasonally "
                "flooded fringe in north-west Botswana."
            ),
            "source_urls": [
                "https://rsis.ramsar.org/ris/879",
                "https://whc.unesco.org/en/list/1432/",
            ],
        },
        "mekong_delta": {
            "label": "Mekong Delta",
            "kind": "delta_wetland",
            "priority": 7,
            "continent": "Southeast Asia",
            "bbox": [104.2, 8.3, 106.9, 11.5],
            "rationale": (
                "One of the largest and most fertile deltas in Asia, with floodplains, wetlands, "
                "mangroves, mudflats, and peatlands."
            ),
            "bbox_basis": (
                "Inferred working bbox covering the Vietnamese Mekong Delta lowlands and coastal "
                "wetland belt."
            ),
            "source_urls": [
                "https://asiapacific.panda.org/priority_places/mekong_delta/",
                "https://wwf.panda.org/discover/our_focus/freshwater_practice/river_stories/",
            ],
        },
        "mekong_flooded_forest": {
            "label": "Mekong Flooded Forest",
            "kind": "river_floodplain",
            "priority": 8,
            "continent": "Southeast Asia",
            "bbox": [105.7, 12.0, 106.6, 14.3],
            "rationale": (
                "A globally important Lower Mekong freshwater landscape with wetlands, deep pools, "
                "sandy and rocky riverine habitats along the Cambodia-Laos corridor."
            ),
            "bbox_basis": (
                "Inferred working bbox covering the Kratie-Stung Treng flooded forest corridor "
                "and adjoining Laos border reach."
            ),
            "source_urls": [
                "https://asiapacific.panda.org/priority_places/mekong_flooded_forest/",
                "https://www.wwf.org.kh/about_us/where_we_work/mekong_flooded_forest/",
            ],
        },
        "danau_sentarum": {
            "label": "Danau Sentarum",
            "kind": "lake_floodplain_wetland",
            "priority": 9,
            "continent": "Insular Southeast Asia",
            "bbox": [111.95, 0.75, 112.3333, 1.0333],
            "rationale": (
                "A Ramsar wetland and one of the last major representatives of seasonal "
                "freshwater lakes, rivers, peat and swamp forest in Kalimantan."
            ),
            "bbox_basis": (
                "Directly taken from the official reported geographic extent of TN Danau "
                "Sentarum (0°45'–1°02'N, 111°57'–112°20'E)."
            ),
            "source_urls": [
                "https://ksdae.kehutanan.go.id/kawasan-konservasi/100244030/",
                "https://rsis.ramsar.org/ris/667",
            ],
        },
    },
}


@dataclass(frozen=True)
class PriorityRegion:
    region_id: str
    label: str
    kind: str
    priority: int
    continent: str
    bbox: tuple[float, float, float, float]
    rationale: str
    bbox_basis: str
    source_urls: tuple[str, ...]


@dataclass(frozen=True)
class RoughRegionRunOutput:
    region_id: str
    target_time: pd.Timestamp
    status: str
    output_dir: Path
    summary_path: Path
    metrics_path: Path | None
    comparison_grids_path: Path | None
    participant_surfaces_path: Path | None
    focus_areas_path: Path | None
    participant_dataset_ids: tuple[str, ...]


def load_priority_regions(
    path: str | Path = DEFAULT_PRIORITY_REGIONS_PATH,
) -> dict[str, PriorityRegion]:
    region_path = Path(path)
    if region_path.exists():
        document = yaml.safe_load(region_path.read_text(encoding="utf-8")) or {}
    elif region_path == DEFAULT_PRIORITY_REGIONS_PATH:
        document = DEFAULT_PRIORITY_REGION_DOCUMENT
    else:
        raise FileNotFoundError(f"Priority region file not found: {region_path}")
    if not isinstance(document, dict) or not isinstance(document.get("regions"), dict):
        raise ValueError("Priority region document must contain a top-level 'regions' mapping")

    loaded: dict[str, PriorityRegion] = {}
    for region_id, payload in document["regions"].items():
        if not isinstance(payload, dict):
            raise ValueError(f"Region {region_id!r} must be a mapping")
        bbox = payload.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"Region {region_id!r} must define bbox as 4-item list")
        loaded[str(region_id)] = PriorityRegion(
            region_id=str(region_id),
            label=str(payload["label"]),
            kind=str(payload["kind"]),
            priority=int(payload.get("priority", 999)),
            continent=str(payload.get("continent", "unknown")),
            bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
            rationale=str(payload.get("rationale", "")),
            bbox_basis=str(payload.get("bbox_basis", "")),
            source_urls=tuple(str(item) for item in payload.get("source_urls", [])),
        )
    return loaded


def resolve_region_ids(
    regions: Mapping[str, PriorityRegion],
    requested: Iterable[str] | None = None,
) -> list[str]:
    if not requested:
        return [
            region_id
            for region_id, _region in sorted(
                regions.items(), key=lambda item: (item[1].priority, item[0])
            )
        ]

    flattened: list[str] = []
    for entry in requested:
        flattened.extend(part.strip() for part in str(entry).split(",") if part.strip())

    unknown = sorted(set(flattened) - set(regions))
    if unknown:
        raise KeyError(f"Unknown region ids: {', '.join(unknown)}")
    return flattened


def build_phase2_options(
    *,
    bbox: tuple[float, float, float, float],
    target_time: pd.Timestamp,
    resolution_deg: float = 0.25,
    aggregation: BinaryAggregation = "mean",
    top_n: int = 8,
    top_n_per_region: int = 2,
    aoi_size_deg: float = 2.0,
    min_distance_deg: float = 3.0,
    preview_items: int = 5,
    results_root: str = "results/phase2/rough",
    gwd30_workers: int = 0,
    gwd30_surface_path: str | None = None,
) -> RoughProbeOptions:
    return RoughProbeOptions(
        bbox=bbox,
        bbox_label="priority_region_catalog",
        target_time=target_time,
        target_time_label="phase2_batch",
        resolution_deg=resolution_deg,
        aggregation=aggregation,
        top_n=top_n,
        top_n_per_region=top_n_per_region,
        aoi_size_deg=aoi_size_deg,
        min_distance_deg=min_distance_deg,
        preview_items=preview_items,
        download_modis=False,
        allow_interactive_auth=False,
        results_root=results_root,
        fail_fast=False,
        gwd30_workers=gwd30_workers,
        gwd30_surface_path=gwd30_surface_path,
    )


def run_rough_region_batch(
    app_config: AppConfig,
    *,
    regions_path: str | Path = DEFAULT_PRIORITY_REGIONS_PATH,
    region_ids: Iterable[str] | None = None,
    target_times: Iterable[str | pd.Timestamp] | None = None,
    dataset_ids: Iterable[str] | None = None,
    results_root: str | Path = "results/phase2/rough",
    resolution_deg: float = 0.25,
    aggregation: BinaryAggregation = "mean",
    top_n: int = 8,
    top_n_per_region: int = 2,
    aoi_size_deg: float = 2.0,
    min_distance_deg: float = 3.0,
    preview_items: int = 5,
    gwd30_workers: int = 0,
    gwd30_surface_root: str | Path | None = None,
) -> list[RoughRegionRunOutput]:
    regions = load_priority_regions(regions_path)
    selected_region_ids = resolve_region_ids(regions, region_ids)
    selected_dataset_ids = (
        list(dataset_ids) if dataset_ids else expand_dataset_ids(app_config, [])
    )
    prepared, preparation_failures = prepare_datasets(app_config, selected_dataset_ids)
    resolved_target_times = [
        pd.Timestamp(value) for value in (target_times or DEFAULT_PHASE2_TARGET_TIMES)
    ]

    root = Path(results_root)
    root.mkdir(parents=True, exist_ok=True)

    outputs: list[RoughRegionRunOutput] = []
    batch_manifest_entries: list[dict[str, Any]] = []

    for region_id in selected_region_ids:
        region = regions[region_id]
        for target_time in resolved_target_times:
            options = build_phase2_options(
                bbox=region.bbox,
                target_time=target_time,
                resolution_deg=resolution_deg,
                aggregation=aggregation,
                top_n=top_n,
                top_n_per_region=top_n_per_region,
                aoi_size_deg=aoi_size_deg,
                min_distance_deg=min_distance_deg,
                preview_items=preview_items,
                results_root=str(root),
                gwd30_workers=gwd30_workers,
                gwd30_surface_path=_resolve_gwd30_surface_path(
                    gwd30_surface_root,
                    region_id=region.region_id,
                    target_time=target_time,
                ),
            )
            run_output = _run_single_region_time(
                region=region,
                prepared=prepared,
                preparation_failures=preparation_failures,
                options=options,
                output_root=root,
            )
            outputs.append(run_output)
            batch_manifest_entries.append(
                {
                    "region_id": run_output.region_id,
                    "target_time": run_output.target_time.isoformat(),
                    "status": run_output.status,
                    "output_dir": str(run_output.output_dir),
                    "summary_path": str(run_output.summary_path),
                    "metrics_path": (
                        str(run_output.metrics_path) if run_output.metrics_path else None
                    ),
                    "comparison_grids_path": (
                        str(run_output.comparison_grids_path)
                        if run_output.comparison_grids_path
                        else None
                    ),
                    "participant_surfaces_path": (
                        str(run_output.participant_surfaces_path)
                        if run_output.participant_surfaces_path
                        else None
                    ),
                    "focus_areas_path": (
                        str(run_output.focus_areas_path) if run_output.focus_areas_path else None
                    ),
                    "participant_dataset_ids": list(run_output.participant_dataset_ids),
                }
            )

    manifest_path = root / "batch_manifest.json"
    manifest_payload = {
        "regions_path": str(Path(regions_path)),
        "dataset_ids": selected_dataset_ids,
        "target_times": [timestamp.isoformat() for timestamp in resolved_target_times],
        "runs": batch_manifest_entries,
    }
    manifest_path.write_text(
        json.dumps(make_json_safe(manifest_payload), indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    return outputs


def _run_single_region_time(
    *,
    region: PriorityRegion,
    prepared: list[PreparedRoughDataset],
    preparation_failures: list[RoughDatasetProbeResult],
    options: RoughProbeOptions,
    output_root: Path,
) -> RoughRegionRunOutput:
    reference_grid = create_comparison_grid(region.bbox, resolution_deg=options.resolution_deg)
    dataset_results = [asdict_failure_copy(result) for result in preparation_failures]
    participant_surfaces: dict[str, xr.DataArray] = {}

    for prepared_dataset in prepared:
        result, surface = probe_prepared_dataset(prepared_dataset, options, reference_grid)
        dataset_results.append(result)
        if surface is not None:
            participant_surfaces[prepared_dataset.dataset_id] = surface

    metrics_rows: list[dict[str, Any]] | None = None
    focus_areas_payload: list[dict[str, Any]] | None = None
    comparison_grids_path: Path | None = None
    participant_surfaces_path: Path | None = None
    metrics_path: Path | None = None
    focus_areas_path: Path | None = None
    gwd30_trace_path: Path | None = None
    gwd30_tiles_geojson_path: Path | None = None
    disagreement_summary: dict[str, Any] | None = None
    warnings: list[str] = []

    run_dir = output_root / region.region_id / f"{options.target_time:%Y%m}"
    run_dir.mkdir(parents=True, exist_ok=True)

    if len(participant_surfaces) >= 2:
        rough_result = compute_rough_binary_metrics(participant_surfaces)
        metrics_rows = rough_result.metrics.to_dict("records")
        disagreement_summary = summarize_disagreement(
            rough_result,
            preview_items=options.preview_items,
        )
        zero_overlap_rows = [row for row in metrics_rows if int(row["valid_cell_count"]) == 0]
        if zero_overlap_rows:
            warnings.append(
                f"{len(zero_overlap_rows)} pairwise metric rows have valid_cell_count=0"
            )

        metrics_path = run_dir / "pairwise_metrics.csv"
        rough_result.metrics.to_csv(metrics_path, index=False)

        comparison_grids_path = run_dir / "comparison_grids.nc"
        xr.Dataset(
            {
                "disagreement_score": rough_result.disagreement_score,
                "wetland_vote_fraction": rough_result.wetland_vote_fraction,
                "participant_count": rough_result.participant_count,
            },
            attrs={
                "region_id": region.region_id,
                "region_label": region.label,
                "target_time": options.target_time.isoformat(),
            },
        ).to_netcdf(comparison_grids_path)

        participant_surfaces_path = run_dir / "participant_surfaces.nc"
        xr.Dataset(
            {
                dataset_id: surface.astype("float32")
                for dataset_id, surface in participant_surfaces.items()
            },
            attrs={
                "region_id": region.region_id,
                "region_label": region.label,
                "target_time": options.target_time.isoformat(),
            },
        ).to_netcdf(participant_surfaces_path)

        focus_areas = select_focus_areas(
            rough_result.disagreement_score,
            rough_result.participant_count,
            target_time=options.target_time,
            wetland_vote_fraction=rough_result.wetland_vote_fraction,
            top_n=options.top_n,
            top_n_per_region=options.top_n_per_region,
            aoi_size_deg=options.aoi_size_deg,
            min_distance_deg=options.min_distance_deg,
        )
        focus_areas_payload = [asdict(area) for area in focus_areas]
        focus_areas_path = run_dir / "focus_areas.csv"
        pd.DataFrame(focus_areas_payload).to_csv(focus_areas_path, index=False)

    status = _overall_status(dataset_results, participant_surfaces)
    gwd30_trace = _extract_gwd30_trace(dataset_results)
    if gwd30_trace is not None:
        gwd30_trace_path = run_dir / "gwd30_load_trace.json"
        gwd30_trace_path.write_text(
            json.dumps(make_json_safe(gwd30_trace), indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        gwd30_tiles_geojson_path = run_dir / "gwd30_selected_tiles.geojson"
        geojson_payload = _gwd30_trace_to_geojson(
            region.region_id,
            options.target_time,
            gwd30_trace,
        )
        gwd30_tiles_geojson_path.write_text(
            json.dumps(
                make_json_safe(geojson_payload),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
    summary_path = run_dir / "run_summary.json"
    summary_payload = {
        "region": asdict(region),
        "target_time": options.target_time,
        "status": status,
        "reference_grid_summary": summarize_reference_grid(reference_grid),
        "participant_dataset_ids": sorted(participant_surfaces),
        "dataset_results": [asdict(result) for result in dataset_results],
        "metrics_row_count": len(metrics_rows or []),
        "disagreement_summary": disagreement_summary,
        "focus_area_count": len(focus_areas_payload or []),
        "warnings": warnings,
        "output_files": {
            "metrics_path": metrics_path,
            "comparison_grids_path": comparison_grids_path,
            "participant_surfaces_path": participant_surfaces_path,
            "focus_areas_path": focus_areas_path,
            "gwd30_trace_path": gwd30_trace_path,
            "gwd30_tiles_geojson_path": gwd30_tiles_geojson_path,
        },
    }
    summary_path.write_text(
        json.dumps(make_json_safe(summary_payload), indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    return RoughRegionRunOutput(
        region_id=region.region_id,
        target_time=options.target_time,
        status=status,
        output_dir=run_dir,
        summary_path=summary_path,
        metrics_path=metrics_path,
        comparison_grids_path=comparison_grids_path,
        participant_surfaces_path=participant_surfaces_path,
        focus_areas_path=focus_areas_path,
        participant_dataset_ids=tuple(sorted(participant_surfaces)),
    )


def asdict_failure_copy(result: RoughDatasetProbeResult) -> RoughDatasetProbeResult:
    return RoughDatasetProbeResult(**asdict(result))


def _overall_status(
    dataset_results: list[RoughDatasetProbeResult],
    participant_surfaces: Mapping[str, xr.DataArray],
) -> str:
    failed_count = sum(result.status.startswith("failed") for result in dataset_results)
    skipped_count = sum(result.status.startswith("skipped") for result in dataset_results)
    if len(participant_surfaces) >= 2:
        if failed_count > 0:
            return "completed_with_failures"
        if skipped_count > 0:
            return "completed_with_skips"
        return "completed"
    if failed_count > 0:
        return "failed"
    return "insufficient_participants"


def _extract_gwd30_trace(
    dataset_results: list[RoughDatasetProbeResult],
) -> dict[str, Any] | None:
    for result in dataset_results:
        if result.dataset_id != "gwd30" or result.dataset_summary is None:
            continue
        load_trace = result.dataset_summary.get("load_trace")
        if isinstance(load_trace, dict):
            return load_trace
    return None


def _resolve_gwd30_surface_path(
    gwd30_surface_root: str | Path | None,
    *,
    region_id: str,
    target_time: pd.Timestamp,
) -> str | None:
    if gwd30_surface_root is None:
        return None
    candidate = Path(gwd30_surface_root) / region_id / f"{target_time:%Y%m}" / "gwd30_surface.nc"
    if not candidate.exists():
        raise FileNotFoundError(f"Expected precomputed GWD30 surface at {candidate}")
    return str(candidate)


def _gwd30_trace_to_geojson(
    region_id: str,
    target_time: pd.Timestamp,
    trace: Mapping[str, Any],
) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    for year_entry in trace.get("years", []):
        if not isinstance(year_entry, dict):
            continue
        year = year_entry.get("year")
        band_count = len(year_entry.get("selected_band_indexes", []))
        for tile_entry in year_entry.get("selected_tiles", []):
            if not isinstance(tile_entry, dict):
                continue
            tile_bbox = tile_entry.get("tile_bbox")
            if not isinstance(tile_bbox, list) or len(tile_bbox) != 4:
                continue
            west, south, east, north = [float(value) for value in tile_bbox]
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "region_id": region_id,
                        "target_time": target_time.isoformat(),
                        "year": year,
                        "tile_code": tile_entry.get("tile_code"),
                        "path": tile_entry.get("path"),
                        "selected_band_count": band_count,
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [west, south],
                                [east, south],
                                [east, north],
                                [west, north],
                                [west, south],
                            ]
                        ],
                    },
                }
            )
    return {"type": "FeatureCollection", "features": features}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Phase 2 rough-comparison data files for priority tropical regions."
    )
    parser.add_argument("--regions-file", default=str(DEFAULT_PRIORITY_REGIONS_PATH))
    parser.add_argument("--region", action="append", default=[])
    parser.add_argument("--target-time", action="append", default=[])
    parser.add_argument("--dataset", action="append", default=[])
    parser.add_argument("--results-root", default="results/phase2/rough")
    parser.add_argument("--resolution-deg", type=float, default=0.25)
    parser.add_argument("--aggregation", choices=("mean", "max"), default="mean")
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument("--top-n-per-region", type=int, default=2)
    parser.add_argument("--aoi-size-deg", type=float, default=2.0)
    parser.add_argument("--min-distance-deg", type=float, default=3.0)
    parser.add_argument("--preview-items", type=int, default=5)
    parser.add_argument("--gwd30-workers", type=int, default=0)
    parser.add_argument("--gwd30-surface-root")
    parser.add_argument("--dataset-config", default="config/datasets.yaml")
    parser.add_argument("--gee-config", default="config/gee_config.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    app_config = load_config(args.dataset_config, args.gee_config)
    run_rough_region_batch(
        app_config,
        regions_path=args.regions_file,
        region_ids=args.region,
        target_times=args.target_time,
        dataset_ids=args.dataset,
        results_root=args.results_root,
        resolution_deg=args.resolution_deg,
        aggregation=args.aggregation,
        top_n=args.top_n,
        top_n_per_region=args.top_n_per_region,
        aoi_size_deg=args.aoi_size_deg,
        min_distance_deg=args.min_distance_deg,
        preview_items=args.preview_items,
        gwd30_workers=args.gwd30_workers,
        gwd30_surface_root=args.gwd30_surface_root,
    )
    return 0
