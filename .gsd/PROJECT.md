# Project

## What This Is

WA (Wetland Assemble) is a research-engineering workspace for comparing and ultimately fusing multiple wetland datasets around one thesis-sized logic chain. The project now centers on three coordinated evidence lines:

1. **湿地百分比** — normalize multiple datasets to `0-1` wetland fraction on a shared `0.25°` grid and compare their regional and pixel-scale behavior.
2. **分类准确度 / 分类分歧** — compare `G2017 / GLWD / GWD30` after remapping to a shared 8-class wetland vocabulary on a `500m` grid.
3. **时间趋势正确性** — compare trend behavior derived from wetland-fraction surfaces on a shared `0.25°` grid.

The thesis goal is not only to show where datasets differ, but to identify disagreement hotspots, explain why those hotspots appear, judge dataset quality more rigorously, and eventually build a better fraction-first fused product.

## Core Value

One reproducible, paper-aligned evidence backbone that can show **where wetland datasets disagree, why they disagree, and whether a fraction-first fused product is actually better** under a balanced multi-objective scorecard.

## Current State

M001 is complete and closed the audit / recovery-control problem. M002 is in execution and has now closed the canonical-subset contract surfaces for all three main evidence lines **plus** the cross-line hotspot integration layer.

What is now stable in-code for M002:

- shared Phase 4 evidence-contract semantics in `src/WA/comparison/evidence_contract.py`
- contract-backed percentage surfaces, summaries, and hotspot families on the canonical subset
- contract-backed trend agreement surfaces, trend hotspot manifests, and semantic trend-hotspot reloads
- contract-backed classification surfaces, summaries, and hotspot manifests for the fixed `g2017+glwd_v2+gwd30` trio
- a unified hotspot ledger in `src/WA/comparison/hotspot_ledger.py` that normalizes percentage / classification / trend hotspot families into stable long-form `analysis_object_id` rows with provenance
- semantic reload helpers in `src/WA/visualization/phase4.py` so downstream code can reopen trend hotspots and unified ledgers by meaning instead of guessed filenames
- fail-closed Phase 4 runners:
  - `scripts/run_phase4_trend_contract.py`
  - `scripts/run_phase4_classification_contract.py`
  - `scripts/run_phase4_hotspot_ledger.py`
- related-test routing that treats these contract and ledger paths as one Phase 4 verification family

What is **not** closed yet:

- ten-region scale-out proof for the full contract + ledger chain
- fresh HPC/runtime proof on real canonical outputs for the newly added S04 surfaces
- paper-ready figure/table packs that consume the unified ledger directly
- hotspot-cause interpretation surfaces using MODIS / auxiliary hydro-climate evidence
- fraction-first fusion and the multi-objective evaluation scorecard

## Current Recommended Route

The next implementation bottleneck is **M002/S05: Ten-region scale-out with reproducible HPC-safe execution**.

Use the new S04 surfaces as the stable comparison/control plane:

1. rebuild one-region trend hotspots with `scripts/run_phase4_trend_contract.py --region amazon --no-skip`
2. rebuild one-region unified ledger with `scripts/run_phase4_hotspot_ledger.py --region amazon --no-skip`
3. widen to `--subset canonical`
4. only then expand the same contract/ledger path to the ten-region set

Do **not** bypass the semantic reload helpers or rebuild downstream figure logic around ad hoc filename parsing; S04 established the ledger and reload helpers as the supported boundary.

## Architecture / Key Patterns

- Python package under `src/WA`, mainly split across `loaders`, `comparison`, `validation`, and `visualization`
- Comparison modules now expose three contract-backed hotspot families plus one unified long-form ledger
- Shared evidence objects use paired manifest/data outputs, provenance-rich metadata, and fail-closed reload validation
- Cross-line hotspot comparison preserves family-local score meaning via `primary_score_name`, `primary_score_value`, `family_percentile`, and `line_specific_json`
- Validation modules still use thin wrappers and artifact-return-value patterns for reference imagery / external evidence workflows
- HPC execution uses split/cache/merge patterns, explicit submit scripts, and rsync-based deployment rather than git-based remote execution
- M001 recovery precedence still stands:
  - S05 = first-stop recovery index
  - S03 = route truth
  - S04 = ordered execution truth
  - S02 = proof-boundary/status matrix
  - S01 = frozen evidence inventory
- Broad Phase 4 defaults remain dangerous; year/dataset/region filters must stay explicit until proof gaps are retired
- New milestone outputs must remain **paper evidence objects**, not just intermediate engineering artifacts

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement states, and coverage mapping.

## Milestone Sequence

- [x] M001: Current-State Audit and Recovery Control Plane — re-established authoritative route truth, proof boundaries, and ordered re-entry without claiming fresh HPC execution proof
- [ ] M002: 论文主线统一分析合同与核心证据主干
  - [x] S01 Canonical subset contract + wetland-percentage backbone
  - [x] S02 Trend-correctness backbone on the shared contract
  - [x] S03 Classification-disagreement backbone on the shared contract
  - [x] S04 Unified hotspot ledger and cross-line evidence surfaces
  - [ ] S05 Ten-region scale-out with reproducible HPC-safe execution
  - [ ] S06 Paper-ready evidence pack and milestone integration proof
- [ ] M003: 热点成因解释与质量差异分析 — explain hotspot causes with quantitative auxiliary evidence plus land-cover context and turn those explanations into dataset-quality judgments
- [ ] M004: Fraction-First 融合与多目标验证 — build a balanced scorecard and validate a fraction-first fused product against explicit baselines
