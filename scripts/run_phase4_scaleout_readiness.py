#!/usr/bin/env python3
"""Write operator-facing readiness reports for Phase 4 scale-out hotspot families."""

from __future__ import annotations

import argparse
import logging
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
from WA.comparison.scaleout_readiness import (  # noqa: E402
    DEFAULT_SCALEOUT_CLASSIFICATION_KEY,
    DEFAULT_SCALEOUT_PERCENTAGE_KEY,
    DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS,
    write_scaleout_readiness_report,
)

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect percentage, classification, and trend hotspot families for one "
            "region, --subset canonical, or --subset ten, then write a deterministic "
            "CSV/JSON readiness report with ready/missing/partial statuses and "
            "artifact paths before any wide ledger rerun."
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
        "--percentage-key",
        default=DEFAULT_SCALEOUT_PERCENTAGE_KEY,
        help="Semantic key for the percentage hotspot family (default: canonical).",
    )
    parser.add_argument(
        "--classification-key",
        default=DEFAULT_SCALEOUT_CLASSIFICATION_KEY,
        help="Semantic key for the classification hotspot family (default: canonical).",
    )
    parser.add_argument(
        "--trend-dataset-id",
        action="append",
        default=[],
        help=(
            "Trend participant dataset id. Repeat to override the default wetland set "
            f"({', '.join(DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS)})."
        ),
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
    trend_participant_ids = (
        args.trend_dataset_id
        if args.trend_dataset_id
        else list(DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS)
    )

    try:
        report = write_scaleout_readiness_report(
            contract=contract,
            subset=args.subset,
            requested_region_ids=args.region or None,
            percentage_key=args.percentage_key,
            classification_key=args.classification_key,
            trend_participant_ids=trend_participant_ids,
        )
    except Exception as exc:
        logger.error(
            "stage=scaleout-readiness action=failed subset=%s requested_regions=%s error=%s",
            args.subset or "<none>",
            args.region,
            exc,
        )
        raise

    logger.info(
        "stage=scaleout-readiness selector=%s ready_regions=%s "
        "incomplete_regions=%s csv=%s json=%s",
        report.selector_label,
        list(report.ready_region_ids),
        list(report.incomplete_region_ids),
        report.csv_path,
        report.json_path,
    )
    for row in report.rows:
        logger.info(
            "stage=scaleout-readiness region=%s metric_family=%s family_key=%s status=%s "
            "manifest=%s table=%s surface=%s summary=%s reason=%s",
            row.region_id,
            row.metric_family,
            row.family_key,
            row.status,
            row.manifest_path,
            row.table_path,
            row.surface_output_path,
            row.summary_output_path,
            row.reason,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
