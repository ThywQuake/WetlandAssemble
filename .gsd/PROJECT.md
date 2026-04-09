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

M001 is complete. M002 is now complete through **S07 closeout in local repo state**, but S07 closed as an **honest fail-closed boundary-compression slice**, not as a real authenticated ten-region materialization proof. The repo now contains the frozen ten-region ladder, proof notes, wrapper/readiness/ledger guardrails, and exact authenticated rerun commands. The remaining blocking gap is still external: authenticated HPC materialization and sync-back of the real ten-region percentage / classification / trend / readiness / ledger artifacts, followed by S08 strict paper-pack proof and milestone validation.

What is now stable in-code for M002:

- shared Phase 4 evidence-contract semantics in `src/WA/comparison/evidence_contract.py`
- one ordered shared `ten` selector plus explicit subset/region validation across the main Phase 4 CLIs
- contract-backed percentage surfaces, summaries, and hotspot families via:
  - `src/WA/comparison/percentage_backbone.py`
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
- the trend submit wrapper preflight now resolves regions with the explicit repo interpreter (`--python-bin`) instead of bare `python3`
- a unified hotspot ledger in `src/WA/comparison/hotspot_ledger.py` that stays fail-closed unless all three hotspot families are complete and semantically valid
- ten-region readiness diagnostics via:
  - `src/WA/comparison/scaleout_readiness.py`
  - `scripts/run_phase4_scaleout_readiness.py`
- focused readiness/ledger regressions that prove all-ready synthetic subset-ten inputs reopen cleanly while real missing inputs remain loudly fail-closed:
  - `tests/test_comparison/test_scaleout_readiness.py`
  - `tests/test_comparison/test_hotspot_ledger.py`
- semantic reload helpers in `src/WA/visualization/phase4.py` so downstream code can reopen percentage/classification/trend/ledger artifacts by meaning instead of guessed filenames
- a derived paper-facing pack builder plus strict proof surface via:
  - `src/WA/visualization/phase4_pack.py`
  - `scripts/run_phase4_evidence_pack.py`
  - deterministic `manifest.json`, `complete_pack_proof.json`, and `complete_pack_proof.md` outputs under a pack root outside `results/phase4`
- an S07 proof bundle under `results/phase4/proof/` that freezes:
  - the ten-region command ladder
  - the copied trend dry-run TSV
  - the producer-materialization boundary
  - the trend-fanout boundary
  - the readiness/ledger stop-state and S08 handoff gate
- standing execution rules in `.gsd/DECISIONS.md`:
  - D053 — auto-mode owns local verification/proof bookkeeping, while OTP-authenticated HPC work remains an external boundary
  - D054 — trend-wrapper preflight must use the explicit repo interpreter

What is **not** closed yet:

- fresh authenticated HPC materialization of the ten-region percentage / classification / trend outputs on real external inputs
- one real copied `results/phase4/proof/phase4-trend-contract-submit.tsv` from the authenticated trend submit
- one real all-green subset-ten readiness report synced back into the repo
- one real `results/phase4/unified_hotspot_ledgers/` tree synced back into the repo
- one real `--subset ten --strict` complete-pack claim written from regenerated science artifacts rather than local fixtures / stop-state notes
- milestone validation / completion records for M002 after that real strict proof exists
- hotspot-cause interpretation surfaces using MODIS / auxiliary hydro-climate evidence
- fraction-first fusion and the multi-objective evaluation scorecard

## Current Recommended Route

The next practical step is still **not more local implementation**. Use the S07 proof bundle as the recovery surface, then complete the real external-input run from an authenticated workstation/HPC session:

1. sync the repo to HPC via:
   ```bash
   rsync -avz --delete --exclude-from=.gitignore ./ \
     2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/
   ```
2. on HPC, run:
   ```bash
   python scripts/run_phase4_percentage_contract.py \
     --subset ten \
     --output-root results/phase4 \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --dataset-key canonical \
     --surface-year 2016 \
     --start-year 1990 \
     --end-year 2020 \
     --no-skip
   ```
3. on HPC, run:
   ```bash
   python scripts/run_phase4_classification_contract.py \
     --subset ten \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --classification-key canonical \
     --year 2016 \
     --phase36-output-dir results/phase3.6 \
     --phase36-cache-dir results/cache/phase3_6 \
     --phase37-output-dir results/phase3.7_hotspots \
     --phase37-cache-dir results/cache/phase3_7 \
     --no-skip
   ```
4. on HPC, fan out trend regeneration with:
   ```bash
   bash scripts/submit_phase4_trend_contract.sh \
     --repo "$PWD" \
     --python-bin "$PWD/.venv/bin/python" \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --subset ten \
     --dataset-id gwd30 \
     --dataset-id giems_mc \
     --dataset-id topmodel \
     --dataset-id swamps \
     --dataset-id wad2m \
     --aggregation annual \
     --start-year 1990 \
     --end-year 2020 \
     --min-observations 5 \
     --min-overlap-years 5 \
     --top-hotspots 10 \
     --cpus 2 \
     --time 480 \
     --partition C064M0256G \
     --jobs-base temp/slurm-jobs-s07 \
     --tmp-root temp/slurm-tmp-s07 \
     --no-progress
   ```
5. on HPC, rerun the readiness gate:
   ```bash
   python scripts/run_phase4_scaleout_readiness.py \
     --subset ten \
     --output-root results/phase4 \
     --percentage-key canonical \
     --classification-key canonical \
     --trend-dataset-id gwd30 \
     --trend-dataset-id giems_mc \
     --trend-dataset-id topmodel \
     --trend-dataset-id swamps \
     --trend-dataset-id wad2m
   ```
6. assert the readiness JSON is truly all-green, then build the unified ledger:
   ```bash
   python scripts/run_phase4_hotspot_ledger.py \
     --subset ten \
     --output-root results/phase4 \
     --ledger-key canonical \
     --percentage-key canonical \
     --classification-key canonical \
     --trend-dataset-id gwd30 \
     --trend-dataset-id giems_mc \
     --trend-dataset-id topmodel \
     --trend-dataset-id swamps \
     --trend-dataset-id wad2m \
     --no-skip
   ```
7. sync back into the repo:
   - `results/phase4/proof/phase4-trend-contract-submit.tsv`
   - `results/phase4/scaleout_readiness/`
   - `results/phase4/unified_hotspot_ledgers/`
8. only after those synced-back artifacts exist, run:
   ```bash
   python scripts/run_phase4_evidence_pack.py --subset ten --strict ...
   ```
9. inspect `results/figures/phase4_pack/manifest.json` and `complete_pack_proof.{json,md}`
10. validate M002, then complete the milestone

Do **not** bypass the shared `ten` selector, the semantic reload helpers, the readiness gate, or the strict pack proof by hand-writing region lists, dropping `topmodel`, or guessing filenames.

## Architecture / Key Patterns

- Python package under `src/WA`, mainly split across `loaders`, `comparison`, `validation`, and `visualization`
- Comparison modules now expose three contract-backed hotspot families plus one unified long-form ledger
- Shared evidence objects use paired manifest/data outputs, provenance-rich metadata, and fail-closed reload validation
- Wide Phase 4 runs follow an explicit selector -> producer/reload -> readiness -> ledger -> pack/proof sequence rather than one opaque batch step
- Percentage scale-out uses one multi-dataset contract bundle per region, including GWD30 restored through Stage-1 tile manifests
- Classification scale-out wraps Phase 3.6 / 3.7 producers rather than duplicating disagreement science in Phase 4
- Trend scale-out separates stable downstream contract artifacts from resumable region/dataset checkpoints
- Paper-facing outputs are a derived layer under a dedicated pack root and must never mutate the science contract tree under `results/phase4`
- Unified hotspot comparison preserves family-local score meaning via `primary_score_name`, `primary_score_value`, `family_percentile`, and `line_specific_json`
- The complete-pack claim surface is explicit: proof artifacts are always written, but only `--strict` turns incomplete readiness/ledger proof into a non-zero exit
- S07 added an execution-boundary pattern for OTP-gated work: keep exact rerun commands and proof targets in-repo, keep failures visible, and never treat container-only diagnostics as synced-back completion proof
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
  - [x] S07 Ten-region HPC materialization and readiness/ledger proof
  - [ ] S08 Strict paper-pack proof and evidence-audit repair
- [ ] M003: 热点成因解释与质量差异分析 — explain hotspot causes with quantitative auxiliary evidence plus land-cover context and turn those explanations into dataset-quality judgments
- [ ] M004: Fraction-First 融合与多目标验证 — build a balanced scorecard and validate a fraction-first fused product against explicit baselines
