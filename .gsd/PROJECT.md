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

M001 is complete. M002 is complete in-code through S06, while S07 and S08 now carry the remaining proof work. The resolved 2026-04-09 `auto` override is now captured as the standing D053 execution rule: auto-mode still owns local verification, logging, proof bookkeeping, and targeted fix/resync loops, but the OTP-authenticated HPC sync/submit/readiness/ledger leg remains an explicit external boundary. The remaining gap is therefore no longer local implementation; it is **authenticated external-input materialization plus milestone-level proof closure across S07 and S08**.

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
- public trend-agreement semantic reload/output helpers in `src/WA/comparison/trend_contract.py`, with thin visualization wrappers instead of script-private reload reuse
- a derived paper-facing pack builder plus strict proof surface via:
  - `src/WA/visualization/phase4_pack.py`
  - `scripts/run_phase4_evidence_pack.py`
  - deterministic `manifest.json`, `complete_pack_proof.json`, and `complete_pack_proof.md` outputs under a pack root outside `results/phase4`
- related-test routing that treats the restored Phase 4 contract, readiness, ledger, and paper-pack paths as one verification family

What is **not** closed yet:

- fresh HPC materialization of the ten-region percentage / classification / trend / readiness / ledger outputs on real external inputs
- one real `--subset ten --strict` complete-pack claim written from regenerated science artifacts rather than local fixtures
- milestone validation / completion records for M002 after that real strict proof exists
- hotspot-cause interpretation surfaces using MODIS / auxiliary hydro-climate evidence
- fraction-first fusion and the multi-objective evaluation scorecard

## Current Recommended Route

The next practical step is still **not more local implementation**. Per D053, auto-mode remains the local planning/repair posture, but the S07 producer/readiness/ledger ladder must run from an authenticated workstation/HPC session and fail closed if OTP access is unavailable; only after those artifacts are synced back should S08 rerun the strict paper-pack proof and milestone closeout surfaces.

Recommended order:

1. from an authenticated workstation, sync the repo to HPC via `rsync`
2. run `scripts/run_phase4_percentage_contract.py --subset ten --no-skip`
3. run `scripts/run_phase4_classification_contract.py --subset ten --no-skip`
4. fan out trend regeneration with `bash scripts/submit_phase4_trend_contract.sh --repo "$HOME/repos/WA" ... --subset ten --no-progress`
5. scan completeness with `scripts/run_phase4_scaleout_readiness.py --subset ten`
6. build the cross-line final gate with `scripts/run_phase4_hotspot_ledger.py --subset ten --no-skip`
7. after the S07 artifacts are synced back into the repo, run `python scripts/run_phase4_evidence_pack.py --subset ten --strict ...`
8. inspect `results/figures/phase4_pack/manifest.json` and `results/figures/phase4_pack/complete_pack_proof.{json,md}`
9. validate M002, then complete the milestone

Do **not** bypass the shared `ten` selector, the semantic reload helpers, the readiness gate, or the strict pack proof by hand-writing region lists or guessing filenames.

## Architecture / Key Patterns

- Python package under `src/WA`, mainly split across `loaders`, `comparison`, `validation`, and `visualization`
- Comparison modules now expose three contract-backed hotspot families plus one unified long-form ledger
- Shared evidence objects use paired manifest/data outputs, provenance-rich metadata, and fail-closed reload validation
- Wide Phase 4 runs now follow an explicit selector -> producer/reload -> readiness -> ledger -> pack/proof sequence rather than one opaque batch step
- Percentage scale-out uses one multi-dataset contract bundle per region, including GWD30 restored through Stage-1 tile manifests
- Classification scale-out wraps Phase 3.6 / 3.7 producers rather than duplicating disagreement science in Phase 4
- Trend scale-out separates stable downstream contract artifacts from resumable region/dataset checkpoints
- Paper-facing outputs are a derived layer under a dedicated pack root and must never mutate the science contract tree under `results/phase4`
- Unified hotspot comparison preserves family-local score meaning via `primary_score_name`, `primary_score_value`, `family_percentile`, and `line_specific_json`
- The complete-pack claim surface is explicit: proof artifacts are always written, but only `--strict` turns incomplete readiness/ledger proof into a non-zero exit
- HPC execution uses split/cache/merge patterns, explicit submit scripts, and rsync-based deployment rather than git-based remote execution
- Failures should remain visible: readiness distinguishes `ready` / `missing` / `partial`, ledger failures emit family-specific diagnostics, and incomplete pack claims still write replayable proof artifacts
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
  - [x] S06 Paper-ready evidence pack and milestone integration proof
  - [ ] S07 Ten-region HPC materialization and readiness/ledger proof
  - [ ] S08 Strict paper-pack proof and evidence-audit repair
- [ ] M003: 热点成因解释与质量差异分析 — explain hotspot causes with quantitative auxiliary evidence plus land-cover context and turn those explanations into dataset-quality judgments
- [ ] M004: Fraction-First 融合与多目标验证 — build a balanced scorecard and validate a fraction-first fused product against explicit baselines
