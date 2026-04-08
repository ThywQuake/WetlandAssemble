# M002/S03 — Research

**Date:** 2026-04-08

## Summary

This slice primarily owns **R103** (500m unified-8-class classification disagreement outputs) and directly supports **R101 / R105 / R106 / R107** by putting the classification line onto the same contract surface already established for percentage and trend. The scientific backbone already exists: `src/WA/comparison/phase36.py` computes the global 500m disagreement products with cache-backed resume/materialize behavior, `src/WA/phase37_hotspots.py` selects regional entropy hotspots with tested quota/threshold/dedup rules, and `src/WA/visualization/phase37.py` already knows how to subset and plot the region AOIs. What is missing is **contract plumbing**, not new disagreement math.

The cleanest path is an **adapter-first integration**, not a rewrite. Mirror the S02 pattern: extend `src/WA/comparison/evidence_contract.py` with classification artifact families, add a new `src/WA/comparison/classification_contract.py` that owns relpaths/metadata/validation/region subsetting, then add a thin `scripts/run_phase4_classification_contract.py` runner that resolves `--subset canonical` and reuses the existing Phase 3.6 / 3.7 engines. This follows the in-project pattern already proven by `trend_contract.py` and `run_phase4_trend_contract.py`.

Per the loaded `brainstorming` skill rule, this is exactly the kind of work where multiple valid integration routes exist and the contract decision must be made before implementation. Also note that the dependency artifact `.gsd/milestones/M002/slices/S01/S01-SUMMARY.md` is a blocker placeholder, so the trustworthy S01 references are the live code plus stashes `2026-04-08-014`, `2026-04-08-016`, and `2026-04-08-017`.

## Recommendation

Use a **classification contract adapter** rather than pushing contract logic into `phase36.py` or `phase37_hotspots.py`.

Recommended shape:

- Extend `src/WA/comparison/evidence_contract.py` with **classification-specific artifact families**.
- Use a **multi-dataset participant-set key** in the same sorted `+`-joined style already standardized for trend agreement (for example `g2017+glwd_v2+gwd30`). That keeps filenames and downstream indexing from inventing a second convention.
- Write one **region-scoped classification surface dataset** that carries:
  - `entropy`
  - `majority_class`
  - `agreement_count`
  - `joint_valid_mask`
  - `g2017_dominant_class`, `glwd_v2_dominant_class`, `gwd30_dominant_class`
  - `g2017_source_dominant_class`, `glwd_v2_source_dominant_class`, `gwd30_source_dominant_class`
- Add a **region-scoped summary CSV** and **contract hotspot manifest/CSV** instead of leaving classification on legacy global JSON only.
- Keep `phase36.py` as the global compute/cache owner and `phase37_hotspots.py` as the hotspot-selection owner as much as possible. If the current Phase 3.7 API is too write-heavy, extract a pure selection helper from it instead of duplicating threshold/dedup math.

This approach is best because it preserves the already-proven global/HPC route, keeps caching and progress visibility honest, and makes S04’s unified hotspot ledger much easier: S04 can consume region-scoped contract artifacts instead of reverse-engineering legacy `phase3.6` / `phase3.7` filenames.

## Implementation Landscape

### Key Files

- `src/WA/comparison/evidence_contract.py` — current shared contract owner. Today it only knows percentage + trend families; S03 needs classification families here first.
- `tests/test_comparison/test_evidence_contract.py` — must be updated when new artifact kinds are added.
- `src/WA/comparison/phase36.py` — proven global 500m backbone. `run_phase36_analysis()` already writes the real scientific products and cache stages; do not reimplement its math.
- `src/WA/phase37_hotspots.py` — proven hotspot selector over Phase 3.6 outputs. Good source of local-threshold / dedupe / quota behavior, but still tied to legacy global manifest writing and its own YAML region loader.
- `src/WA/visualization/phase37.py` — contains `subset_phase37_plot_dataset_to_bbox(...)`, which is already tested for bbox slicing and should be reused for region-scoped contract surfaces.
- `src/WA/classification.py` — single owner of YAML-driven unified/source class naming and mappings. If S03 needs labels, raw/source class ids, or class-name metadata, use this instead of hardcoding.
- `src/WA/comparison/trend_contract.py` — the closest architectural template for S03. It shows the intended split between pure compute modules and contract write/validation code.
- `scripts/run_phase4_trend_contract.py` — the exact runner pattern to copy: contract region resolution, `--skip` reload behavior, stage-tagged logs, and explicit failure wrapping.
- `src/WA/visualization/phase4.py` — current phase4 reload helpers are percentage/trend-only. If S03 needs downstream loading before S04, add classification-specific helpers here rather than forcing classification CSVs through percentage loaders.
- `src/WA/test_selection.py` / `docs/testing/test-categories.md` — should be updated if new classification contract files must map into the `phase4` related-test family.
- `docs/stashes/2026-04-08-014-m002-s01-t01-evidence-contract.md` — S01 contract rules and strict-validation pattern.
- `docs/stashes/2026-04-08-016-m002-s01-t03-regional-contract-summary.md` — shows how S01 attached an existing producer to the contract without rewriting the scientific core.
- `docs/stashes/2026-04-08-018-m002-s02-t01-trend-contract.md` and `docs/stashes/2026-04-08-019-m002-s02-t02-trend-contract-runner.md` — the pattern S03 should follow almost directly.
- `docs/stashes/2026-03-31-016-phase36-global-500m-classification-disagreement-implementation.md` and `docs/stashes/2026-03-31-017-phase36-global-cache.md` — confirm what Phase 3.6 already proves and what cache stages exist.
- `docs/stashes/2026-04-01-004-phase37-hotspots-implementation.md` — current hotspot rules and outputs.
- `docs/stashes/2026-04-04-002-phase36-gwd30-source-dominant-oom-fix.md` and `docs/stashes/2026-04-05-001-phase36-gwd30-source-dominant-wetland-priority.md` — important GWD30 raw/source-dominant caveats that S03 must preserve.

### Build Order

1. **Contract schema first**
   - Add classification artifact semantics to `evidence_contract.py`.
   - Decide the multi-dataset key and hotspot-id convention before any filenames are written.
   - Update `tests/test_comparison/test_evidence_contract.py` immediately.

2. **Classification contract adapter second**
   - Add `src/WA/comparison/classification_contract.py`.
   - It should own relpaths, metadata JSON, atomic writes, validators, region subsetting, and hotspot manifest rewriting.
   - It should consume existing Phase 3.6 / Phase 3.7 outputs instead of re-running disagreement logic internally.

3. **Runner third**
   - Add `scripts/run_phase4_classification_contract.py`.
   - Resolve `--subset canonical` / `--region` through `load_phase4_evidence_contract(...)`.
   - Reuse `run_phase36_analysis(...)` for cache-backed global outputs.
   - Then write region-scoped contract artifacts and hotspot manifests.

4. **Reload/test-selection follow-up fourth**
   - Only if needed, add classification reload helpers to `src/WA/visualization/phase4.py`.
   - Update `src/WA/test_selection.py` and `docs/testing/test-categories.md` so `run_related_tests.py` catches the new files.

### Verification Approach

Contract layer only:

```bash
ruff check \
  src/WA/comparison/evidence_contract.py \
  src/WA/comparison/classification_contract.py \
  tests/test_comparison/test_evidence_contract.py \
  tests/test_comparison/test_classification_contract.py
```

```bash
python -m pytest \
  tests/test_comparison/test_evidence_contract.py \
  tests/test_comparison/test_classification_contract.py -q
```

If Phase 3.6 / Phase 3.7 internals move:

```bash
python -m pytest \
  tests/test_phase3_6_analysis.py \
  tests/test_phase3_7_hotspots.py \
  tests/test_phase3_7_plotting.py \
  tests/test_phase3_7_hotspot_panels.py -q
```

If phase4 runner/reload helpers are added:

```bash
python scripts/run_phase4_classification_contract.py --help
```

```bash
python -m pytest tests/test_visualization/test_phase4.py -q
```

```bash
python scripts/run_related_tests.py \
  src/WA/comparison/classification_contract.py \
  scripts/run_phase4_classification_contract.py \
  src/WA/visualization/phase4.py \
  src/WA/test_selection.py
```

Likely HPC commands after implementation:

1. Refresh or materialize the global Phase 3.6 backbone when needed:

```bash
python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 512 \
  --static-worker-count 1 \
  --gwd30-worker-count 4
```

2. Single-region contract smoke test:

```bash
python scripts/run_phase4_classification_contract.py \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --year 2016 \
  --no-skip
```

3. Canonical subset proof:

```bash
python scripts/run_phase4_classification_contract.py \
  --subset canonical \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --year 2016 \
  --no-skip
```

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Region catalog / canonical subset / stable relpaths | `src/WA/comparison/evidence_contract.py` | S01/S02 already standardized this and tests enforce strict validation. |
| Global 500m classification compute + cache resume | `src/WA/comparison/phase36.py::run_phase36_analysis` | Preserves proven cache stages, GWD30 OOM fixes, and visible stage logging. |
| Hotspot selection heuristics | `src/WA/phase37_hotspots.py` | Existing local-threshold/dedupe/quota behavior already has targeted tests. |
| Region bbox subsetting | `src/WA/visualization/phase37.py::subset_phase37_plot_dataset_to_bbox` | Already handles descending-lat selections and is tested. |
| Contract writer / runner architecture | `src/WA/comparison/trend_contract.py` + `scripts/run_phase4_trend_contract.py` | Closest in-project pattern for multi-artifact contract plumbing. |

## Constraints

- Do **not** modify `config/` without approval. S03 must reuse `config/priority_regions.yaml` and `config/classification_mappings.yaml` through existing helpers.
- Default target year is **2016**.
- `phase36.py` is the HPC-safe backbone; S03 should wrap its outputs, not replace its cache layout.
- If implementation updates `CHANGELOG.md`, keep the repo’s raw-docstring wrapper or Ruff will fail.
- The dependency file `.gsd/milestones/M002/slices/S01/S01-SUMMARY.md` is not trustworthy; it is a placeholder written after auto-mode recovery failed.

## Common Pitfalls

- **Loose phase37 region parsing vs strict contract parsing** — `phase37_hotspots.py` still uses its own `load_phase37_priority_regions(...)`. If S03 keeps that as-is, region semantics can drift from the stricter M002 contract. Prefer contract-resolved regions or a translation layer from `ContractRegion`.
- **Two quota allocators already exist** — percentage hotspots use `allocate_percentage_region_quotas(...)`, phase37 uses `allocate_phase37_region_quotas(...)` with slightly different tie-break behavior. S03 should choose one contract-wide rule explicitly.
- **Legacy hotspot IDs are not contract-stable** — current Phase 3.7 IDs look like `entropy-<region>-001` and omit the participant set. If S03 rewrites IDs, preserve a compatibility field or the phase3.6.1 trace tools become harder to reuse.
- **`class_disagreement_summary` is currently not populated** — the `Phase37Hotspot` dataclass declares it, but the selection code never fills it. Do not promise per-hotspot class-mixture stats unless S03 computes them deliberately.
- **Source-dominant vars matter** — recent fixes around `gwd30_source_dominant_class` were specifically to preserve raw hotspot panel and diagnostic behavior. A contract surface that drops source-dominant vars will regress downstream tools.

## Open Risks

- The biggest unresolved design choice is whether classification artifacts should be keyed by a participant-set string (`g2017+glwd_v2+gwd30`) or a synthetic dataset id. Decide this before writing tests and filenames.
- If `run_phase37_hotspot_selection(...)` is reused without refactor, S03 may produce both legacy `results/phase3.7_hotspots/*` artifacts and new contract artifacts. That is workable but messy.
- If S03 wants phase4-style reload helpers immediately, `src/WA/visualization/phase4.py` will need classification-specific loaders; the current percentage/trend loaders are not a clean fit.

## Skills Discovered

Per the loaded `find-skills` workflow, there are optional but not-installed skills that could help if implementation later gets deeper into xarray/geospatial ergonomics:

| Technology | Skill | Status |
|------------|-------|--------|
| xarray | `tondevrel/scientific-agent-skills@xarray` | available |
| geospatial Python / geopandas | `davila7/claude-code-templates@geopandas` | available |
