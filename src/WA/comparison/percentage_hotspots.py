"""Contract-backed percentage hotspot manifests and CSV companions."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr
from scipy.ndimage import maximum_filter

from WA.comparison.evidence_contract import (
    EvidenceContract,
    metadata_json,
    validate_stem_token,
)
from WA.comparison.percentage_backbone import (
    PercentageSummaryBundle,
    PercentageSurfaceBundle,
    load_contract_percentage_summary,
    load_contract_percentage_surface,
)
from WA.loaders.base import BBox

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0088
PERCENTAGE_HOTSPOT_MANIFEST_VERSION = 1
PERCENTAGE_HOTSPOT_RANKING = (
    "wetland_percentage desc",
    "wetland_area_km2 desc",
    "center_lat desc",
    "center_lon asc",
)
PERCENTAGE_HOTSPOT_TABLE_COLUMNS = (
    "hotspot_id",
    "hotspot_rank",
    "region_id",
    "dataset_key",
    "dataset_ids_json",
    "center_lat",
    "center_lon",
    "bbox",
    "wetland_percentage",
    "wetland_area_km2",
    "valid_area_km2",
    "valid_dataset_count",
    "std_wetland_percentage",
)


@dataclass(frozen=True)
class PercentageHotspotManifest:
    """Validated metadata for one percentage hotspot JSON/CSV pair."""

    manifest_path: Path
    table_path: Path
    region_id: str
    dataset_key: str
    dataset_ids: tuple[str, ...]
    hotspot_count: int
    surface_output_path: Path
    summary_output_path: Path
    contract_metadata_json: str
    contract_metadata: dict[str, Any]
    table_sha256: str
    manifest_relpath: str
    table_relpath: str
    surface_output_relpath: str | None
    summary_output_relpath: str | None


@dataclass(frozen=True)
class PercentageHotspotReload:
    """Reloaded manifest plus validated hotspot table."""

    manifest: PercentageHotspotManifest
    table: pd.DataFrame


def percentage_hotspot_manifest_relpath(
    contract: EvidenceContract,
    *,
    region_id: str,
    dataset_key: str,
) -> Path:
    normalized_key = validate_stem_token(dataset_key, label="dataset_key")
    return contract.artifact_relpath(
        kind="hotspot_manifest",
        dataset_or_key=normalized_key,
        region_id=region_id,
    )


def percentage_hotspot_manifest_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    dataset_key: str,
) -> Path:
    return contract.output_root / percentage_hotspot_manifest_relpath(
        contract,
        region_id=region_id,
        dataset_key=dataset_key,
    )


def percentage_hotspot_table_relpath(
    contract: EvidenceContract,
    *,
    region_id: str,
    dataset_key: str,
) -> Path:
    return percentage_hotspot_manifest_relpath(
        contract,
        region_id=region_id,
        dataset_key=dataset_key,
    ).with_suffix(".csv")


def percentage_hotspot_table_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    dataset_key: str,
) -> Path:
    return contract.output_root / percentage_hotspot_table_relpath(
        contract,
        region_id=region_id,
        dataset_key=dataset_key,
    )


def build_percentage_hotspot_table(
    surface_bundle: PercentageSurfaceBundle,
    *,
    top_n: int = 10,
    min_distance_deg: float = 0.5,
) -> pd.DataFrame:
    """Rank local-max coarse cells as percentage hotspots."""

    if top_n <= 0:
        raise ValueError("top_n must be positive")
    if min_distance_deg < 0:
        raise ValueError("min_distance_deg must be non-negative")

    mean_surface = surface_bundle.dataset["mean_wetland_percentage"]
    std_surface = surface_bundle.dataset["std_wetland_percentage"]
    count_surface = surface_bundle.dataset["valid_dataset_count"]
    y_dim, x_dim = _spatial_dims(mean_surface)
    lat_values = np.asarray(mean_surface.coords[y_dim].values, dtype=np.float64)
    lon_values = np.asarray(mean_surface.coords[x_dim].values, dtype=np.float64)
    lat_edges = _coordinate_edges(lat_values)
    lon_edges = _coordinate_edges(lon_values)

    mean_values = np.asarray(mean_surface.values, dtype=np.float64)
    std_values = np.asarray(std_surface.values, dtype=np.float64)
    count_values = np.asarray(count_surface.values, dtype=np.int32)
    valid_mask = np.isfinite(mean_values) & np.isfinite(std_values) & (count_values > 0)
    if not np.any(valid_mask):
        raise ValueError("No valid percentage hotspot candidates were found")

    local_max = maximum_filter(
        np.where(valid_mask, mean_values, -np.inf),
        size=3,
        mode="nearest",
    )
    candidate_mask = valid_mask & np.isclose(mean_values, local_max, equal_nan=False)
    if not np.any(candidate_mask):
        raise ValueError("No local-max percentage hotspot candidates were found")

    dataset_ids_json = json.dumps(list(surface_bundle.dataset_ids), separators=(",", ":"))
    candidates: list[dict[str, object]] = []
    rows, cols = np.where(candidate_mask)
    for row_index, col_index in zip(rows.tolist(), cols.tolist(), strict=True):
        bbox = _bbox_for_cell(
            lat_index=row_index,
            lon_index=col_index,
            lat_edges=lat_edges,
            lon_edges=lon_edges,
        )
        valid_area_km2 = _cell_area_km2(
            lat_index=row_index,
            lon_index=col_index,
            lat_edges=lat_edges,
            lon_edges=lon_edges,
        )
        wetland_percentage = float(mean_values[row_index, col_index])
        candidates.append(
            {
                "region_id": surface_bundle.region_id,
                "dataset_key": surface_bundle.dataset_key,
                "dataset_ids_json": dataset_ids_json,
                "center_lat": float(lat_values[row_index]),
                "center_lon": float(lon_values[col_index]),
                "bbox": bbox,
                "wetland_percentage": wetland_percentage,
                "wetland_area_km2": float(valid_area_km2 * wetland_percentage / 100.0),
                "valid_area_km2": float(valid_area_km2),
                "valid_dataset_count": int(count_values[row_index, col_index]),
                "std_wetland_percentage": float(std_values[row_index, col_index]),
            }
        )

    if not candidates:
        raise ValueError("No percentage hotspot candidates remained after candidate extraction")

    ordered = sorted(
        candidates,
        key=lambda item: (
            -float(item["wetland_percentage"]),
            -float(item["wetland_area_km2"]),
            -float(item["center_lat"]),
            float(item["center_lon"]),
        ),
    )
    selected: list[dict[str, object]] = []
    for candidate in ordered:
        if len(selected) >= top_n:
            break
        if any(_center_distance(candidate, current) < min_distance_deg for current in selected):
            continue
        selected.append(candidate)

    if not selected:
        raise ValueError("No percentage hotspot candidates remained after distance filtering")

    table = pd.DataFrame(selected)
    table.insert(
        0,
        "hotspot_id",
        [
            f"pct-{surface_bundle.region_id}-{surface_bundle.dataset_key}-{rank:03d}"
            for rank in range(1, len(table) + 1)
        ],
    )
    table.insert(1, "hotspot_rank", list(range(1, len(table) + 1)))
    return table.loc[:, list(PERCENTAGE_HOTSPOT_TABLE_COLUMNS)]


def write_percentage_hotspot_outputs(
    *,
    contract: EvidenceContract,
    region_id: str,
    dataset_key: str,
    top_n: int = 10,
    min_distance_deg: float = 0.5,
) -> PercentageHotspotManifest:
    """Write one validated percentage hotspot JSON/CSV pair."""

    normalized_key = validate_stem_token(dataset_key, label="dataset_key")
    surface_bundle = load_contract_percentage_surface(
        contract=contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    summary_bundle = load_contract_percentage_summary(
        contract=contract,
        region_id=region_id,
        dataset_key=normalized_key,
        expected_dataset_ids=surface_bundle.dataset_ids,
    )
    _require_matching_inputs(surface_bundle, summary_bundle)

    table = build_percentage_hotspot_table(
        surface_bundle,
        top_n=top_n,
        min_distance_deg=min_distance_deg,
    )
    manifest_path = percentage_hotspot_manifest_output_path(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    table_path = percentage_hotspot_table_output_path(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    table_serializable = table.copy()
    table_serializable["bbox"] = table_serializable["bbox"].map(_format_bbox_for_csv)
    table_text = table_serializable.to_csv(index=False, lineterminator="\n")
    table_sha256 = hashlib.sha256(table_text.encode("utf-8")).hexdigest()

    manifest_relpath = percentage_hotspot_manifest_relpath(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    table_relpath = percentage_hotspot_table_relpath(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    surface_relpath = _relative_to_root(surface_bundle.surface_path, contract.output_root)
    summary_relpath = _relative_to_root(summary_bundle.summary_path, contract.output_root)
    contract_metadata = {
        "artifact_kind": "hotspot_manifest",
        "dataset_key": normalized_key,
        "dataset_ids": list(surface_bundle.dataset_ids),
        "region_id": region_id,
        "region_label": surface_bundle.region_label,
        "surface_output_path": str(surface_bundle.surface_path),
        "summary_output_path": str(summary_bundle.summary_path),
        "surface_output_relpath": surface_relpath,
        "summary_output_relpath": summary_relpath,
        "surface_year": surface_bundle.target_year,
        "resolution_deg": surface_bundle.resolution_deg,
        "summary_time_range": list(summary_bundle.time_range),
        "ranking": list(PERCENTAGE_HOTSPOT_RANKING),
        "min_distance_deg": float(min_distance_deg),
        "table_sha256": table_sha256,
    }
    manifest_payload = {
        "artifact_kind": "hotspot_manifest",
        "manifest_version": PERCENTAGE_HOTSPOT_MANIFEST_VERSION,
        "region_id": region_id,
        "dataset_key": normalized_key,
        "dataset_ids": list(surface_bundle.dataset_ids),
        "hotspot_count": int(len(table)),
        "manifest_output_path": str(manifest_path.resolve()),
        "manifest_relpath": str(manifest_relpath),
        "table_output_path": str(table_path.resolve()),
        "table_relpath": str(table_relpath),
        "surface_output_path": str(surface_bundle.surface_path),
        "surface_output_relpath": surface_relpath,
        "summary_output_path": str(summary_bundle.summary_path),
        "summary_output_relpath": summary_relpath,
        "table_columns": list(PERCENTAGE_HOTSPOT_TABLE_COLUMNS),
        "table_sha256": table_sha256,
        "contract_metadata_json": metadata_json(contract_metadata),
    }
    manifest_text = json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n"

    _write_text_atomic(table_path, table_text)
    _write_text_atomic(manifest_path, manifest_text)
    logger.info(
        "stage=percentage-hotspots region=%s action=write-complete dataset_key=%s "
        "hotspots=%s manifest=%s table=%s",
        region_id,
        normalized_key,
        len(table),
        manifest_path,
        table_path,
    )
    return load_percentage_hotspot_manifest(manifest_path)


def load_percentage_hotspot_manifest(path: str | Path) -> PercentageHotspotManifest:
    """Load and validate one percentage hotspot manifest JSON file."""

    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Percentage hotspot manifest must be a JSON object: {manifest_path}")
    if payload.get("artifact_kind") != "hotspot_manifest":
        raise ValueError(
            f"Expected artifact_kind='hotspot_manifest', got {payload.get('artifact_kind')!r}"
        )

    dataset_key = validate_stem_token(str(payload.get("dataset_key", "")), label="dataset_key")
    region_id = validate_stem_token(str(payload.get("region_id", "")), label="region_id")
    dataset_ids_raw = payload.get("dataset_ids")
    if not isinstance(dataset_ids_raw, list) or not dataset_ids_raw:
        raise ValueError("Percentage hotspot manifest must contain a non-empty dataset_ids list")
    dataset_ids = tuple(
        validate_stem_token(str(dataset_id), label="dataset_id") for dataset_id in dataset_ids_raw
    )
    hotspot_count = int(payload.get("hotspot_count", 0))
    if hotspot_count <= 0:
        raise ValueError("Percentage hotspot manifest hotspot_count must be positive")

    table_sha256 = str(payload.get("table_sha256", "")).strip()
    if len(table_sha256) != 64:
        raise ValueError("Percentage hotspot manifest table_sha256 must be a SHA-256 hex digest")

    manifest_output_path = Path(str(payload.get("manifest_output_path", manifest_path)))
    if manifest_output_path.resolve() != manifest_path.resolve():
        raise ValueError("Percentage hotspot manifest_output_path does not match the loaded path")

    table_path = Path(str(payload.get("table_output_path", "")))
    surface_output_path = Path(str(payload.get("surface_output_path", "")))
    summary_output_path = Path(str(payload.get("summary_output_path", "")))
    for label, candidate in (
        ("table_output_path", table_path),
        ("surface_output_path", surface_output_path),
        ("summary_output_path", summary_output_path),
    ):
        if not str(candidate).strip():
            raise ValueError(f"Percentage hotspot manifest is missing {label}")
        if not candidate.is_file():
            raise FileNotFoundError(
                f"Percentage hotspot manifest references missing {label}: {candidate}"
            )

    contract_metadata_json = str(payload.get("contract_metadata_json", "")).strip()
    if not contract_metadata_json:
        raise ValueError("Percentage hotspot manifest is missing contract_metadata_json")
    try:
        contract_metadata = json.loads(contract_metadata_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Malformed contract_metadata_json in percentage hotspot manifest") from exc
    if not isinstance(contract_metadata, dict):
        raise ValueError(
            "Percentage hotspot manifest contract_metadata_json must decode to an object"
        )

    manifest_relpath = str(payload.get("manifest_relpath", "")).strip()
    table_relpath = str(payload.get("table_relpath", "")).strip()
    if not manifest_relpath or not table_relpath:
        raise ValueError(
            "Percentage hotspot manifest must contain manifest_relpath and table_relpath"
        )

    return PercentageHotspotManifest(
        manifest_path=manifest_path.resolve(),
        table_path=table_path.resolve(),
        region_id=region_id,
        dataset_key=dataset_key,
        dataset_ids=dataset_ids,
        hotspot_count=hotspot_count,
        surface_output_path=surface_output_path.resolve(),
        summary_output_path=summary_output_path.resolve(),
        contract_metadata_json=contract_metadata_json,
        contract_metadata=contract_metadata,
        table_sha256=table_sha256,
        manifest_relpath=manifest_relpath,
        table_relpath=table_relpath,
        surface_output_relpath=_optional_string(payload.get("surface_output_relpath")),
        summary_output_relpath=_optional_string(payload.get("summary_output_relpath")),
    )


def load_contract_percentage_hotspot_table(
    *,
    contract: EvidenceContract,
    region_id: str,
    dataset_key: str,
    expected_dataset_ids: Iterable[str] | None = None,
) -> PercentageHotspotReload:
    """Load one percentage hotspot JSON/CSV pair by contract semantics."""

    normalized_key = validate_stem_token(dataset_key, label="dataset_key")
    surface_bundle = load_contract_percentage_surface(
        contract=contract,
        region_id=region_id,
        dataset_key=normalized_key,
        expected_dataset_ids=expected_dataset_ids,
    )
    summary_bundle = load_contract_percentage_summary(
        contract=contract,
        region_id=region_id,
        dataset_key=normalized_key,
        expected_dataset_ids=surface_bundle.dataset_ids,
    )
    manifest_path = percentage_hotspot_manifest_output_path(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    expected_table_path = percentage_hotspot_table_output_path(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    ).resolve()
    manifest = load_percentage_hotspot_manifest(manifest_path)
    if manifest.region_id != region_id:
        raise ValueError(
            "Percentage hotspot manifest region mismatch: "
            f"expected {region_id!r}, got {manifest.region_id!r}"
        )
    if manifest.dataset_key != normalized_key:
        raise ValueError("Percentage hotspot manifest dataset_key does not match the request")
    if manifest.dataset_ids != surface_bundle.dataset_ids:
        raise ValueError("Percentage hotspot manifest dataset_ids do not match the surface bundle")
    if manifest.dataset_ids != summary_bundle.dataset_ids:
        raise ValueError("Percentage hotspot manifest dataset_ids do not match the summary bundle")
    if manifest.table_path != expected_table_path:
        raise ValueError(
            "Percentage hotspot manifest table_output_path does not match contract semantics"
        )
    if manifest.surface_output_path != surface_bundle.surface_path:
        raise ValueError(
            "Percentage hotspot manifest surface_output_path does not match contract semantics"
        )
    if manifest.summary_output_path != summary_bundle.summary_path:
        raise ValueError(
            "Percentage hotspot manifest summary_output_path does not match contract semantics"
        )

    table_text = manifest.table_path.read_text(encoding="utf-8")
    table_sha256 = hashlib.sha256(table_text.encode("utf-8")).hexdigest()
    if table_sha256 != manifest.table_sha256:
        raise ValueError(
            "Percentage hotspot table SHA mismatch; refusing to reuse "
            "a partial or stale JSON/CSV pair"
        )

    table = pd.read_csv(manifest.table_path)
    _validate_percentage_hotspot_table(
        table,
        manifest=manifest,
        expected_region_id=region_id,
        expected_dataset_key=normalized_key,
        expected_dataset_ids=surface_bundle.dataset_ids,
    )
    table = table.copy()
    table["bbox"] = table["bbox"].map(_parse_bbox_literal)
    table["dataset_ids"] = table["dataset_ids_json"].map(_parse_dataset_ids_json)
    logger.info(
        "stage=percentage-hotspots region=%s action=reload-ready dataset_key=%s hotspots=%s",
        region_id,
        normalized_key,
        len(table),
    )
    return PercentageHotspotReload(manifest=manifest, table=table)


def _require_matching_inputs(
    surface_bundle: PercentageSurfaceBundle,
    summary_bundle: PercentageSummaryBundle,
) -> None:
    if surface_bundle.region_id != summary_bundle.region_id:
        raise ValueError("Percentage surface and summary region_id values do not match")
    if surface_bundle.dataset_key != summary_bundle.dataset_key:
        raise ValueError("Percentage surface and summary dataset_key values do not match")
    if surface_bundle.dataset_ids != summary_bundle.dataset_ids:
        raise ValueError("Percentage surface and summary dataset_ids do not match")


def _spatial_dims(data: xr.DataArray) -> tuple[str, str]:
    if "lat" in data.dims and "lon" in data.dims:
        return ("lat", "lon")
    if "y" in data.dims and "x" in data.dims:
        return ("y", "x")
    raise ValueError(f"Expected spatial dims lat/lon or y/x, got {data.dims!r}")


def _coordinate_edges(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        raise ValueError("Cannot derive hotspot cell bounds from an empty coordinate axis")
    if values.size == 1:
        center = float(values[0])
        return np.array([center - 0.5, center + 0.5], dtype=np.float64)

    mids = (values[:-1] + values[1:]) / 2.0
    edges = np.empty(values.size + 1, dtype=np.float64)
    edges[1:-1] = mids
    edges[0] = values[0] - (mids[0] - values[0])
    edges[-1] = values[-1] + (values[-1] - mids[-1])
    return edges


def _bbox_for_cell(
    *,
    lat_index: int,
    lon_index: int,
    lat_edges: np.ndarray,
    lon_edges: np.ndarray,
) -> BBox:
    south = float(min(lat_edges[lat_index], lat_edges[lat_index + 1]))
    north = float(max(lat_edges[lat_index], lat_edges[lat_index + 1]))
    west = float(min(lon_edges[lon_index], lon_edges[lon_index + 1]))
    east = float(max(lon_edges[lon_index], lon_edges[lon_index + 1]))
    return (west, south, east, north)


def _cell_area_km2(
    *,
    lat_index: int,
    lon_index: int,
    lat_edges: np.ndarray,
    lon_edges: np.ndarray,
) -> float:
    south = math.radians(min(lat_edges[lat_index], lat_edges[lat_index + 1]))
    north = math.radians(max(lat_edges[lat_index], lat_edges[lat_index + 1]))
    west = math.radians(min(lon_edges[lon_index], lon_edges[lon_index + 1]))
    east = math.radians(max(lon_edges[lon_index], lon_edges[lon_index + 1]))
    return float((EARTH_RADIUS_KM**2) * (east - west) * (math.sin(north) - math.sin(south)))


def _center_distance(left: dict[str, object], right: dict[str, object]) -> float:
    return math.hypot(
        float(left["center_lon"]) - float(right["center_lon"]),
        float(left["center_lat"]) - float(right["center_lat"]),
    )


def _format_bbox_for_csv(bbox: BBox) -> str:
    return json.dumps([float(value) for value in bbox], separators=(",", ":"))


def _parse_bbox_literal(value: object) -> BBox:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid hotspot bbox JSON: {value!r}") from exc
    if not isinstance(parsed, list) or len(parsed) != 4:
        raise ValueError(f"Hotspot bbox must be a 4-item JSON list, got {value!r}")
    bbox = tuple(float(item) for item in parsed)
    if not all(math.isfinite(item) for item in bbox):
        raise ValueError(f"Hotspot bbox must contain finite values, got {value!r}")
    west, south, east, north = bbox
    if west >= east or south >= north:
        raise ValueError(f"Hotspot bbox bounds are invalid: {value!r}")
    return bbox  # type: ignore[return-value]


def _parse_dataset_ids_json(value: object) -> tuple[str, ...]:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid dataset_ids_json: {value!r}") from exc
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("dataset_ids_json must decode to a non-empty list")
    normalized = tuple(
        validate_stem_token(str(dataset_id), label="dataset_id") for dataset_id in parsed
    )
    if len(set(normalized)) != len(normalized):
        raise ValueError("dataset_ids_json must not contain duplicates")
    return normalized


def _validate_percentage_hotspot_table(
    table: pd.DataFrame,
    *,
    manifest: PercentageHotspotManifest,
    expected_region_id: str,
    expected_dataset_key: str,
    expected_dataset_ids: tuple[str, ...],
) -> None:
    missing_columns = [
        column for column in PERCENTAGE_HOTSPOT_TABLE_COLUMNS if column not in table.columns
    ]
    if missing_columns:
        raise ValueError(
            "Percentage hotspot table is missing required columns: " + ", ".join(missing_columns)
        )
    if len(table) != manifest.hotspot_count:
        raise ValueError(
            "Percentage hotspot table row count "
            f"{len(table)} does not match manifest.hotspot_count {manifest.hotspot_count}"
        )

    expected_ranks = list(range(1, len(table) + 1))
    if table["hotspot_rank"].astype(int).tolist() != expected_ranks:
        raise ValueError("Percentage hotspot table hotspot_rank must be sequential starting at 1")

    hotspot_ids = [str(value).strip() for value in table["hotspot_id"]]
    if any(not hotspot_id for hotspot_id in hotspot_ids):
        raise ValueError("Percentage hotspot table hotspot_id values must not be empty")
    if len(set(hotspot_ids)) != len(hotspot_ids):
        raise ValueError("Percentage hotspot table hotspot_id values must be unique")

    for index, row in table.iterrows():
        if str(row["region_id"]).strip() != expected_region_id:
            raise ValueError(f"Percentage hotspot table row {index} has a mixed region_id")
        if str(row["dataset_key"]).strip() != expected_dataset_key:
            raise ValueError(f"Percentage hotspot table row {index} has a mixed dataset_key")
        dataset_ids = _parse_dataset_ids_json(row["dataset_ids_json"])
        if dataset_ids != expected_dataset_ids:
            raise ValueError(f"Percentage hotspot table row {index} has mixed dataset ids")
        _parse_bbox_literal(row["bbox"])
        wetland_percentage = float(row["wetland_percentage"])
        wetland_area_km2 = float(row["wetland_area_km2"])
        valid_area_km2 = float(row["valid_area_km2"])
        center_lat = float(row["center_lat"])
        center_lon = float(row["center_lon"])
        std_wetland_percentage = float(row["std_wetland_percentage"])
        valid_dataset_count = int(row["valid_dataset_count"])
        if not all(
            math.isfinite(value)
            for value in (
                wetland_percentage,
                wetland_area_km2,
                valid_area_km2,
                center_lat,
                center_lon,
                std_wetland_percentage,
            )
        ):
            raise ValueError(f"Percentage hotspot row {index} contains non-finite values")
        if valid_dataset_count <= 0:
            raise ValueError(f"Percentage hotspot row {index} valid_dataset_count must be positive")


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    try:
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _relative_to_root(path: Path, root: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return None


def _optional_string(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
