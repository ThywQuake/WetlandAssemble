"""Contract-backed trend hotspot manifests and CSV companions."""

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

from WA.comparison.evidence_contract import (
    EvidenceContract,
    metadata_json,
    validate_stem_token,
)
from WA.comparison.trend_agreement import TrendAgreementResult
from WA.loaders.base import BBox

logger = logging.getLogger(__name__)

TREND_HOTSPOT_MANIFEST_VERSION = 1
TREND_HOTSPOT_RANKING = (
    "disagreement_score desc",
    "slope_std desc",
    "center_lat desc",
    "center_lon asc",
)
TREND_HOTSPOT_TABLE_COLUMNS = (
    "hotspot_id",
    "hotspot_rank",
    "region_id",
    "participant_set_key",
    "participant_ids_json",
    "overlap_window_start",
    "overlap_window_end",
    "center_lat",
    "center_lon",
    "bbox",
    "disagreement_score",
    "agreement_ratio",
    "slope_std",
    "mean_slope",
)


@dataclass(frozen=True)
class TrendHotspotManifest:
    """Validated metadata for one trend hotspot JSON/CSV pair."""

    manifest_path: Path
    table_path: Path
    region_id: str
    participant_ids: tuple[str, ...]
    participant_set_key: str
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
class TrendHotspotReload:
    """Reloaded manifest plus validated hotspot table."""

    manifest: TrendHotspotManifest
    table: pd.DataFrame


def normalize_participant_ids(participant_ids: Iterable[str]) -> tuple[str, ...]:
    """Return stable, sorted participant ids for contract-backed artifact keys."""

    normalized = [
        validate_stem_token(str(participant_id), label="participant_id")
        for participant_id in participant_ids
    ]
    if not normalized:
        raise ValueError("participant_ids must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError("participant_ids must not contain duplicates")
    return tuple(sorted(normalized))


def build_participant_set_key(participant_ids: Iterable[str]) -> str:
    """Build a stable participant-set key for contract artifact stems."""

    return "+".join(normalize_participant_ids(participant_ids))


def trend_hotspot_manifest_relpath(
    contract: EvidenceContract,
    *,
    region_id: str,
    participant_ids: Iterable[str],
) -> Path:
    """Return the contract-stable relpath for one trend hotspot manifest."""

    participant_set_key = build_participant_set_key(participant_ids)
    return contract.artifact_relpath(
        kind="trend_hotspot_manifest",
        dataset_or_key=participant_set_key,
        region_id=region_id,
    )


def trend_hotspot_manifest_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    participant_ids: Iterable[str],
) -> Path:
    """Return the output path for one trend hotspot manifest."""

    return contract.output_root / trend_hotspot_manifest_relpath(
        contract,
        region_id=region_id,
        participant_ids=participant_ids,
    )


def trend_hotspot_table_relpath(
    contract: EvidenceContract,
    *,
    region_id: str,
    participant_ids: Iterable[str],
) -> Path:
    """Return the CSV companion relpath for one trend hotspot manifest."""

    return trend_hotspot_manifest_relpath(
        contract,
        region_id=region_id,
        participant_ids=participant_ids,
    ).with_suffix(".csv")


def trend_hotspot_table_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    participant_ids: Iterable[str],
) -> Path:
    """Return the CSV companion output path for one trend hotspot manifest."""

    return contract.output_root / trend_hotspot_table_relpath(
        contract,
        region_id=region_id,
        participant_ids=participant_ids,
    )


def build_trend_hotspot_table(
    agreement_result: TrendAgreementResult,
    *,
    region_id: str,
    participant_ids: Iterable[str] | None = None,
    top_n: int = 10,
) -> pd.DataFrame:
    """Select disagreement-first hotspot rows from one agreement result."""

    if top_n <= 0:
        raise ValueError("top_n must be positive")
    if agreement_result.status != "computed":
        raise ValueError(
            "Trend hotspot selection requires agreement_result.status='computed'"
        )

    normalized_participants = normalize_participant_ids(
        participant_ids
        if participant_ids is not None
        else agreement_result.participant_ids
    )
    result_participants = normalize_participant_ids(agreement_result.participant_ids)
    if normalized_participants != result_participants:
        raise ValueError(
            "participant_ids do not match agreement_result.participant_ids after sorting"
        )

    disputed = _require_spatial_dataarray("disputed", agreement_result.disputed)
    agreement_ratio = _require_spatial_dataarray(
        "agreement_ratio",
        agreement_result.agreement_ratio,
        reference=disputed,
    )
    slope_std = _require_spatial_dataarray(
        "slope_std",
        agreement_result.slope_std,
        reference=disputed,
    )
    mean_slope = _require_spatial_dataarray(
        "mean_slope",
        agreement_result.mean_slope,
        reference=disputed,
    )

    lat_values = np.asarray(disputed.coords["lat"].values, dtype=np.float64)
    lon_values = np.asarray(disputed.coords["lon"].values, dtype=np.float64)
    lat_edges = _coordinate_edges(lat_values)
    lon_edges = _coordinate_edges(lon_values)

    participant_set_key = build_participant_set_key(normalized_participants)
    participant_ids_json = json.dumps(list(normalized_participants), separators=(",", ":"))
    overlap_start, overlap_end = agreement_result.overlap_window

    disputed_values = np.asarray(disputed.values)
    agreement_values = np.asarray(agreement_ratio.values, dtype=np.float64)
    slope_std_values = np.asarray(slope_std.values, dtype=np.float64)
    mean_slope_values = np.asarray(mean_slope.values, dtype=np.float64)

    rows: list[dict[str, object]] = []
    for lat_index, center_lat in enumerate(lat_values):
        for lon_index, center_lon in enumerate(lon_values):
            if not _as_bool(disputed_values[lat_index, lon_index]):
                continue
            agreement_cell = float(agreement_values[lat_index, lon_index])
            slope_std_cell = float(slope_std_values[lat_index, lon_index])
            if not math.isfinite(agreement_cell):
                continue
            if not math.isfinite(slope_std_cell):
                continue
            bbox = _bbox_for_cell(
                lat_index=lat_index,
                lon_index=lon_index,
                lat_edges=lat_edges,
                lon_edges=lon_edges,
            )
            mean_slope_cell = float(mean_slope_values[lat_index, lon_index])
            rows.append(
                {
                    "region_id": region_id,
                    "participant_set_key": participant_set_key,
                    "participant_ids_json": participant_ids_json,
                    "overlap_window_start": overlap_start,
                    "overlap_window_end": overlap_end,
                    "center_lat": float(center_lat),
                    "center_lon": float(center_lon),
                    "bbox": bbox,
                    "disagreement_score": float(1.0 - agreement_cell),
                    "agreement_ratio": agreement_cell,
                    "slope_std": slope_std_cell,
                    "mean_slope": mean_slope_cell,
                }
            )

    if not rows:
        raise ValueError(
            "No disputed trend-hotspot candidates were found; zero-candidate selections are invalid"
        )

    table = pd.DataFrame(rows)
    table = table.sort_values(
        ["disagreement_score", "slope_std", "center_lat", "center_lon"],
        ascending=[False, False, False, True],
        kind="mergesort",
    ).head(top_n)
    table = table.reset_index(drop=True)
    table.insert(
        0,
        "hotspot_id",
        [
            f"trend-{region_id}-{participant_set_key}-{rank:03d}"
            for rank in range(1, len(table) + 1)
        ],
    )
    table.insert(1, "hotspot_rank", list(range(1, len(table) + 1)))
    return table.loc[:, list(TREND_HOTSPOT_TABLE_COLUMNS)]


def write_trend_hotspot_outputs(
    *,
    contract: EvidenceContract,
    agreement_result: TrendAgreementResult,
    region_id: str,
    surface_output_path: str | Path,
    summary_output_path: str | Path,
    participant_ids: Iterable[str] | None = None,
    top_n: int = 10,
) -> TrendHotspotManifest:
    """Write one validated trend hotspot JSON/CSV pair."""

    normalized_participants = normalize_participant_ids(
        participant_ids
        if participant_ids is not None
        else agreement_result.participant_ids
    )
    participant_set_key = build_participant_set_key(normalized_participants)
    surface_path = Path(surface_output_path)
    summary_path = Path(summary_output_path)

    if not surface_path.is_file():
        raise FileNotFoundError(
            "Missing trend agreement surface for trend-hotspots: "
            f"region_id={region_id} participant_set_key={participant_set_key} path={surface_path}"
        )
    if not summary_path.is_file():
        raise FileNotFoundError(
            "Missing trend agreement summary for trend-hotspots: "
            f"region_id={region_id} participant_set_key={participant_set_key} path={summary_path}"
        )

    table = build_trend_hotspot_table(
        agreement_result,
        region_id=region_id,
        participant_ids=normalized_participants,
        top_n=top_n,
    )
    manifest_path = trend_hotspot_manifest_output_path(
        contract,
        region_id=region_id,
        participant_ids=normalized_participants,
    )
    table_path = trend_hotspot_table_output_path(
        contract,
        region_id=region_id,
        participant_ids=normalized_participants,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    table_serializable = table.copy()
    table_serializable["bbox"] = table_serializable["bbox"].map(_format_bbox_for_csv)
    table_text = table_serializable.to_csv(index=False, lineterminator="\n")
    table_sha256 = hashlib.sha256(table_text.encode("utf-8")).hexdigest()

    manifest_relpath = trend_hotspot_manifest_relpath(
        contract,
        region_id=region_id,
        participant_ids=normalized_participants,
    )
    table_relpath = trend_hotspot_table_relpath(
        contract,
        region_id=region_id,
        participant_ids=normalized_participants,
    )
    surface_relpath = _relative_to_root(surface_path, contract.output_root)
    summary_relpath = _relative_to_root(summary_path, contract.output_root)
    contract_metadata = {
        "artifact_kind": "trend_hotspot_manifest",
        "manifest_relpath": str(manifest_relpath),
        "table_relpath": str(table_relpath),
        "region_id": region_id,
        "participant_ids": list(normalized_participants),
        "participant_set_key": participant_set_key,
        "candidate_mask": "disputed",
        "ranking": list(TREND_HOTSPOT_RANKING),
        "surface_output_path": str(surface_path.resolve()),
        "summary_output_path": str(summary_path.resolve()),
        "surface_output_relpath": surface_relpath,
        "summary_output_relpath": summary_relpath,
        "table_sha256": table_sha256,
    }
    manifest_payload = {
        "artifact_kind": "trend_hotspot_manifest",
        "manifest_version": TREND_HOTSPOT_MANIFEST_VERSION,
        "region_id": region_id,
        "participant_ids": list(normalized_participants),
        "participant_set_key": participant_set_key,
        "hotspot_count": int(len(table)),
        "manifest_output_path": str(manifest_path.resolve()),
        "manifest_relpath": str(manifest_relpath),
        "table_output_path": str(table_path.resolve()),
        "table_relpath": str(table_relpath),
        "surface_output_path": str(surface_path.resolve()),
        "surface_output_relpath": surface_relpath,
        "summary_output_path": str(summary_path.resolve()),
        "summary_output_relpath": summary_relpath,
        "table_columns": list(TREND_HOTSPOT_TABLE_COLUMNS),
        "table_sha256": table_sha256,
        "contract_metadata_json": metadata_json(contract_metadata),
    }
    manifest_text = json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n"

    _write_text_atomic(table_path, table_text)
    _write_text_atomic(manifest_path, manifest_text)
    logger.info(
        "Trend hotspot write complete: region=%s participant_set_key=%s "
        "hotspots=%s manifest=%s table=%s",
        region_id,
        participant_set_key,
        len(table),
        manifest_path,
        table_path,
    )
    return load_trend_hotspot_manifest(manifest_path)


def load_trend_hotspot_manifest(path: str | Path) -> TrendHotspotManifest:
    """Load and validate one trend hotspot manifest JSON file."""

    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Trend hotspot manifest must be a JSON object: {manifest_path}")
    if payload.get("artifact_kind") != "trend_hotspot_manifest":
        raise ValueError(
            f"Expected artifact_kind='trend_hotspot_manifest', got {payload.get('artifact_kind')!r}"
        )

    participant_ids_raw = payload.get("participant_ids")
    if not isinstance(participant_ids_raw, list):
        raise ValueError("Trend hotspot manifest must contain a participant_ids list")
    participant_ids = normalize_participant_ids(participant_ids_raw)
    if participant_ids_raw != list(participant_ids):
        raise ValueError("Trend hotspot manifest participant_ids must already be sorted")

    participant_set_key = str(payload.get("participant_set_key", "")).strip()
    expected_participant_key = build_participant_set_key(participant_ids)
    if participant_set_key != expected_participant_key:
        raise ValueError(
            "Trend hotspot manifest participant_set_key does not match participant_ids"
        )

    region_id = validate_stem_token(str(payload.get("region_id", "")), label="region_id")
    hotspot_count = int(payload.get("hotspot_count", 0))
    if hotspot_count <= 0:
        raise ValueError("Trend hotspot manifest hotspot_count must be positive")

    table_sha256 = str(payload.get("table_sha256", "")).strip()
    if len(table_sha256) != 64:
        raise ValueError("Trend hotspot manifest table_sha256 must be a SHA-256 hex digest")

    manifest_output_path = Path(str(payload.get("manifest_output_path", manifest_path)))
    if manifest_output_path.resolve() != manifest_path.resolve():
        raise ValueError("Trend hotspot manifest_output_path does not match the loaded path")

    table_path = Path(str(payload.get("table_output_path", "")))
    surface_output_path = Path(str(payload.get("surface_output_path", "")))
    summary_output_path = Path(str(payload.get("summary_output_path", "")))
    for label, candidate in (
        ("table_output_path", table_path),
        ("surface_output_path", surface_output_path),
        ("summary_output_path", summary_output_path),
    ):
        if not str(candidate).strip():
            raise ValueError(f"Trend hotspot manifest is missing {label}")
        if not candidate.is_file():
            raise FileNotFoundError(
                f"Trend hotspot manifest references missing {label}: {candidate}"
            )

    contract_metadata_json = str(payload.get("contract_metadata_json", "")).strip()
    if not contract_metadata_json:
        raise ValueError("Trend hotspot manifest is missing contract_metadata_json")
    try:
        contract_metadata = json.loads(contract_metadata_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Malformed contract_metadata_json in trend hotspot manifest") from exc
    if not isinstance(contract_metadata, dict):
        raise ValueError("Trend hotspot manifest contract_metadata_json must decode to an object")

    manifest_relpath = str(payload.get("manifest_relpath", "")).strip()
    table_relpath = str(payload.get("table_relpath", "")).strip()
    if not manifest_relpath or not table_relpath:
        raise ValueError("Trend hotspot manifest must contain manifest_relpath and table_relpath")

    return TrendHotspotManifest(
        manifest_path=manifest_path.resolve(),
        table_path=table_path.resolve(),
        region_id=region_id,
        participant_ids=participant_ids,
        participant_set_key=participant_set_key,
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


def load_contract_trend_hotspot_table(
    *,
    contract: EvidenceContract,
    region_id: str,
    participant_ids: Iterable[str],
) -> TrendHotspotReload:
    """Load one trend hotspot JSON/CSV pair by contract semantics."""

    normalized_participants = normalize_participant_ids(participant_ids)
    manifest_path = trend_hotspot_manifest_output_path(
        contract,
        region_id=region_id,
        participant_ids=normalized_participants,
    )
    expected_table_path = trend_hotspot_table_output_path(
        contract,
        region_id=region_id,
        participant_ids=normalized_participants,
    ).resolve()
    manifest = load_trend_hotspot_manifest(manifest_path)
    if manifest.region_id != region_id:
        raise ValueError(
            "Trend hotspot manifest region mismatch: "
            f"expected {region_id!r}, got {manifest.region_id!r}"
        )
    if manifest.participant_ids != normalized_participants:
        raise ValueError(
            "Trend hotspot manifest participant_ids do not match the requested participant set"
        )
    if manifest.table_path != expected_table_path:
        raise ValueError(
            "Trend hotspot manifest table_output_path does not match contract semantics"
        )

    table_text = manifest.table_path.read_text(encoding="utf-8")
    table_sha256 = hashlib.sha256(table_text.encode("utf-8")).hexdigest()
    if table_sha256 != manifest.table_sha256:
        raise ValueError(
            "Trend hotspot table SHA mismatch; refusing to reuse a partial or stale JSON/CSV pair"
        )

    table = pd.read_csv(manifest.table_path)
    _validate_trend_hotspot_table(
        table,
        manifest=manifest,
        expected_region_id=region_id,
        expected_participant_ids=normalized_participants,
    )
    table = table.copy()
    table["bbox"] = table["bbox"].map(_parse_bbox_literal)
    table["participant_ids"] = table["participant_ids_json"].map(_parse_participant_ids_json)
    return TrendHotspotReload(manifest=manifest, table=table)


def _require_spatial_dataarray(
    name: str,
    data: xr.DataArray,
    *,
    reference: xr.DataArray | None = None,
) -> xr.DataArray:
    if not isinstance(data, xr.DataArray):
        raise TypeError(f"{name} must be an xarray.DataArray")
    if {"lat", "lon"} - set(data.dims):
        raise ValueError(f"{name} must contain lat/lon dims, got {data.dims!r}")
    normalized = data.transpose("lat", "lon")
    if reference is not None:
        reference_normalized = reference.transpose("lat", "lon")
        if normalized.shape != reference_normalized.shape:
            raise ValueError(
                f"{name} shape {normalized.shape!r} does not match "
                f"reference {reference_normalized.shape!r}"
            )
        if not np.array_equal(normalized["lat"].values, reference_normalized["lat"].values):
            raise ValueError(f"{name} lat coordinates do not match reference")
        if not np.array_equal(normalized["lon"].values, reference_normalized["lon"].values):
            raise ValueError(f"{name} lon coordinates do not match reference")
    return normalized


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


def _parse_participant_ids_json(value: object) -> tuple[str, ...]:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid participant_ids_json: {value!r}") from exc
    if not isinstance(parsed, list):
        raise ValueError("participant_ids_json must decode to a list")
    return normalize_participant_ids(parsed)


def _validate_trend_hotspot_table(
    table: pd.DataFrame,
    *,
    manifest: TrendHotspotManifest,
    expected_region_id: str,
    expected_participant_ids: tuple[str, ...],
) -> None:
    missing_columns = [
        column for column in TREND_HOTSPOT_TABLE_COLUMNS if column not in table.columns
    ]
    if missing_columns:
        raise ValueError(
            "Trend hotspot table is missing required columns: "
            + ", ".join(missing_columns)
        )
    if len(table) != manifest.hotspot_count:
        raise ValueError(
            "Trend hotspot table row count "
            f"{len(table)} does not match "
            f"manifest.hotspot_count {manifest.hotspot_count}"
        )

    expected_participant_key = build_participant_set_key(expected_participant_ids)
    expected_ranks = list(range(1, len(table) + 1))
    if table["hotspot_rank"].astype(int).tolist() != expected_ranks:
        raise ValueError("Trend hotspot table hotspot_rank must be sequential starting at 1")

    for index, row in table.iterrows():
        if str(row["region_id"]).strip() != expected_region_id:
            raise ValueError(f"Trend hotspot table row {index} has a mixed region_id")
        if str(row["participant_set_key"]).strip() != expected_participant_key:
            raise ValueError(
                f"Trend hotspot table row {index} has a mixed participant_set_key"
            )
        participant_ids = _parse_participant_ids_json(row["participant_ids_json"])
        if participant_ids != expected_participant_ids:
            raise ValueError(
                f"Trend hotspot table row {index} has mixed participant ids"
            )
        _parse_bbox_literal(row["bbox"])
        agreement_ratio = float(row["agreement_ratio"])
        disagreement_score = float(row["disagreement_score"])
        slope_std = float(row["slope_std"])
        center_lat = float(row["center_lat"])
        center_lon = float(row["center_lon"])
        if not math.isfinite(agreement_ratio):
            raise ValueError(f"Trend hotspot row {index} agreement_ratio must be finite")
        if not math.isfinite(disagreement_score):
            raise ValueError(
                f"Trend hotspot row {index} disagreement_score must be finite"
            )
        if not math.isfinite(slope_std):
            raise ValueError(f"Trend hotspot row {index} slope_std must be finite")
        if not math.isfinite(center_lat) or not math.isfinite(center_lon):
            raise ValueError(f"Trend hotspot row {index} center coordinates must be finite")
        if not math.isclose(disagreement_score, 1.0 - agreement_ratio, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(
                f"Trend hotspot row {index} disagreement_score must equal 1 - agreement_ratio"
            )


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
    temp_path.replace(path)


def _relative_to_root(path: Path, root: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return None


def _optional_string(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _as_bool(value: object) -> bool:
    if pd.isna(value):
        return False
    return bool(value)
