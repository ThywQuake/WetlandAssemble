#!/usr/bin/env python3
"""Build a derived Phase 4 paper-facing evidence pack from contract artifacts."""

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
)
from WA.comparison.trend_hotspots import (  # noqa: E402
    build_participant_set_key,
    normalize_participant_ids,
)
from WA.visualization.phase4_pack import (  # noqa: E402
    DEFAULT_PHASE4_PACK_OUTPUT_ROOT,
    build_phase4_evidence_pack_proof,
)

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a derived Phase 4 paper-facing evidence pack from semantic reloads "
            "alone. The pack claim surface now writes strict readiness + ledger "
            "proof artifacts before it can report a complete pack. The derived pack "
            "still reopens contract-backed percentage/classification/trend/ledger "
            "artifacts, writes percentage interannual + climatology figures, one "
            "joined regional evidence table, one unified hotspot table, one narrative "
            "summary, and one deterministic manifest under a pack root that must stay "
            "outside results/phase4."
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
        "--phase4-output-root",
        type=Path,
        default=DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
        help="Science contract root to reopen semantically (default: results/phase4).",
    )
    parser.add_argument(
        "--pack-output-root",
        type=Path,
        default=DEFAULT_PHASE4_PACK_OUTPUT_ROOT,
        help=(
            "Derived pack root for figures/tables/summary/manifest. Must stay outside "
            "results/phase4 (default: results/figures/phase4_pack)."
        ),
    )
    parser.add_argument(
        "--percentage-key",
        default=DEFAULT_SCALEOUT_PERCENTAGE_KEY,
        help="Semantic key for the percentage family (default: canonical).",
    )
    parser.add_argument(
        "--classification-key",
        default=DEFAULT_SCALEOUT_CLASSIFICATION_KEY,
        help="Semantic key for the classification family (default: canonical).",
    )
    parser.add_argument(
        "--ledger-key",
        default="canonical",
        help="Semantic key for the unified hotspot ledger family (default: canonical).",
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
        "--strict",
        action="store_true",
        help=(
            "Fail closed unless readiness rows are all ready, every requested unified "
            "ledger reopens cleanly, selector keys match, and the pack writes a fresh "
            "manifest. Without --strict, the CLI still writes explicit incomplete-proof "
            "artifacts but returns success so operators can inspect gaps before the "
            "final rerun."
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
        output_root=args.phase4_output_root,
        regions_file=args.regions_file,
    )
    participant_ids = normalize_participant_ids(
        args.trend_dataset_id
        if args.trend_dataset_id
        else DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS
    )
    participant_set_key = build_participant_set_key(participant_ids)
    try:
        regions = contract.resolve_regions(
            subset=args.subset,
            requested_region_ids=args.region or None,
        )
    except Exception as exc:
        logger.error(
            "stage=pack selector=resolve subset=%s requested_regions=%s "
            "participant_set_key=%s error=%s",
            args.subset or "<none>",
            args.region,
            participant_set_key,
            exc,
        )
        return 1

    selector_label = args.subset or (
        "explicit-region-list" if args.region else "canonical"
    )
    logger.info(
        "stage=pack selector=%s strict=%s participant_set_key=%s region_ids=%s",
        selector_label,
        args.strict,
        participant_set_key,
        [region.region_id for region in regions],
    )

    try:
        proof = build_phase4_evidence_pack_proof(
            phase4_output_root=args.phase4_output_root,
            pack_output_root=args.pack_output_root,
            regions_file=args.regions_file,
            subset=args.subset,
            requested_region_ids=args.region or None,
            percentage_key=args.percentage_key,
            classification_key=args.classification_key,
            ledger_key=args.ledger_key,
            trend_participant_ids=participant_ids,
        )
    except Exception as exc:
        logger.error(
            "stage=pack-proof action=failed strict=%s selector=%s participant_set_key=%s "
            "error=%s",
            args.strict,
            selector_label,
            participant_set_key,
            exc,
        )
        return 1

    if proof.pack_build_error is not None:
        logger.error(
            "stage=pack-proof action=build-error strict=%s verdict=%s proof_json=%s "
            "proof_markdown=%s error=%s",
            args.strict,
            proof.proof_verdict,
            proof.proof_json_path,
            proof.proof_markdown_path,
            proof.pack_build_error,
        )
        return 1

    if proof.proof_verdict != "complete":
        log = logger.error if args.strict else logger.warning
        log(
            "stage=pack-proof action=incomplete strict=%s proof_json=%s proof_markdown=%s "
            "manifest=%s blocking_reasons=%s",
            args.strict,
            proof.proof_json_path,
            proof.proof_markdown_path,
            proof.manifest_path,
            list(proof.blocking_reasons),
        )
        return 2 if args.strict else 0

    assert proof.pack_result is not None  # pragma: no cover - guarded by verdict
    logger.info(
        "stage=pack-proof action=complete strict=%s regions=%s manifest=%s summary=%s "
        "joined_table=%s hotspot_table=%s proof_json=%s proof_markdown=%s",
        args.strict,
        list(proof.resolved_region_ids),
        proof.pack_result.manifest_path,
        proof.pack_result.summary_path,
        proof.pack_result.joined_regional_evidence_path,
        proof.pack_result.unified_hotspot_table_path,
        proof.proof_json_path,
        proof.proof_markdown_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
