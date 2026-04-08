from __future__ import annotations

from pathlib import Path

import pytest

from WA.comparison.evidence_contract import (
    EvidenceContract,
    default_artifact_semantics,
    load_phase4_evidence_contract,
)

EXPECTED_TEN_REGION_IDS = [
    "amazon",
    "orinoco",
    "pantanal",
    "indogangetic",
    "mekong",
    "sudd",
    "congo",
    "okavango",
    "borneo",
    "northernaus",
]


def test_default_artifact_semantics_include_trend_hotspot_and_unified_ledger() -> None:
    semantics = default_artifact_semantics()

    assert semantics["trend_hotspot_manifest"].family_dir == "trend_hotspot_manifests"
    assert semantics["trend_hotspot_manifest"].stem_suffix == "trend_hotspot_manifest"
    assert semantics["trend_hotspot_manifest"].default_extension == ".json"
    assert semantics["unified_hotspot_ledger"].family_dir == "unified_hotspot_ledgers"
    assert semantics["unified_hotspot_ledger"].stem_suffix == "unified_hotspot_ledger"
    assert semantics["unified_hotspot_ledger"].default_extension == ".csv"


def test_evidence_contract_requires_new_artifact_families() -> None:
    semantics = default_artifact_semantics()
    del semantics["trend_hotspot_manifest"]
    del semantics["unified_hotspot_ledger"]

    regions = load_phase4_evidence_contract().regions
    with pytest.raises(ValueError, match="trend_hotspot_manifest"):
        EvidenceContract(
            output_root=Path("results/phase4"),
            regions_file=Path("config/priority_regions.yaml"),
            canonical_region_ids=("amazon",),
            regions=regions,
            artifact_semantics=semantics,
        )


def test_artifact_relpath_locks_new_family_stems() -> None:
    contract = load_phase4_evidence_contract(output_root=Path("results/phase4"))

    hotspot_relpath = contract.artifact_relpath(
        kind="trend_hotspot_manifest",
        dataset_or_key="gwd30+swamps+wad2m",
        region_id="amazon",
    )
    ledger_relpath = contract.artifact_relpath(
        kind="unified_hotspot_ledger",
        dataset_or_key="canonical",
        region_id="amazon",
    )

    assert hotspot_relpath == Path(
        "trend_hotspot_manifests/amazon/"
        "gwd30+swamps+wad2m__amazon__trend_hotspot_manifest.json"
    )
    assert ledger_relpath == Path(
        "unified_hotspot_ledgers/amazon/canonical__amazon__unified_hotspot_ledger.csv"
    )


def test_resolve_regions_pins_canonical_and_ten_ordering() -> None:
    contract = load_phase4_evidence_contract(output_root=Path("results/phase4"))

    assert contract.resolve_region_ids(subset="canonical") == [
        "amazon",
        "pantanal",
        "sudd",
        "borneo",
    ]
    assert contract.resolve_region_ids(subset="ten") == EXPECTED_TEN_REGION_IDS
    assert contract.resolve_regions(subset="ten")[0].region_id == "amazon"
    assert contract.resolve_regions(subset="ten")[-1].region_id == "northernaus"


def test_resolve_regions_rejects_unknown_subset() -> None:
    contract = load_phase4_evidence_contract(output_root=Path("results/phase4"))

    with pytest.raises(ValueError, match="supported subsets"):
        contract.resolve_regions(subset="macro")


def test_resolve_regions_rejects_ambiguous_and_duplicate_requests() -> None:
    contract = load_phase4_evidence_contract(output_root=Path("results/phase4"))

    with pytest.raises(ValueError, match="Ambiguous region selector"):
        contract.resolve_regions(subset="ten", requested_region_ids=["amazon"])

    with pytest.raises(ValueError, match="Duplicate region ids requested"):
        contract.resolve_regions(requested_region_ids=["amazon", "amazon"])
