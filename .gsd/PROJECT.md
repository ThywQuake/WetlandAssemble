# Project

## What This Is

WA (Wetland Assemble) is a research-engineering workspace for comparing and eventually fusing multiple wetland datasets around one thesis-sized logic chain. The project centers on three coordinated evidence lines:

1. **湿地百分比** — normalize multiple datasets to `0-1` wetland fraction on a shared `0.25°` grid and compare their regional and pixel-scale behavior.
2. **分类准确度 / 分类分歧** — compare `G2017 / GLWD / GWD30` after remapping to a shared 8-class wetland vocabulary on a `500m` grid.
3. **时间趋势正确性** — compare trend behavior derived from wetland-fraction surfaces on a shared `0.25°` grid.

The thesis goal is not only to show where datasets differ, but to identify disagreement hotspots, explain why those hotspots appear, judge dataset quality more rigorously, and eventually build a better fraction-first fused product.

## Core Value

One reproducible, paper-aligned evidence backbone that can show **where wetland datasets disagree, why they disagree, and whether a fraction-first fused product is actually better** under a balanced multi-objective scorecard.

## Current State

M001 is complete and closed the audit / recovery-control problem. M002 is still active, and S05 has now closed the **ten-region scale-out execution boundary** in code even though the worktree does not include freshly materialized ten-region science outputs.

What is now stable in-code for M002:

- shared Phase 4 evidence-contract semantics in `src/WA/comparison/evidence_contract.py`
- one ordered shared `ten` selector plus explicit subset/region validation across the main Phase 4 CLIs
- contract-backed percentage surfaces, summaries, and hotspot families via:
  - `src/WA/comparison/percentage_backbone.py`
  - `src/WA/comparison/percentage_hotspots.py`
  - `scripts/run_phase4_percentage_contract.py`
- GWD30 restored to the shared `0.25°` percentage path through Stage-1-backed surface recovery
- contract-backed classification surfaces, summaries, and hotspot manifests for the fixed `g2017+glwd_v2+gwd30` trio via:
  - `src/WA/comparison/classification_contract.py`
  - `scripts/run_phase4_classification_contract.py`
- dataset-scoped trend surfaces/summaries plus participant-set agreement/hotspot families via:
  - `src/WA/comparison/trend_contract.py`
  - `src/WA/comparison/trends.py`
  - `scripts/run_phase4_trend_contract.py`
- resumable trend checkpoints under `results/phase4/trend_checkpoints/` and the HPC-safe fanout wrapper `scripts/submit_phase4_trend_contract.sh`
- a unified hotspot ledger in `src/WA/comparison/hotspot_ledger.py` that stays fail-closed unless all three hotspot families are complete and semantically valid
- ten-region readiness diagnostics via:
  - `src/WA/comparison/scaleout_readiness.py`
  - `scripts/run_phase4_scaleout_readiness.py`
- semantic reload helpers in `src/WA/visualization/phase4.py` so downstream code can reopen percentage/classification/trend/ledger artifacts by meaning instead of guessed filenames
- related-test routing that treats the restored Phase 4 contract, readiness, and ledger paths as one verification family

What is **not** closed yet:

- fresh HPC materialization of the new S05 ten-region producers and readiness/ledger outputs on real external inputs
- S06 paper-ready figure/table/summary packs that consume the ten-region contract outputs and unified ledger directly
- milestone-level reintegration proof that the ten-region outputs are regenerated, reopened, and packaged end-to-end
- hotspot-cause interpretation surfaces using MODIS / auxiliary hydro-climate evidence
- fraction-first fusion and the multi-objective evaluation scorecard

## Current Recommended Route

The next implementation bottleneck is **M002/S06: Paper-ready evidence pack and milestone integration proof**.

Use the S05 execution boundary in this order:

1. run `scripts/run_phase4_percentage_contract.py --subset ten --no-skip` on HPC
2. run `scripts/run_phase4_classification_contract.py --subset ten --no-skip` on HPC
3. fan out trend regeneration with `bash scripts/submit_phase4_trend_contract.sh --repo "$HOME/repos/WA" ... --subset ten --no-progress`
4. scan completeness with `scripts/run_phase4_scaleout_readiness.py --subset ten`
5. only after readiness is satisfactory, build the cross-line final gate with `scripts/run_phase4_hotspot_ledger.py --subset ten --no-skip`
6. use those regenerated ten-region artifacts as the input pack for S06 figures/tables/integration validation

Do **not** bypass the shared `ten` selector, the semantic reload helpers, or the readiness gate by hand-writing region lists or guessing filenames.

## Architecture / Key Patterns

- Python package under `src/WA`, mainly split across `loaders`, `comparison`, `validation`, and `visualization`
- Comparison modules now expose three contract-backed hotspot families plus one unified long-form ledger
- Shared evidence objects use paired manifest/data outputs, provenance-rich metadata, and fail-closed reload validation
- Wide Phase 4 runs now follow an explicit selector -> producer/reload -> readiness -> ledger sequence rather than one opaque batch step
- Percentage scale-out uses one multi-dataset contract bundle per region, including GWD30 restored through Stage-1 tile manifests
- Classification scale-out wraps Phase 3.6 / 3.7 producers rather than duplicating disagreement science in Phase 4
- Trend scale-out separates stable downstream contract artifacts from resumable region/dataset checkpoints
- Unified hotspot comparison preserves family-local score meaning via `primary_score_name`, `primary_score_value`, `family_percentile`, and `line_specific_json`
- HPC execution uses split/cache/merge patterns, explicit submit scripts, and rsync-based deployment rather than git-based remote execution
- Failures should remain visible: readiness distinguishes `ready` / `missing` / `partial`, and ledger failures now emit family-specific diagnostics plus a single-region readiness report
- M001 recovery precedence still stands:
  - S05 = first-stop recovery index
  - S03 = route truth
  - S04 = ordered execution truth
  - S02 = proof-boundary/status matrix
  - S01 = frozen evidence inventory

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement states, and coverage mapping.

## Milestone Sequence

- [x] M001: Current-State Audit and Recovery Control Plane — re-established authoritative route truth, proof boundaries, and ordered re-entry without claiming fresh HPC execution proof
- [ ] M002: 论文主线统一分析合同与核心证据主干
  - [x] S01 Canonical subset contract + wetland-percentage backbone
  - [x] S02 Trend-correctness backbone on the shared contract
  - [x] S03 Classification-disagreement backbone on the shared contract
  - [x] S04 Unified hotspot ledger and cross-line evidence surfaces
  - [x] S05 Ten-region scale-out with reproducible HPC-safe execution
  - [ ] S06 Paper-ready evidence pack and milestone integration proof
- [ ] M003: 热点成因解释与质量差异分析 — explain hotspot causes with quantitative auxiliary evidence plus land-cover context and turn those explanations into dataset-quality judgments
- [ ] M004: Fraction-First 融合与多目标验证 — build a balanced scorecard and validate a fraction-first fused product against explicit baselines
