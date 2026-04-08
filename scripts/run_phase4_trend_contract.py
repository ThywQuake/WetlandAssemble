#!/usr/bin/env python3
"""Generate contract-backed Phase 4 trend surfaces, summaries, agreement, and hotspots."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.comparison.evidence_contract import (  # noqa: E402
    DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    DEFAULT_PHASE4_REGIONS_FILE,
    SUPPORTED_PHASE4_REGION_SUBSETS,
    load_phase4_evidence_contract,
    metadata_json,
)
from WA.comparison.trend_agreement import (  # noqa: E402
    TrendAgreementResult,
    compute_trend_agreement,
)
from WA.comparison.trend_contract import (  # noqa: E402
    TrendSummaryBundle,
    TrendSurfaceBundle,
    load_contract_trend_summary,
    load_contract_trend_surface,
    trend_summary_output_path,
    trend_surface_output_path,
    write_contract_trend_summary,
    write_contract_trend_surface,
)
from WA.comparison.trend_hotspots import (  # noqa: E402
    build_participant_set_key,
    load_contract_trend_hotspot_table,
    normalize_participant_ids,
    trend_hotspot_manifest_output_path,
    trend_hotspot_table_output_path,
    write_trend_hotspot_outputs,
)
from WA.comparison.trends import (  # noqa: E402
    TrendCheckpointBundle,
    materialize_trend_checkpoint,
)

logger = logging.getLogger(__name__)

DEFAULT_TREND_PARTICIPANT_IDS = (
    "gwd30",
    "giems_mc",
    "topmodel",
    "swamps",
    "wad2m",
)
REQUIRED_AGREEMENT_VARS = (
    "agreement_ratio",
    "mean_slope",
    "slope_std",
    "robust_increase",
    "robust_decrease",
    "robust_stable",
    "disputed",
)
REQUIRED_AGREEMENT_SUMMARY_COLUMNS = (
    "region",
    "total_valid_pixels",
    "mean_agreement_ratio",
    "fraction_robust_increase",
    "fraction_robust_decrease",
    "fraction_robust_stable",
    "fraction_disputed",
    "mean_slope_across_datasets",
    "region_id",
    "participant_set_key",
    "participant_ids_json",
    "overlap_window_start",
    "overlap_window_end",
    "contract_metadata_json",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate one contract-backed Phase 4 trend family: per-dataset "
            "trend_surface and trend_regional_summary artifacts, then the "
            "participant-set trend agreement and trend-hotspots JSON/CSV outputs. "
            "Wide runs first reuse or rebuild explicit region/dataset/time-window "
            "checkpoints before the agreement stage."
        )
    )
    parser.add_argument("--regions-file", default=str(DEFAULT_PHASE4_REGIONS_FILE))
    parser.add_argument(
        "--subset",
        choices=SUPPORTED_PHASE4_REGION_SUBSETS,
        default=None,
        help=(
            "Evidence-contract priority-region subset. Use 'canonical' for the "
            "four-region hydro-diverse subset or 'ten' for the full ordered contract "
            "list. Omit --subset to keep the canonical default unless --region is "
            "passed explicitly."
        ),
    )
    parser.add_argument(
        "--region",
        action="append",
        default=[],
        help="Explicit region id override; may be repeated. Cannot be combined with --subset.",
    )
    parser.add_argument(
        "--dataset-id",
        action="append",
        default=[],
        help=(
            "Participant dataset id. Repeat to override the default wetland trend set "
            f"({', '.join(DEFAULT_TREND_PARTICIPANT_IDS)})."
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    )
    parser.add_argument(
        "--standardized-dir",
        type=Path,
        default=Path("output/standardized"),
        help="Standardized dataset root used by trend surface loaders.",
    )
    parser.add_argument(
        "--aggregation",
        choices=("annual", "seasonal", "monthly"),
        default="annual",
        help="Trend aggregation level passed into compute_pixel_trends (default: annual).",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=1990,
        help="Start year for the trend window (default: 1990).",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2020,
        help="End year for the trend window (default: 2020).",
    )
    parser.add_argument(
        "--min-observations",
        type=int,
        default=5,
        help="Minimum aggregated observations required per dataset trend (default: 5).",
    )
    parser.add_argument(
        "--min-overlap-years",
        type=int,
        default=5,
        help="Minimum common overlap window required for agreement (default: 5).",
    )
    parser.add_argument(
        "--top-hotspots",
        type=int,
        default=10,
        help="Maximum disputed trend-hotspots to retain per region (default: 10).",
    )
    parser.add_argument(
        "--skip",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Reuse valid dataset checkpoints plus complete trend/agreement/hotspot "
            "artifacts when present (default: True)."
        ),
    )
    parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show loader progress where available (default: True).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="[%(levelname)s] %(message)s",
    )

    if args.start_year > args.end_year:
        raise ValueError("start_year must be <= end_year")

    contract = load_phase4_evidence_contract(
        output_root=args.output_root,
        regions_file=args.regions_file,
    )
    contract.output_root.mkdir(parents=True, exist_ok=True)
    participant_ids = normalize_participant_ids(
        args.dataset_id if args.dataset_id else DEFAULT_TREND_PARTICIPANT_IDS
    )
    participant_set_key = build_participant_set_key(participant_ids)
    time_range = (f"{args.start_year}-01-01", f"{args.end_year}-12-31")

    try:
        regions = contract.resolve_regions(
            subset=args.subset,
            requested_region_ids=args.region or None,
        )
    except Exception as exc:
        logger.error(
            "stage=region-selector subset=%s requested_regions=%s participant_set_key=%s error=%s",
            args.subset or "<none>",
            args.region,
            participant_set_key,
            exc,
        )
        raise

    selector_subset = args.subset or ("explicit-region-list" if args.region else "canonical")
    logger.info(
        "stage=region-selector subset=%s participant_set_key=%s region_ids=%s",
        selector_subset,
        participant_set_key,
        [region.region_id for region in regions],
    )
    logger.info(
        "Phase4 trend contract start: subset=%s regions=%s participant_set_key=%s "
        "time_range=%s aggregation=%s skip=%s",
        selector_subset,
        [region.region_id for region in regions],
        participant_set_key,
        time_range,
        args.aggregation,
        args.skip,
    )

    for region in regions:
        logger.info(
            "stage=trend region=%s participant_set_key=%s bbox=%s action=start",
            region.region_id,
            participant_set_key,
            region.bbox,
        )
        trend_results = {}
        for dataset_id in participant_ids:
            checkpoint_bundle = materialize_trend_checkpoint(
                output_root=args.output_root,
                region_id=region.region_id,
                bbox=region.bbox,
                dataset_id=dataset_id,
                time_range=time_range,
                aggregation=args.aggregation,
                min_observations=args.min_observations,
                gwd30_standardized_dir=args.standardized_dir,
                show_progress=args.progress,
                skip_existing=args.skip,
            )
            trend_results[dataset_id] = checkpoint_bundle.trend_result
            _materialize_trend_artifacts(
                contract=contract,
                region=region,
                checkpoint_bundle=checkpoint_bundle,
                skip_existing=args.skip,
            )

        agreement_result = compute_trend_agreement(
            trend_results,
            min_overlap_years=args.min_overlap_years,
            region_bboxes={region.region_id: region.bbox},
        )
        if agreement_result.status != "computed":
            raise ValueError(
                "stage=agreement "
                f"region={region.region_id} participant_set_key={participant_set_key} "
                "cannot continue because "
                f"agreement_result.status={agreement_result.status}"
            )

        agreement_surface_path, agreement_summary_path = _materialize_agreement_artifacts(
            contract=contract,
            region_id=region.region_id,
            participant_ids=participant_ids,
            agreement_result=agreement_result,
            skip_existing=args.skip,
        )

        _materialize_trend_hotspots(
            contract=contract,
            region_id=region.region_id,
            participant_ids=participant_ids,
            agreement_result=agreement_result,
            agreement_surface_path=agreement_surface_path,
            agreement_summary_path=agreement_summary_path,
            top_hotspots=args.top_hotspots,
            skip_existing=args.skip,
        )

    logger.info(
        "Phase4 trend contract complete: regions=%s participant_set_key=%s",
        [region.region_id for region in regions],
        participant_set_key,
    )
    return 0


def _materialize_trend_artifacts(
    *,
    contract,
    region,
    checkpoint_bundle: TrendCheckpointBundle,
    skip_existing: bool,
) -> tuple[TrendSurfaceBundle, TrendSummaryBundle]:
    surface_path = trend_surface_output_path(
        contract,
        region_id=region.region_id,
        dataset_id=checkpoint_bundle.dataset_id,
    )
    summary_path = trend_summary_output_path(
        contract,
        region_id=region.region_id,
        dataset_id=checkpoint_bundle.dataset_id,
    )

    if skip_existing and (surface_path.exists() or summary_path.exists()):
        _require_complete_pair(
            label="trend-write",
            region_id=region.region_id,
            family_key=checkpoint_bundle.dataset_id,
            left_path=surface_path,
            right_path=summary_path,
        )
        logger.info(
            "stage=trend-write region=%s dataset_id=%s action=reload surface=%s summary=%s",
            region.region_id,
            checkpoint_bundle.dataset_id,
            surface_path,
            summary_path,
        )
        surface_bundle = load_contract_trend_surface(
            contract=contract,
            region_id=region.region_id,
            dataset_id=checkpoint_bundle.dataset_id,
            expected_aggregation=checkpoint_bundle.aggregation,
            expected_time_range=checkpoint_bundle.time_range,
        )
        summary_bundle = load_contract_trend_summary(
            contract=contract,
            region_id=region.region_id,
            dataset_id=checkpoint_bundle.dataset_id,
            expected_aggregation=checkpoint_bundle.aggregation,
            expected_time_range=checkpoint_bundle.time_range,
        )
    else:
        logger.info(
            "stage=trend-write region=%s dataset_id=%s action=%s surface=%s summary=%s",
            region.region_id,
            checkpoint_bundle.dataset_id,
            "rebuild" if surface_path.exists() or summary_path.exists() else "write",
            surface_path,
            summary_path,
        )
        surface_bundle = write_contract_trend_surface(
            contract=contract,
            region_id=region.region_id,
            region_label=region.label,
            bbox=region.bbox,
            trend_result=checkpoint_bundle.trend_result,
        )
        summary_bundle = write_contract_trend_summary(
            contract=contract,
            region_id=region.region_id,
            region_label=region.label,
            bbox=region.bbox,
            trend_result=checkpoint_bundle.trend_result,
            surface_output_path=surface_bundle.surface_path,
        )

    logger.info(
        "stage=trend-write region=%s dataset_id=%s action=ready checkpoint=%s "
        "surface=%s summary=%s",
        region.region_id,
        checkpoint_bundle.dataset_id,
        checkpoint_bundle.checkpoint_path,
        surface_bundle.surface_path,
        summary_bundle.summary_path,
    )
    return (surface_bundle, summary_bundle)


def _materialize_agreement_artifacts(
    *,
    contract,
    region_id: str,
    participant_ids: tuple[str, ...],
    agreement_result: TrendAgreementResult,
    skip_existing: bool,
) -> tuple[Path, Path]:
    participant_set_key = build_participant_set_key(participant_ids)
    surface_path = contract.artifact_output_path(
        kind="trend_agreement_surface",
        dataset_or_key=participant_set_key,
        region_id=region_id,
    )
    summary_path = contract.artifact_output_path(
        kind="trend_agreement_summary",
        dataset_or_key=participant_set_key,
        region_id=region_id,
    )

    if skip_existing and (surface_path.exists() or summary_path.exists()):
        _require_complete_pair(
            label="agreement",
            region_id=region_id,
            family_key=participant_set_key,
            left_path=surface_path,
            right_path=summary_path,
        )
        logger.info(
            "stage=agreement region=%s participant_set_key=%s action=reload surface=%s summary=%s",
            region_id,
            participant_set_key,
            surface_path,
            summary_path,
        )
        _load_trend_agreement_artifacts(
            contract=contract,
            region_id=region_id,
            participant_ids=participant_ids,
        )
        return (surface_path, summary_path)

    logger.info(
        "stage=agreement region=%s participant_set_key=%s action=write surface=%s summary=%s",
        region_id,
        participant_set_key,
        surface_path,
        summary_path,
    )
    _write_trend_agreement_artifacts(
        contract=contract,
        region_id=region_id,
        participant_ids=participant_ids,
        agreement_result=agreement_result,
    )
    _load_trend_agreement_artifacts(
        contract=contract,
        region_id=region_id,
        participant_ids=participant_ids,
    )
    return (surface_path, summary_path)


def _materialize_trend_hotspots(
    *,
    contract,
    region_id: str,
    participant_ids: tuple[str, ...],
    agreement_result: TrendAgreementResult,
    agreement_surface_path: Path,
    agreement_summary_path: Path,
    top_hotspots: int,
    skip_existing: bool,
) -> None:
    participant_set_key = build_participant_set_key(participant_ids)
    manifest_path = trend_hotspot_manifest_output_path(
        contract,
        region_id=region_id,
        participant_ids=participant_ids,
    )
    table_path = trend_hotspot_table_output_path(
        contract,
        region_id=region_id,
        participant_ids=participant_ids,
    )

    if skip_existing and (manifest_path.exists() or table_path.exists()):
        _require_complete_pair(
            label="trend-hotspots",
            region_id=region_id,
            family_key=participant_set_key,
            left_path=manifest_path,
            right_path=table_path,
        )
        logger.info(
            "stage=trend-hotspots region=%s participant_set_key=%s "
            "action=reload manifest=%s table=%s",
            region_id,
            participant_set_key,
            manifest_path,
            table_path,
        )
        bundle = load_contract_trend_hotspot_table(
            contract=contract,
            region_id=region_id,
            participant_ids=participant_ids,
        )
    else:
        logger.info(
            "stage=trend-hotspots region=%s participant_set_key=%s "
            "action=write manifest=%s table=%s",
            region_id,
            participant_set_key,
            manifest_path,
            table_path,
        )
        write_trend_hotspot_outputs(
            contract=contract,
            agreement_result=agreement_result,
            region_id=region_id,
            participant_ids=participant_ids,
            surface_output_path=agreement_surface_path,
            summary_output_path=agreement_summary_path,
            top_n=top_hotspots,
        )
        bundle = load_contract_trend_hotspot_table(
            contract=contract,
            region_id=region_id,
            participant_ids=participant_ids,
        )

    logger.info(
        "stage=trend-hotspots region=%s participant_set_key=%s "
        "action=ready hotspots=%s manifest=%s table=%s",
        region_id,
        participant_set_key,
        len(bundle.table),
        bundle.manifest.manifest_path,
        bundle.manifest.table_path,
    )


def _write_trend_agreement_artifacts(
    *,
    contract,
    region_id: str,
    participant_ids: tuple[str, ...],
    agreement_result: TrendAgreementResult,
) -> tuple[Path, Path]:
    participant_set_key = build_participant_set_key(participant_ids)
    surface_path = contract.artifact_output_path(
        kind="trend_agreement_surface",
        dataset_or_key=participant_set_key,
        region_id=region_id,
    )
    summary_path = contract.artifact_output_path(
        kind="trend_agreement_summary",
        dataset_or_key=participant_set_key,
        region_id=region_id,
    )
    surface_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    contract_metadata = {
        "artifact_kind": "trend_agreement_surface",
        "region_id": region_id,
        "participant_ids": list(participant_ids),
        "participant_set_key": participant_set_key,
        "surface_relpath": str(surface_path.relative_to(contract.output_root)),
        "summary_relpath": str(summary_path.relative_to(contract.output_root)),
    }
    contract_metadata_json = metadata_json(contract_metadata)

    agreement_dataset = xr.Dataset(
        {
            "agreement_ratio": agreement_result.agreement_ratio,
            "mean_slope": agreement_result.mean_slope,
            "slope_std": agreement_result.slope_std,
            "robust_increase": agreement_result.robust_increase,
            "robust_decrease": agreement_result.robust_decrease,
            "robust_stable": agreement_result.robust_stable,
            "disputed": agreement_result.disputed,
        }
    )
    agreement_dataset.attrs.update(
        {
            "region_id": region_id,
            "participant_ids_json": json.dumps(list(participant_ids), separators=(",", ":")),
            "participant_set_key": participant_set_key,
            "overlap_window_start": agreement_result.overlap_window[0],
            "overlap_window_end": agreement_result.overlap_window[1],
            "status": agreement_result.status,
            "contract_metadata_json": contract_metadata_json,
        }
    )

    summary = agreement_result.regional_summary.copy()
    summary["region_id"] = region_id
    summary["participant_set_key"] = participant_set_key
    summary["participant_ids_json"] = json.dumps(
        list(participant_ids),
        separators=(",", ":"),
    )
    summary["overlap_window_start"] = agreement_result.overlap_window[0]
    summary["overlap_window_end"] = agreement_result.overlap_window[1]
    summary["contract_metadata_json"] = contract_metadata_json

    _write_dataset_atomic(surface_path, agreement_dataset)
    _write_text_atomic(summary_path, summary.to_csv(index=False, lineterminator="\n"))
    return (surface_path, summary_path)


def _load_trend_agreement_artifacts(
    *,
    contract,
    region_id: str,
    participant_ids: tuple[str, ...],
) -> TrendAgreementResult:
    participant_set_key = build_participant_set_key(participant_ids)
    surface_path = contract.artifact_output_path(
        kind="trend_agreement_surface",
        dataset_or_key=participant_set_key,
        region_id=region_id,
    )
    summary_path = contract.artifact_output_path(
        kind="trend_agreement_summary",
        dataset_or_key=participant_set_key,
        region_id=region_id,
    )
    _require_complete_pair(
        label="agreement",
        region_id=region_id,
        family_key=participant_set_key,
        left_path=surface_path,
        right_path=summary_path,
    )

    dataset = xr.load_dataset(surface_path)
    missing_vars = [
        name for name in REQUIRED_AGREEMENT_VARS if name not in dataset.data_vars
    ]
    if missing_vars:
        raise ValueError(
            "stage=agreement "
            f"region={region_id} participant_set_key={participant_set_key} "
            f"missing variables={', '.join(missing_vars)}"
        )

    surface_region_id = str(dataset.attrs.get("region_id", "")).strip()
    if surface_region_id != region_id:
        raise ValueError(
            "stage=agreement "
            f"region={region_id} participant_set_key={participant_set_key} "
            f"surface region mismatch={surface_region_id}"
        )
    surface_participant_ids = _parse_participant_ids_json(
        dataset.attrs.get("participant_ids_json", "")
    )
    if surface_participant_ids != participant_ids:
        raise ValueError(
            "stage=agreement "
            f"region={region_id} participant_set_key={participant_set_key} "
            "participant_ids mismatch"
        )
    _parse_contract_metadata_json(dataset.attrs.get("contract_metadata_json", ""))

    summary = pd.read_csv(summary_path)
    missing_columns = [
        column
        for column in REQUIRED_AGREEMENT_SUMMARY_COLUMNS
        if column not in summary.columns
    ]
    if missing_columns:
        raise ValueError(
            "stage=agreement "
            f"region={region_id} participant_set_key={participant_set_key} "
            f"missing summary columns={', '.join(missing_columns)}"
        )
    if summary.empty:
        raise ValueError(
            "stage=agreement "
            f"region={region_id} participant_set_key={participant_set_key} "
            "summary must not be empty"
        )
    if any(str(value).strip() != region_id for value in summary["region_id"]):
        raise ValueError(
            "stage=agreement "
            f"region={region_id} participant_set_key={participant_set_key} "
            "summary contains mixed region_id values"
        )
    if any(
        str(value).strip() != participant_set_key
        for value in summary["participant_set_key"]
    ):
        raise ValueError(
            "stage=agreement "
            f"region={region_id} participant_set_key={participant_set_key} "
            "summary contains mixed participant_set_key values"
        )
    for value in summary["participant_ids_json"]:
        if _parse_participant_ids_json(value) != participant_ids:
            raise ValueError(
                "stage=agreement "
                f"region={region_id} participant_set_key={participant_set_key} "
                "summary contains mixed participant ids"
            )
    for value in summary["contract_metadata_json"]:
        _parse_contract_metadata_json(value)

    return TrendAgreementResult(
        overlap_window=(
            str(dataset.attrs.get("overlap_window_start", "")),
            str(dataset.attrs.get("overlap_window_end", "")),
        ),
        participant_ids=list(participant_ids),
        agreement_ratio=dataset["agreement_ratio"],
        mean_slope=dataset["mean_slope"],
        slope_std=dataset["slope_std"],
        robust_increase=dataset["robust_increase"].astype(bool),
        robust_decrease=dataset["robust_decrease"].astype(bool),
        robust_stable=dataset["robust_stable"].astype(bool),
        disputed=dataset["disputed"].astype(bool),
        regional_summary=summary,
        status=str(dataset.attrs.get("status", "computed")),
    )


def _require_complete_pair(
    *,
    label: str,
    region_id: str,
    family_key: str,
    left_path: Path,
    right_path: Path,
) -> None:
    left_exists = left_path.is_file()
    right_exists = right_path.is_file()
    if left_exists and right_exists:
        return
    if left_exists or right_exists:
        raise FileNotFoundError(
            f"stage={label} region={region_id} "
            f"family_key={family_key} found partial artifact pair: "
            f"{left_path} exists={left_exists} {right_path} exists={right_exists}"
        )


def _parse_participant_ids_json(value: object) -> tuple[str, ...]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed participant_ids_json: {value!r}") from exc
    if not isinstance(payload, list):
        raise ValueError("participant_ids_json must decode to a list")
    return normalize_participant_ids(payload)


def _parse_contract_metadata_json(value: object) -> dict[str, object]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed contract_metadata_json: {value!r}") from exc
    if not isinstance(payload, dict):
        raise ValueError("contract_metadata_json must decode to an object")
    return payload


def _write_dataset_atomic(path: Path, dataset: xr.Dataset) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        dataset.to_netcdf(temp_path)
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


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


if __name__ == "__main__":
    raise SystemExit(main())
