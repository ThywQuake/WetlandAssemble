---
estimated_steps: 12
estimated_files: 8
skills_used:
  - sync-hpc
---

# T02: Materialize the ten-region percentage and classification contract families

Why: readiness and ledger cannot prove anything until the percentage and classification families exist materially for the full ordered ten-region set.

## Steps
1. Use the project `sync-hpc` route to rsync the repo, then run `scripts/run_phase4_percentage_contract.py` on HPC with `--subset ten`, `/lustre/home/2200013429/Wetland_Assemble/data/standardized`, `--surface-year 2016`, `--start-year 1990`, `--end-year 2020`, and `--no-skip`.
2. Run `scripts/run_phase4_classification_contract.py` on HPC with `--subset ten`, the same standardized root, `--year 2016`, explicit `results/phase3.6` / `results/cache/phase3_6` / `results/phase3.7_hotspots` / `results/cache/phase3_7` directories, and `--no-skip`.
3. Spot-check representative first and last region artifacts (`amazon`, `northernaus`) for surface, summary, and hotspot manifest/table pairs; if a producer bug appears, patch only the touched producer/reload files, rerun focused local tests/help surfaces, resync, and rerun only the failed family.
4. Write `results/phase4/proof/phase4-producer-materialization.md` in bilingual form, logging the executed commands, representative output paths, and any rerun decisions.

## Must-Haves
- [ ] `dataset_key=canonical` and `classification_key=canonical` stay unchanged across all ten regions.
- [ ] Every region has percentage and classification surface/summary/hotspot outputs; no hand-edited artifacts or `--skip` shortcuts are used.
- [ ] Representative first/last region outputs can be reopened from disk before readiness runs.

## Done when
The percentage and classification families are materially present for the ten-region contract set, and readiness has real upstream inputs instead of all-`missing` rows.

## Inputs

- `results/phase4/proof/phase4-ten-region-command-ladder.md`
- `results/phase4/proof/phase4-trend-contract-dry-run.tsv`
- `scripts/run_phase4_percentage_contract.py`
- `scripts/run_phase4_classification_contract.py`
- `src/WA/comparison/percentage_backbone.py`
- `src/WA/comparison/percentage_hotspots.py`
- `src/WA/comparison/classification_contract.py`

## Expected Output

- `results/phase4/hotspot_manifests/amazon/canonical__amazon__hotspot_manifest.json`
- `results/phase4/hotspot_manifests/northernaus/canonical__northernaus__hotspot_manifest.json`
- `results/phase4/classification_hotspot_manifests/amazon/canonical__amazon__classification_hotspot_manifest.json`
- `results/phase4/classification_hotspot_manifests/northernaus/canonical__northernaus__classification_hotspot_manifest.json`
- `results/phase4/proof/phase4-producer-materialization.md`

## Verification

python scripts/run_phase4_percentage_contract.py \
  --subset ten \
  --output-root results/phase4 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --surface-year 2016 \
  --start-year 1990 \
  --end-year 2020 \
  --no-skip
python scripts/run_phase4_classification_contract.py \
  --subset ten \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --year 2016 \
  --phase36-output-dir results/phase3.6 \
  --phase36-cache-dir results/cache/phase3_6 \
  --phase37-output-dir results/phase3.7_hotspots \
  --phase37-cache-dir results/cache/phase3_7 \
  --no-skip
test -f results/phase4/hotspot_manifests/amazon/canonical__amazon__hotspot_manifest.json
test -f results/phase4/hotspot_manifests/northernaus/canonical__northernaus__hotspot_manifest.json
test -f results/phase4/classification_hotspot_manifests/amazon/canonical__amazon__classification_hotspot_manifest.json
test -f results/phase4/classification_hotspot_manifests/northernaus/canonical__northernaus__classification_hotspot_manifest.json

## Observability Impact

- Signals added/changed: `stage=percentage-summary`, `stage=percentage-surface`, `stage=percentage-hotspots`, `stage=phase36`, `stage=phase37`, and `stage=classification` logs remain the first inspection surface.
- How a future agent inspects this: open `results/phase4/proof/phase4-producer-materialization.md` and representative manifest paths under `results/phase4/hotspot_manifests/` and `results/phase4/classification_hotspot_manifests/`.
- Failure state exposed: missing standardized inputs, malformed Phase 3.6 / 3.7 sources, or partial hotspot pairs stay visible in the producer logs and output tree.

## Failure Modes

- **Dependencies**: `scripts/run_phase4_percentage_contract.py`, `scripts/run_phase4_classification_contract.py`, `src/WA/comparison/percentage_backbone.py`, `src/WA/comparison/classification_contract.py`, `/lustre/.../standardized`, and the existing `results/phase3.6` / `results/phase3.7_hotspots` trees.
- **On error**: rerun only the failed family after any required local bug fix and focused tests; do not continue to readiness with partial families.
- **On timeout**: percentage/classification runs may be long I/O jobs; prefer visible progress and rerun just the failed family instead of restarting the full ladder blindly.
- **On malformed response**: reject malformed hotspot manifests, missing Phase 3.6/3.7 sources, or mixed-region artifacts before writing proof notes.

## Load Profile

- **Shared resources**: GWD30 pixel-statistics inputs, Phase 3.6 / 3.7 outputs, `results/phase4` contract tree, and any producer caches.
- **Per-operation cost**: one ten-region percentage materialization plus one ten-region classification materialization, each with per-region surface/summary/hotspot writes.
- **10x breakpoint**: GWD30/Phase 3.6 I/O and cache churn fail before CPU becomes the main bottleneck, so reruns stay family-scoped and visible.

## Negative Tests

- **Malformed inputs**: missing standardized root, missing Phase 3.6 / 3.7 outputs, corrupted hotspot manifest/table pairs, or wrong region ids.
- **Error paths**: producer failures must surface stage-tagged errors (`percentage-summary`, `phase36`, `phase37`, `classification`) and block later tasks.
- **Boundary conditions**: `amazon` and `northernaus` spot-checks, `dataset_key=canonical`, and `classification_key=canonical` remain stable across reruns.
