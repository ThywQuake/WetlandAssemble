#!/usr/bin/env python3
"""Build or reopen contract-backed unified Phase 4 hotspot ledgers."""

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
    load_phase4_evidence_contract,
)
from WA.comparison.hotspot_ledger import (  # noqa: E402
    load_contract_unified_hotspot_ledger,
    unified_hotspot_ledger_output_path,
    write_unified_hotspot_ledger,
)
from WA.comparison.trend_hotspots import (  # noqa: E402
    build_participant_set_key,
    normalize_participant_ids,
)

logger = logging.getLogger(__name__)

DEFAULT_TREND_PARTICIPANT_IDS = (
    "gwd30",
    "giems_mc",
    "topmodel",
    "swamps",
    "wad2m",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or reload one contract-backed unified hotspot ledger from the "
            "percentage, classification, and trend hotspot families. The ledger stage "
            "fails closed when any family is missing or malformed."
        )
    )
    parser.add_argument("--regions-file", default=str(DEFAULT_PHASE4_REGIONS_FILE))
    parser.add_argument(
        "--subset",
        default="canonical",
        help="Region subset from the evidence contract (default: canonical).",
    )
    parser.add_argument(
        "--region",
        action="append",
        default=[],
        help="Explicit region id override; may be repeated.",
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
    regions = contract.resolve_regions(
        subset=None if args.region else args.subset,
        requested_region_ids=args.region or None,
    )

    logger.info(
        "Phase4 hotspot ledger start: regions=%s ledger_key=%s percentage_key=%s "
        "classification_key=%s participant_set_key=%s",
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


if __name__ == "__main__":
    raise SystemExit(main())
