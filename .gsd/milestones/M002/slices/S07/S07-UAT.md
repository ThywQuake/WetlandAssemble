# S07: Ten-region HPC materialization and readiness/ledger proof — UAT

**Milestone:** M002
**Written:** 2026-04-09T07:29:40.643Z

# S07 UAT — Ten-region HPC materialization and readiness/ledger proof

**Milestone:** M002  
**Written:** 2026-04-09

## Preconditions

1. The repo contains the S07 proof bundle and code changes.
2. Local verification uses the repo environment plus `uv` for the split pytest/dependency surface.
3. An authenticated workstation is available for the real HPC leg; repo deployment must use `rsync`, not git.
4. HPC standardized inputs exist under `/lustre/home/2200013429/Wetland_Assemble/data/standardized`.
5. Real reruns must keep `--subset ten`, `dataset_key=canonical`, `classification_key=canonical`, the trend dataset ids `gwd30 giems_mc topmodel swamps wad2m`, and `--no-skip`.

## Test Case 1 — Freeze and verify the ten-region trend fanout ladder locally

### Steps

1. Run:
   ```bash
   bash -n scripts/submit_phase4_trend_contract.sh
   ```
2. Run the five help surfaces:
   ```bash
   python scripts/run_phase4_percentage_contract.py --help
   python scripts/run_phase4_classification_contract.py --help
   python scripts/run_phase4_trend_contract.py --help
   python scripts/run_phase4_scaleout_readiness.py --help
   python scripts/run_phase4_hotspot_ledger.py --help
   ```
3. Run the focused wrapper regression surface:
   ```bash
   uv run --with pytest --python .venv/bin/python python -m pytest tests/test_submit_phase4_trend_contract.py -q
   ```
4. Run the real dry-run wrapper:
   ```bash
   bash scripts/submit_phase4_trend_contract.sh \
     --dry-run \
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
     --jobs-base temp/slurm-jobs-s07-uat \
     --tmp-root temp/slurm-tmp-s07-uat \
     --no-progress
   ```

### Expected outcomes

- Shell syntax is clean.
- All five CLIs expose the expected subset/key options.
- The pytest run passes.
- The dry-run resolves the exact ordered ten regions, includes `topmodel`, shows `Skip mode: --no-skip`, and generates one submit script per region.
- Preflight uses the repo interpreter and no longer fails with the false `No regions resolved` surface.

## Test Case 2 — Local fail-closed readiness/ledger diagnostics stay honest before authenticated sync-back

### Steps

1. Run the subset-ten readiness command:
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
2. Inspect:
   - `results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json`
   - `results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.csv`
3. Run the acceptance assertion:
   ```bash
   python - <<'PY'
   import json
   from pathlib import Path
   path = Path('results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json')
   payload = json.loads(path.read_text())
   expected = ['amazon', 'orinoco', 'pantanal', 'indogangetic', 'mekong', 'sudd', 'congo', 'okavango', 'borneo', 'northernaus']
   assert payload['ready_region_ids'] == expected, payload['ready_region_ids']
   assert payload['incomplete_region_ids'] == [], payload['incomplete_region_ids']
   assert all(row['status'] == 'ready' for row in payload['rows']), 'non-ready row present'
   PY
   ```
4. Run the ledger command:
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

### Expected outcomes

- The readiness CLI writes deterministic subset-ten CSV/JSON diagnostics.
- In the current local snapshot, the readiness report remains all-`missing` with `ready_region_ids=[]`; that is the expected honest failure signal until authenticated outputs are synced back.
- The assertion fails rather than silently downgrading to a best-effort pass.
- The ledger fails closed at the first missing region and writes the single-region readiness diagnostic (`regions-amazon__...__scaleout_readiness.{csv,json}`) with `stage=ledger action=family-context` logs.
- No unified ledger CSV should be claimed locally while upstream families are missing.

## Test Case 3 — Authenticated HPC producer ladder materializes all three upstream families

### Steps

1. Sync the repo from an authenticated workstation:
   ```bash
   rsync -avz --delete --exclude-from=.gitignore ./ \
     2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/
   ```
2. Run on HPC:
   ```bash
   ssh 2200013429@wm2-data.pku.edu.cn <<'SH'
   set -euo pipefail
   cd /lustre/home/2200013429/repos/WA2
   python scripts/run_phase4_percentage_contract.py \
     --subset ten \
     --output-root results/phase4 \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --dataset-key canonical \
     --surface-year 2016 \
     --start-year 1990 \
     --end-year 2020 \
     --no-skip
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
   test -f results/phase4/hotspot_manifests/amazon/canonical__amazon__hotspot_manifest.json
   test -f results/phase4/hotspot_manifests/northernaus/canonical__northernaus__hotspot_manifest.json
   test -f results/phase4/classification_hotspot_manifests/amazon/canonical__amazon__classification_hotspot_manifest.json
   test -f results/phase4/classification_hotspot_manifests/northernaus/canonical__northernaus__classification_hotspot_manifest.json
   test -f results/phase4/trend_hotspot_manifests/amazon/giems_mc+gwd30+swamps+topmodel+wad2m__amazon__trend_hotspot_manifest.json
   test -f results/phase4/trend_hotspot_manifests/northernaus/giems_mc+gwd30+swamps+topmodel+wad2m__northernaus__trend_hotspot_manifest.json
   SH
   ```
3. Sync back the copied submit TSV:
   ```bash
   rsync -avz \
     2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/results/phase4/proof/phase4-trend-contract-submit.tsv \
     results/phase4/proof/
   ```

### Expected outcomes

- The frozen selector/key set is unchanged.
- Real percentage/classification/trend manifests exist for representative first/last regions.
- The copied submit TSV exists locally and contains one row per region.
- No hand-written region list or dropped `topmodel` is involved anywhere in the run.

## Test Case 4 — Authenticated readiness + unified ledger acceptance gate for S07

### Steps

1. Run on the authenticated HPC repo:
   ```bash
   ssh 2200013429@wm2-data.pku.edu.cn <<'SH'
   set -euo pipefail
   cd /lustre/home/2200013429/repos/WA2
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
   python - <<'PY'
   import json
   from pathlib import Path
   path = Path('results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json')
   payload = json.loads(path.read_text())
   expected = ['amazon', 'orinoco', 'pantanal', 'indogangetic', 'mekong', 'sudd', 'congo', 'okavango', 'borneo', 'northernaus']
   assert payload['ready_region_ids'] == expected, payload['ready_region_ids']
   assert payload['incomplete_region_ids'] == [], payload['incomplete_region_ids']
   assert all(row['status'] == 'ready' for row in payload['rows']), 'non-ready row present'
   PY
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
   test -f results/phase4/unified_hotspot_ledgers/amazon/canonical__amazon__unified_hotspot_ledger.csv
   test -f results/phase4/unified_hotspot_ledgers/northernaus/canonical__northernaus__unified_hotspot_ledger.csv
   SH
   ```
2. Sync back the readiness and ledger trees:
   ```bash
   rsync -avz \
     2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/results/phase4/scaleout_readiness/ \
     results/phase4/scaleout_readiness/
   rsync -avz \
     2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/results/phase4/unified_hotspot_ledgers/ \
     results/phase4/unified_hotspot_ledgers/
   ```

### Expected outcomes

- `ready_region_ids` equals the exact ordered ten-region contract list.
- `incomplete_region_ids` is empty and every readiness row is `ready`.
- Representative `amazon` and `northernaus` unified ledgers exist both on HPC and after sync-back.
- Only after this gate passes may S08 run `python scripts/run_phase4_evidence_pack.py --subset ten --strict ...`.

## Edge Case 1 — OTP/auth is unavailable

### Steps

1. Attempt the normal `rsync` / `ssh` route from a non-authenticated context.

### Expected outcomes

- The run stops at the auth boundary (`OTP Verification Fail!` / keyboard-interactive denial).
- Operators use the existing S07 proof bundle as the recovery surface.
- No one fabricates `phase4-trend-contract-submit.tsv`, readiness green status, or unified ledgers.

## Edge Case 2 — Readiness is still `missing` or `partial` after HPC rerun

### Steps

1. Inspect the subset-ten readiness CSV/JSON and the region-specific ledger diagnostic if the ledger run fails.
2. Rerun only the missing producer family or failed region jobs using the frozen commands.

### Expected outcomes

- Readiness diagnostics identify which family/region remains missing or partial.
- Operators repair only the missing producer or rerun the failed region jobs; they do not hand-edit downstream outputs.
- S08 remains blocked until the subset-ten readiness report is all-green and representative ledgers reopen cleanly.

