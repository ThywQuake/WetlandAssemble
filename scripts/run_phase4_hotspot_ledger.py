#!/usr/bin/env python3
"""Build or reopen contract-backed unified Phase 4 hotspot ledgers."""

from __future__ import annotations

import argparse
import logging
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.comparison.evidence_contract import (  # noqa: E402
    DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    DEFAULT_PHASE4_REGIONS_FILE,
    SUPPORTED_PHASE4_REGION_SUBSETS,
    load_phase4_evidence_contract,
)
from WA.comparison.hotspot_ledger import (  # noqa: E402
    load_contract_unified_hotspot_ledger,
    unified_hotspot_ledger_output_path,
    write_unified_hotspot_ledger,
)
from WA.comparison.scaleout_readiness import (  # noqa: E402
    DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS,
    write_scaleout_readiness_report,
)
from WA.comparison.trend_hotspots import (  # noqa: E402
    build_participant_set_key,
    normalize_participant_ids,
)

logger = logging.getLogger(__name__)

DEFAULT_TREND_PARTICIPANT_IDS = DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or reload one contract-backed unified hotspot ledger from the "
            "percentage, classification, and trend hotspot families. The ledger stage "
            "fails closed when any family is missing or malformed; run "
            "scripts/run_phase4_scaleout_readiness.py first to inspect ready/missing/"
            "partial statuses before a wide rerun."
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
        "--output-root",
        type=Path,
        default=DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    )
    parser.add_argument(
        "--ledger-key",
        default="canonical",
        help="Stable ledger key used in the unified_hotspot_ledger artifact stem.",
    )
    parser.add_argument(
        "--percentage-key",
        default="canonical",
        help="Semantic key for the percentage hotspot family (default: canonical).",
    )
    parser.add_argument(
        "--classification-key",
        default="canonical",
        help="Semantic key for the classification hotspot family (default: canonical).",
    )
    parser.add_argument(
        "--trend-dataset-id",
        action="append",
        default=[],
        help=(
            "Trend participant dataset id. Repeat to override the default wetland set "
            f"({', '.join(DEFAULT_TREND_PARTICIPANT_IDS)})."
        ),
    )
    parser.add_argument(
        "--skip",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reuse an existing valid unified ledger when present (default: True).",
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

    contract = load_phase4_evidence_contract(
        output_root=args.output_root,
        regions_file=args.regions_file,
    )
    contract.output_root.mkdir(parents=True, exist_ok=True)
    trend_participant_ids = normalize_participant_ids(
        args.trend_dataset_id if args.trend_dataset_id else DEFAULT_TREND_PARTICIPANT_IDS
    )
    participant_set_key = build_participant_set_key(trend_participant_ids)
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
        "Phase4 hotspot ledger start: subset=%s regions=%s ledger_key=%s percentage_key=%s "
        "classification_key=%s participant_set_key=%s",
        selector_subset,
        [region.region_id for region in regions],
        args.ledger_key,
        args.percentage_key,
        args.classification_key,
        participant_set_key,
    )

    for region in regions:
        ledger_path = unified_hotspot_ledger_output_path(
            contract,
            ledger_key=args.ledger_key,
            region_id=region.region_id,
        )
        try:
            if args.skip and ledger_path.is_file():
                logger.info(
                    "stage=ledger region=%s action=reload decision=skip-existing path=%s",
                    region.region_id,
                    ledger_path,
                )
                bundle = load_contract_unified_hotspot_ledger(
                    contract=contract,
                    region_id=region.region_id,
                    ledger_key=args.ledger_key,
                )
            else:
                logger.info(
                    "stage=ledger region=%s action=build decision=%s path=%s",
                    region.region_id,
                    "rebuild" if ledger_path.exists() else "write",
                    ledger_path,
                )
                bundle = write_unified_hotspot_ledger(
                    contract=contract,
                    region_id=region.region_id,
                    ledger_key=args.ledger_key,
                    percentage_key=args.percentage_key,
                    classification_key=args.classification_key,
                    trend_participant_ids=trend_participant_ids,
                )
        except Exception as exc:
            _log_readiness_diagnostics(
                contract=contract,
                region_id=region.region_id,
                regions_file=args.regions_file,
                output_root=args.output_root,
                percentage_key=args.percentage_key,
                classification_key=args.classification_key,
                trend_participant_ids=trend_participant_ids,
                error=exc,
            )
            raise

        logger.info(
            "stage=ledger region=%s action=ready rows=%s families=%s path=%s",
            region.region_id,
            len(bundle.table),
            sorted(bundle.table["metric_family"].unique().tolist()),
            bundle.ledger_path,
        )

    logger.info(
        "Phase4 hotspot ledger complete: regions=%s ledger_key=%s participant_set_key=%s",
        [region.region_id for region in regions],
        args.ledger_key,
        participant_set_key,
    )
    return 0


def _log_readiness_diagnostics(
    *,
    contract,
    region_id: str,
    regions_file: str,
    output_root: Path,
    percentage_key: str,
    classification_key: str,
    trend_participant_ids: tuple[str, ...],
    error: Exception,
) -> None:
    try:
        report = write_scaleout_readiness_report(
            contract=contract,
            requested_region_ids=[region_id],
            percentage_key=percentage_key,
            classification_key=classification_key,
            trend_participant_ids=trend_participant_ids,
        )
    except Exception as diagnostic_exc:  # pragma: no cover - defensive fallback
        logger.error(
            "stage=ledger region=%s action=readiness-diagnostic-failed error=%s original_error=%s",
            region_id,
            diagnostic_exc,
            error,
        )
        return

    for row in report.rows:
        logger.error(
            "stage=ledger region=%s action=family-context metric_family=%s status=%s "
            "manifest=%s table=%s surface=%s summary=%s reason=%s",
            row.region_id,
            row.metric_family,
            row.status,
            row.manifest_path,
            row.table_path,
            row.surface_output_path,
            row.summary_output_path,
            row.reason,
        )

    logger.error(
        "stage=ledger region=%s action=failed error=%s readiness_csv=%s readiness_json=%s hint=%s",
        region_id,
        error,
        report.csv_path,
        report.json_path,
        _format_readiness_hint(
            regions_file=regions_file,
            output_root=output_root,
            region_id=region_id,
            percentage_key=percentage_key,
            classification_key=classification_key,
            trend_participant_ids=trend_participant_ids,
        ),
    )


def _format_readiness_hint(
    *,
    regions_file: str,
    output_root: Path,
    region_id: str,
    percentage_key: str,
    classification_key: str,
    trend_participant_ids: tuple[str, ...],
) -> str:
    parts = [
        "python",
        "scripts/run_phase4_scaleout_readiness.py",
        "--regions-file",
        regions_file,
        "--output-root",
        str(output_root),
        "--region",
        region_id,
        "--percentage-key",
        percentage_key,
        "--classification-key",
        classification_key,
    ]
    for dataset_id in trend_participant_ids:
        parts.extend(["--trend-dataset-id", dataset_id])
    return " ".join(shlex.quote(part) for part in parts)


if __name__ == "__main__":
    raise SystemExit(main())
