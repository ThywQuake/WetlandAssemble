"""Shared Phase 4 evidence-contract regions, artifact semantics, and JSON-safe metadata.

This module is the contract anchor for Milestone M002. It owns:
- the fixed ten-region catalog sourced from ``config/priority_regions.yaml``
- the hydro-diverse canonical subset ordering
- strict artifact-family semantics and relpath construction
- JSON-safe metadata coercion used by contract writers
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import yaml

from WA.loaders.base import BBox

ArtifactKind = Literal[
    "surface",
    "regional_summary",
    "hotspot_manifest",
    "trend_surface",
    "trend_regional_summary",
    "trend_agreement_surface",
    "trend_agreement_summary",
    "classification_surface",
    "classification_regional_summary",
    "classification_hotspot_manifest",
    "trend_hotspot_manifest",
    "unified_hotspot_ledger",
]

DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT = Path("results/phase4")
DEFAULT_PHASE4_REGIONS_FILE = Path("config/priority_regions.yaml")
DEFAULT_CANONICAL_REGION_IDS = (
    "amazon",
    "pantanal",
    "sudd",
    "borneo",
)
SUPPORTED_PHASE4_REGION_SUBSETS = ("canonical", "ten")

_REQUIRED_REGION_FIELDS = {"label", "label_zh", "kind", "priority", "bbox"}
_ALLOWED_REGION_FIELDS = {
    "label",
    "label_zh",
    "kind",
    "priority",
    "continent",
    "representative_countries",
    "representative_wetland_systems",
    "representative_wetland_systems_zh",
    "bbox",
    "rationale",
    "rationale_zh",
    "short_intro",
    "short_intro_zh",
    "source_urls",
}
_ALLOWED_TOP_LEVEL_FIELDS = {
    "generated_at",
    "purpose",
    "bbox_convention",
    "bbox_type",
    "bbox_note",
    "region_kind_note",
    "regions",
}
_REQUIRED_ARTIFACT_KINDS: set[str] = {
    "surface",
    "regional_summary",
    "hotspot_manifest",
    "trend_surface",
    "trend_regional_summary",
    "trend_agreement_surface",
    "trend_agreement_summary",
    "classification_surface",
    "classification_regional_summary",
    "classification_hotspot_manifest",
    "trend_hotspot_manifest",
    "unified_hotspot_ledger",
}


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"Duplicate YAML key detected: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class ContractRegion:
    """One strict evidence-contract region definition."""

    region_id: str
    label: str
    label_zh: str
    kind: str
    priority: int
    bbox: BBox
    is_canonical: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArtifactSemantics:
    """Stable output-family semantics for one artifact kind."""

    family_dir: str
    stem_suffix: str
    default_extension: str


@dataclass(frozen=True)
class EvidenceContract:
    """Shared region + artifact contract for Phase 4 evidence outputs."""

    output_root: Path
    regions_file: Path
    canonical_region_ids: tuple[str, ...]
    regions: tuple[ContractRegion, ...]
    artifact_semantics: Mapping[ArtifactKind, ArtifactSemantics]

    def __post_init__(self) -> None:
        missing = sorted(_REQUIRED_ARTIFACT_KINDS - set(self.artifact_semantics.keys()))
        if missing:
            raise ValueError(
                "Missing required artifact semantics: " + ", ".join(missing)
            )

        region_ids = [region.region_id for region in self.regions]
        duplicates = sorted(
            {region_id for region_id in region_ids if region_ids.count(region_id) > 1}
        )
        if duplicates:
            raise ValueError(
                "Duplicate region ids in evidence contract: " + ", ".join(duplicates)
            )

        if not self.canonical_region_ids:
            raise ValueError("canonical_region_ids must not be empty")
        if len(set(self.canonical_region_ids)) != len(self.canonical_region_ids):
            raise ValueError("canonical_region_ids must not contain duplicates")

        unknown_canonical = sorted(set(self.canonical_region_ids) - set(region_ids))
        if unknown_canonical:
            raise ValueError(
                "Canonical subset contains unknown region ids: "
                + ", ".join(unknown_canonical)
            )

    @property
    def regions_by_id(self) -> dict[str, ContractRegion]:
        return {region.region_id: region for region in self.regions}

    @property
    def ordered_ten_region_ids(self) -> tuple[str, ...]:
        """Return the fixed ordered ten-region contract subset."""

        return tuple(region.region_id for region in self.regions)

    def resolve_subset_region_ids(self, subset: str) -> list[str]:
        """Resolve one named evidence-contract subset to ordered region ids."""

        normalized = subset.strip().lower()
        if normalized == "canonical":
            return list(self.canonical_region_ids)
        if normalized == "ten":
            return list(self.ordered_ten_region_ids)
        supported = ", ".join(repr(name) for name in SUPPORTED_PHASE4_REGION_SUBSETS)
        raise ValueError(f"Unknown subset {subset!r}; supported subsets: {supported}")

    def resolve_regions(
        self,
        *,
        subset: str | None = None,
        requested_region_ids: Iterable[str] | None = None,
    ) -> list[ContractRegion]:
        """Resolve selected regions from ``--subset`` or explicit ids."""

        if subset is not None and requested_region_ids is not None:
            raise ValueError(
                "Ambiguous region selector: pass either subset or requested_region_ids, not both"
            )

        if subset is None and requested_region_ids is None:
            region_ids = list(self.canonical_region_ids)
        elif subset is not None:
            region_ids = self.resolve_subset_region_ids(subset)
        else:
            flattened: list[str] = []
            assert requested_region_ids is not None
            for entry in requested_region_ids:
                flattened.extend(
                    part.strip() for part in str(entry).split(",") if part.strip()
                )
            if not flattened:
                raise ValueError(
                    "At least one region id is required when subset is omitted"
                )
            duplicates = sorted(
                {region_id for region_id in flattened if flattened.count(region_id) > 1}
            )
            if duplicates:
                raise ValueError(
                    "Duplicate region ids requested: " + ", ".join(duplicates)
                )
            known = set(self.regions_by_id.keys())
            unknown = sorted(set(flattened) - known)
            if unknown:
                raise KeyError(f"Unknown region ids: {', '.join(unknown)}")
            region_ids = flattened

        return [self.regions_by_id[region_id] for region_id in region_ids]

    def resolve_region_ids(
        self,
        *,
        subset: str | None = None,
        requested_region_ids: Iterable[str] | None = None,
    ) -> list[str]:
        return [
            region.region_id
            for region in self.resolve_regions(
                subset=subset,
                requested_region_ids=requested_region_ids,
            )
        ]

    def region_bboxes(
        self,
        *,
        subset: str | None = None,
        requested_region_ids: Iterable[str] | None = None,
    ) -> dict[str, BBox]:
        return {
            region.region_id: region.bbox
            for region in self.resolve_regions(
                subset=subset,
                requested_region_ids=requested_region_ids,
            )
        }

    def semantics_for(self, kind: ArtifactKind) -> ArtifactSemantics:
        try:
            return self.artifact_semantics[kind]
        except KeyError as exc:
            raise KeyError(f"Unknown artifact kind: {kind!r}") from exc

    def artifact_relpath(
        self,
        *,
        kind: ArtifactKind,
        dataset_or_key: str,
        region_id: str,
        extension: str | None = None,
    ) -> Path:
        semantics = self.semantics_for(kind)
        ext = extension or semantics.default_extension
        ext = ext if ext.startswith(".") else f".{ext}"
        stem = build_artifact_stem(
            dataset_or_key=dataset_or_key,
            region_id=region_id,
            suffix=semantics.stem_suffix,
        )
        return Path(semantics.family_dir) / region_id / f"{stem}{ext}"

    def artifact_output_path(
        self,
        *,
        kind: ArtifactKind,
        dataset_or_key: str,
        region_id: str,
        extension: str | None = None,
    ) -> Path:
        return self.output_root / self.artifact_relpath(
            kind=kind,
            dataset_or_key=dataset_or_key,
            region_id=region_id,
            extension=extension,
        )

    def require_output_root(self) -> Path:
        if not self.output_root.exists():
            raise FileNotFoundError(
                f"Evidence-contract output_root does not exist: {self.output_root}"
            )
        if not self.output_root.is_dir():
            raise NotADirectoryError(
                f"Evidence-contract output_root is not a directory: {self.output_root}"
            )
        return self.output_root


def default_artifact_semantics() -> dict[ArtifactKind, ArtifactSemantics]:
    """Return the hard-coded artifact-family contract."""

    return {
        "surface": ArtifactSemantics("surfaces", "surface", ".nc"),
        "regional_summary": ArtifactSemantics(
            "regional_summaries",
            "regional_summary",
            ".csv",
        ),
        "hotspot_manifest": ArtifactSemantics(
            "hotspot_manifests",
            "hotspot_manifest",
            ".json",
        ),
        "trend_surface": ArtifactSemantics(
            "trend_surfaces",
            "trend_surface",
            ".nc",
        ),
        "trend_regional_summary": ArtifactSemantics(
            "trend_regional_summaries",
            "trend_regional_summary",
            ".csv",
        ),
        "trend_agreement_surface": ArtifactSemantics(
            "trend_agreement_surfaces",
            "trend_agreement_surface",
            ".nc",
        ),
        "trend_agreement_summary": ArtifactSemantics(
            "trend_agreement_summaries",
            "trend_agreement_summary",
            ".csv",
        ),
        "classification_surface": ArtifactSemantics(
            "classification_surfaces",
            "classification_surface",
            ".nc",
        ),
        "classification_regional_summary": ArtifactSemantics(
            "classification_regional_summaries",
            "classification_regional_summary",
            ".csv",
        ),
        "classification_hotspot_manifest": ArtifactSemantics(
            "classification_hotspot_manifests",
            "classification_hotspot_manifest",
            ".json",
        ),
        "trend_hotspot_manifest": ArtifactSemantics(
            "trend_hotspot_manifests",
            "trend_hotspot_manifest",
            ".json",
        ),
        "unified_hotspot_ledger": ArtifactSemantics(
            "unified_hotspot_ledgers",
            "unified_hotspot_ledger",
            ".csv",
        ),
    }


def load_phase4_evidence_contract(
    *,
    output_root: str | Path = DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    regions_file: str | Path = DEFAULT_PHASE4_REGIONS_FILE,
    canonical_region_ids: Iterable[str] = DEFAULT_CANONICAL_REGION_IDS,
    artifact_semantics: Mapping[ArtifactKind, ArtifactSemantics] | None = None,
) -> EvidenceContract:
    """Load the shared Phase 4 evidence contract from config + defaults."""

    regions_path = Path(regions_file)
    document = _load_regions_document(regions_path)
    payload_regions = document.get("regions")
    if not isinstance(payload_regions, dict):
        raise ValueError(
            "priority region document must contain a top-level 'regions' mapping"
        )

    ordered_regions: list[ContractRegion] = []
    canonical_set = tuple(str(region_id) for region_id in canonical_region_ids)
    for region_id, payload in sorted(
        payload_regions.items(),
        key=lambda item: (int(item[1].get("priority", 9999)), str(item[0])),
    ):
        if not isinstance(payload, dict):
            raise ValueError(f"Region {region_id!r} must be a mapping")
        _validate_region_payload(str(region_id), payload)
        ordered_regions.append(
            ContractRegion(
                region_id=str(region_id),
                label=str(payload["label"]),
                label_zh=str(payload["label_zh"]),
                kind=str(payload["kind"]),
                priority=int(payload["priority"]),
                bbox=_coerce_bbox(payload["bbox"]),
                is_canonical=str(region_id) in canonical_set,
                metadata=dict(payload),
            )
        )

    return EvidenceContract(
        output_root=Path(output_root),
        regions_file=regions_path,
        canonical_region_ids=canonical_set,
        regions=tuple(ordered_regions),
        artifact_semantics=dict(artifact_semantics or default_artifact_semantics()),
    )


def validate_stem_token(token: str, *, label: str = "token") -> str:
    """Normalize and validate one dataset/participant token used in stems."""

    normalized = str(token).strip()
    if not normalized:
        raise ValueError(f"{label} must not be empty")
    if "__" in normalized:
        raise ValueError(
            f"{label} must not contain '__'; that separator is reserved by the evidence contract"
        )
    if "/" in normalized or "\\" in normalized:
        raise ValueError(f"{label} must not contain path separators")
    return normalized


def build_artifact_stem(*, dataset_or_key: str, region_id: str, suffix: str) -> str:
    """Build one contract-stable artifact stem."""

    dataset_slot = validate_stem_token(dataset_or_key, label="dataset_or_key")
    region_slot = validate_stem_token(region_id, label="region_id")
    suffix_slot = validate_stem_token(suffix, label="suffix")
    return f"{dataset_slot}__{region_slot}__{suffix_slot}"


def json_safe_value(value: Any) -> Any:
    """Recursively coerce metadata to a JSON-safe form.

    Raises
    ------
    TypeError | ValueError
        If a value cannot be serialized safely or contains non-finite floats.
    """

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Metadata float must be finite, got {value!r}")
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return json_safe_value(value.item())
    if isinstance(value, np.ndarray):
        return [json_safe_value(item) for item in value.tolist()]
    if isinstance(value, tuple):
        return [json_safe_value(item) for item in value]
    if isinstance(value, list):
        return [json_safe_value(item) for item in value]
    if isinstance(value, set):
        return [json_safe_value(item) for item in sorted(value, key=repr)]
    if isinstance(value, Mapping):
        return {
            str(key): json_safe_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    raise TypeError(f"Metadata value is not JSON-safe: {value!r}")


def metadata_json(value: Mapping[str, Any]) -> str:
    """Return a stable JSON string for contract metadata."""

    return json.dumps(json_safe_value(value), sort_keys=True, allow_nan=False)


def _load_regions_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    document = yaml.load(text, Loader=_UniqueKeySafeLoader) or {}
    if not isinstance(document, dict):
        raise ValueError("priority region document must deserialize to a mapping")
    unknown = sorted(set(document.keys()) - _ALLOWED_TOP_LEVEL_FIELDS)
    if unknown:
        raise ValueError(
            "Unknown top-level keys in priority region document: " + ", ".join(unknown)
        )
    return document


def _validate_region_payload(region_id: str, payload: Mapping[str, Any]) -> None:
    missing = sorted(_REQUIRED_REGION_FIELDS - set(payload.keys()))
    if missing:
        raise ValueError(
            f"Region {region_id!r} is missing required fields: {', '.join(missing)}"
        )
    unknown = sorted(set(payload.keys()) - _ALLOWED_REGION_FIELDS)
    if unknown:
        raise ValueError(
            f"Region {region_id!r} contains unknown fields: {', '.join(unknown)}"
        )
    _coerce_bbox(payload.get("bbox"))


def _coerce_bbox(value: Any) -> BBox:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"Expected bbox as a 4-item list, got {value!r}")
    west, south, east, north = (float(item) for item in value)
    return (west, south, east, north)
