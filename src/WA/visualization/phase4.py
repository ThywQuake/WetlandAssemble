"""Visualization helpers for Phase 4 regional time-series figures."""

from __future__ import annotations

import calendar
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from WA.comparison.classification_contract import (
    ClassificationHotspotReload,
    ClassificationSummaryBundle,
    load_contract_classification_hotspot_table,
    load_contract_classification_summary,
)
from WA.comparison.evidence_contract import (
    DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    DEFAULT_PHASE4_REGIONS_FILE,
    load_phase4_evidence_contract,
)
from WA.comparison.hotspot_ledger import (
    UnifiedHotspotLedgerReload,
    load_contract_unified_hotspot_ledger,
)
from WA.comparison.percentage_backbone import (
    PercentageSummaryBundle,
    PercentageSurfaceBundle,
    load_contract_percentage_summary,
    load_contract_percentage_surface,
)
from WA.comparison.trend_contract import (
    TrendAgreementSummaryBundle,
    TrendAgreementSurfaceBundle,
    load_contract_trend_agreement_summary,
    load_contract_trend_agreement_surface,
)
from WA.comparison.trend_hotspots import (
    TrendHotspotReload,
    load_contract_trend_hotspot_table,
)

PHASE4_DATASET_ORDER = (
    "gwd30",
    "giems_mc",
    "topmodel",
    "swamps",
    "wad2m",
    "berkeley_rwawc",
)

PHASE4_DATASET_LABELS = {
    "gwd30": "GWD30",
    "giems_mc": "GIEMS-MC",
    "topmodel": "TOPMODEL",
    "swamps": "SWAMPS",
    "wad2m": "WAD2M",
    "berkeley_rwawc": "Berkeley-RWAWC (watermask)",
}

PHASE4_DATASET_COLORS = {
    "gwd30": "#0f4c5c",
    "giems_mc": "#2b9348",
    "topmodel": "#b26b2c",
    "swamps": "#6a4c93",
    "wad2m": "#c44536",
    "berkeley_rwawc": "#808080",
}

PHASE4_DATASET_LINESTYLES = {
    "gwd30": "-",
    "giems_mc": "-",
    "topmodel": "-",
    "swamps": "-",
    "wad2m": "-",
    "berkeley_rwawc": "--",
}

PHASE4_DATASET_LINEWIDTHS = {
    "gwd30": 2.1,
    "giems_mc": 1.9,
    "topmodel": 1.9,
    "swamps": 1.9,
    "wad2m": 1.9,
    "berkeley_rwawc": 1.4,
}


def phase4_interannual_figure_path(
    *,
    figures_root: str | Path,
    region_id: str,
) -> Path:
    """Return the interannual figure path for one region."""

    return Path(figures_root) / "interannual" / f"{region_id}.png"


def phase4_climatology_figure_path(
    *,
    figures_root: str | Path,
    region_id: str,
) -> Path:
    """Return the climatology figure path for one region."""

    return Path(figures_root) / "climatology" / f"{region_id}.png"


def load_phase4_contract_percentage_summary(
    *,
    region_id: str,
    dataset_key: str = "canonical",
    output_root: str | Path = DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    regions_file: str | Path = DEFAULT_PHASE4_REGIONS_FILE,
) -> PercentageSummaryBundle:
    """Reload one contract-backed percentage summary by semantics."""

    contract = load_phase4_evidence_contract(
        output_root=output_root,
        regions_file=regions_file,
    )
    try:
        return load_contract_percentage_summary(
            contract=contract,
            region_id=region_id,
            dataset_key=dataset_key,
        )
    except Exception as exc:  # pragma: no cover - exercised by tests via message
        raise ValueError(
            "Phase4 semantic reload failed for percentage summary: "
            f"region_id={region_id} dataset_key={dataset_key} error={exc}"
        ) from exc


def load_phase4_contract_percentage_surface(
    *,
    region_id: str,
    dataset_key: str = "canonical",
    output_root: str | Path = DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    regions_file: str | Path = DEFAULT_PHASE4_REGIONS_FILE,
) -> PercentageSurfaceBundle:
    """Reload one contract-backed percentage surface by semantics."""

    contract = load_phase4_evidence_contract(
        output_root=output_root,
        regions_file=regions_file,
    )
    try:
        return load_contract_percentage_surface(
            contract=contract,
            region_id=region_id,
            dataset_key=dataset_key,
        )
    except Exception as exc:  # pragma: no cover - exercised by tests via message
        raise ValueError(
            "Phase4 semantic reload failed for percentage surface: "
            f"region_id={region_id} dataset_key={dataset_key} error={exc}"
        ) from exc


def load_phase4_contract_trend_agreement_summary(
    *,
    region_id: str,
    participant_ids: list[str] | tuple[str, ...],
    output_root: str | Path = DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    regions_file: str | Path = DEFAULT_PHASE4_REGIONS_FILE,
) -> TrendAgreementSummaryBundle:
    """Reload one contract-backed trend agreement summary by semantics."""

    contract = load_phase4_evidence_contract(
        output_root=output_root,
        regions_file=regions_file,
    )
    try:
        return load_contract_trend_agreement_summary(
            contract=contract,
            region_id=region_id,
            participant_ids=participant_ids,
        )
    except Exception as exc:  # pragma: no cover - exercised by tests via message
        raise ValueError(
            "Phase4 semantic reload failed for trend agreement summary: "
            f"region_id={region_id} participant_ids={list(participant_ids)} error={exc}"
        ) from exc


def load_phase4_contract_trend_agreement_surface(
    *,
    region_id: str,
    participant_ids: list[str] | tuple[str, ...],
    output_root: str | Path = DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    regions_file: str | Path = DEFAULT_PHASE4_REGIONS_FILE,
) -> TrendAgreementSurfaceBundle:
    """Reload one contract-backed trend agreement surface by semantics."""

    contract = load_phase4_evidence_contract(
        output_root=output_root,
        regions_file=regions_file,
    )
    try:
        return load_contract_trend_agreement_surface(
            contract=contract,
            region_id=region_id,
            participant_ids=participant_ids,
        )
    except Exception as exc:  # pragma: no cover - exercised by tests via message
        raise ValueError(
            "Phase4 semantic reload failed for trend agreement surface: "
            f"region_id={region_id} participant_ids={list(participant_ids)} error={exc}"
        ) from exc


def load_phase4_contract_classification_summary(
    *,
    region_id: str,
    dataset_key: str = "canonical",
    output_root: str | Path = DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    regions_file: str | Path = DEFAULT_PHASE4_REGIONS_FILE,
) -> ClassificationSummaryBundle:
    """Reload one contract-backed classification summary by semantics."""

    contract = load_phase4_evidence_contract(
        output_root=output_root,
        regions_file=regions_file,
    )
    try:
        return load_contract_classification_summary(
            contract=contract,
            region_id=region_id,
            dataset_key=dataset_key,
        )
    except Exception as exc:  # pragma: no cover - exercised by tests via message
        raise ValueError(
            "Phase4 semantic reload failed for classification summary: "
            f"region_id={region_id} dataset_key={dataset_key} error={exc}"
        ) from exc


def load_phase4_contract_classification_hotspot_table(
    *,
    region_id: str,
    dataset_key: str = "canonical",
    output_root: str | Path = DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    regions_file: str | Path = DEFAULT_PHASE4_REGIONS_FILE,
) -> ClassificationHotspotReload:
    """Reload one contract-backed classification hotspot JSON/CSV pair."""

    contract = load_phase4_evidence_contract(
        output_root=output_root,
        regions_file=regions_file,
    )
    try:
        return load_contract_classification_hotspot_table(
            contract=contract,
            region_id=region_id,
            dataset_key=dataset_key,
        )
    except Exception as exc:  # pragma: no cover - exercised by tests via message
        raise ValueError(
            "Phase4 semantic reload failed for classification hotspot table: "
            f"region_id={region_id} dataset_key={dataset_key} error={exc}"
        ) from exc


def load_phase4_unified_hotspot_ledger(
    *,
    region_id: str,
    ledger_key: str = "canonical",
    output_root: str | Path = DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    regions_file: str | Path = DEFAULT_PHASE4_REGIONS_FILE,
) -> UnifiedHotspotLedgerReload:
    """Reload one contract-backed unified hotspot ledger by semantics."""

    contract = load_phase4_evidence_contract(
        output_root=output_root,
        regions_file=regions_file,
    )
    try:
        return load_contract_unified_hotspot_ledger(
            contract=contract,
            region_id=region_id,
            ledger_key=ledger_key,
        )
    except Exception as exc:  # pragma: no cover - exercised by tests via message
        raise ValueError(
            "Phase4 semantic reload failed for unified hotspot ledger: "
            f"region_id={region_id} ledger_key={ledger_key} error={exc}"
        ) from exc


def load_phase4_contract_trend_hotspot_table(
    *,
    region_id: str,
    participant_ids: list[str] | tuple[str, ...],
    output_root: str | Path = DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    regions_file: str | Path = DEFAULT_PHASE4_REGIONS_FILE,
) -> TrendHotspotReload:
    """Reload one contract-backed trend hotspot JSON/CSV pair by semantics."""

    contract = load_phase4_evidence_contract(
        output_root=output_root,
        regions_file=regions_file,
    )
    try:
        return load_contract_trend_hotspot_table(
            contract=contract,
            region_id=region_id,
            participant_ids=participant_ids,
        )
    except Exception as exc:  # pragma: no cover - exercised by tests via message
        raise ValueError(
            "Phase4 semantic reload failed for trend hotspot table: "
            f"region_id={region_id} participant_ids={list(participant_ids)} error={exc}"
        ) from exc


def plot_phase4_interannual(
    table: pd.DataFrame,
    *,
    region_label: str,
    output_path: Path,
    start_year: int = 1990,
    end_year: int = 2020,
    dpi: int = 180,
) -> Path:
    """Plot one 1990-2020 regional interannual comparison figure."""

    annual = table.loc[table["series_type"] == "annual"].copy()
    year_index = pd.Index(range(start_year, end_year + 1), name="year")

    fig, ax = plt.subplots(figsize=(11.5, 6.4))
    try:
        for dataset_id in PHASE4_DATASET_ORDER:
            subset = annual.loc[annual["dataset_id"] == dataset_id]
            if subset.empty:
                values = pd.Series(np.nan, index=year_index, dtype=np.float64)
            else:
                values = (
                    subset.set_index(subset["year"].astype(int))["wetland_percentage"]
                    .sort_index()
                    .reindex(year_index)
                )
            ax.plot(
                year_index.to_numpy(dtype=int),
                values.to_numpy(dtype=np.float64),
                color=PHASE4_DATASET_COLORS[dataset_id],
                linestyle=PHASE4_DATASET_LINESTYLES[dataset_id],
                linewidth=PHASE4_DATASET_LINEWIDTHS[dataset_id],
                label=PHASE4_DATASET_LABELS[dataset_id],
            )

        ax.set_xlim(start_year, end_year)
        ax.set_xticks(np.arange(start_year, end_year + 1, 5))
        ax.set_ylabel("Area-weighted fractional coverage (%)")
        ax.set_xlabel("Year")
        ax.set_title(f"{region_label} | 1990-2020 Interannual")
        ax.grid(True, alpha=0.25, linewidth=0.8)
        ax.legend(frameon=False, ncol=2)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)
    return output_path


def plot_phase4_climatology(
    table: pd.DataFrame,
    *,
    region_label: str,
    output_path: Path,
    dpi: int = 180,
) -> Path:
    """Plot one 12-month regional climatology comparison figure."""

    climatology = table.loc[table["series_type"] == "climatology"].copy()
    month_index = pd.Index(range(1, 13), name="month")

    fig, ax = plt.subplots(figsize=(11.5, 6.4))
    try:
        for dataset_id in PHASE4_DATASET_ORDER:
            subset = climatology.loc[climatology["dataset_id"] == dataset_id]
            if subset.empty:
                values = pd.Series(np.nan, index=month_index, dtype=np.float64)
            else:
                values = (
                    subset.set_index(subset["month"].astype(int))["wetland_percentage"]
                    .sort_index()
                    .reindex(month_index)
                )
            ax.plot(
                month_index.to_numpy(dtype=int),
                values.to_numpy(dtype=np.float64),
                color=PHASE4_DATASET_COLORS[dataset_id],
                linestyle=PHASE4_DATASET_LINESTYLES[dataset_id],
                linewidth=PHASE4_DATASET_LINEWIDTHS[dataset_id],
                label=PHASE4_DATASET_LABELS[dataset_id],
            )

        ax.set_xlim(1, 12)
        ax.set_xticks(np.arange(1, 13))
        ax.set_xticklabels([calendar.month_abbr[month] for month in month_index])
        ax.set_ylabel("Area-weighted fractional coverage (%)")
        ax.set_xlabel("Month")
        ax.set_title(f"{region_label} | Multi-year Monthly Climatology")
        ax.grid(True, alpha=0.25, linewidth=0.8)
        ax.legend(frameon=False, ncol=2)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)
    return output_path
