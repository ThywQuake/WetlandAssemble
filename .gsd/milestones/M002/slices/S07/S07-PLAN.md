# S07: Ten-region HPC materialization and readiness/ledger proof

**Goal:** 在不改动既有 evidence-contract 语义前提下，把 percentage / classification / trend 三条 producer 链在真实十区输入上 materialize 到 `results/phase4`，然后用 readiness 全绿 + unified ledger 复开作为本 slice 的唯一完成证明，为 S08 的 strict paper-pack proof 提供真实上游产物。
**Demo:** After this: After this: the percentage/classification/trend producer ladder has been executed for the full ten-region set, readiness reports all required families as ready, and unified hotspot ledgers reopen cleanly on real outputs.

## Tasks
- [x] **T01: Fixed the trend submit preflight to use the repo interpreter and froze the ten-region Phase 4 command ladder with a copied dry-run proof bundle.** — Why: catch selector/key drift before any real ten-region compute so later tasks do not debug stale participant sets or hand-written region lists.

## Steps
1. Reconfirm from live code that wide execution stays on `--subset ten`, `percentage_key=canonical`, `classification_key=canonical`, and `trend_participant_set_key=giems_mc+gwd30+swamps+topmodel+wad2m`; keep `topmodel` in every trend/readiness/ledger command.
2. Run the local preflight surface: `bash -n` on `scripts/submit_phase4_trend_contract.sh`, `--help` on the five Phase 4 CLIs, then the trend wrapper `--dry-run` with explicit `--repo`, `--python-bin`, HPC standardized dir, repo-local `--jobs-base`, and `--no-progress`.
3. Copy the generated dry-run summary TSV into `results/phase4/proof/phase4-trend-contract-dry-run.tsv`; if preflight exposes a selector or wrapper bug, patch only the touched contract/runner files, rerun focused tests/help commands, and resync before any real submit.
4. Write `results/phase4/proof/phase4-ten-region-command-ladder.md` in bilingual form, recording the frozen region order, keys, participant ids, exact HPC commands, and where later tasks should copy proof artifacts.

## Must-Haves
- [ ] No later task uses a hand-written ten-region list or drops `topmodel` from the trend participant set.
- [ ] The dry-run summary proves ten resolved regions, five datasets, and visible `--no-skip` intent.
- [ ] Any local bug fix is backed by the touched shell/help/pytest surfaces before HPC reruns continue.

## Done when
The repo has one checked command ladder plus a copied dry-run summary, and later tasks can reuse it without re-deriving keys or selectors.
  - Estimate: 90m
  - Files: scripts/run_phase4_percentage_contract.py, scripts/run_phase4_classification_contract.py, scripts/run_phase4_trend_contract.py, scripts/submit_phase4_trend_contract.sh, scripts/run_phase4_scaleout_readiness.py, scripts/run_phase4_hotspot_ledger.py, tests/test_submit_phase4_trend_contract.py, results/phase4/proof/phase4-ten-region-command-ladder.md
  - Verify: bash -n scripts/submit_phase4_trend_contract.sh
python scripts/run_phase4_percentage_contract.py --help
python scripts/run_phase4_classification_contract.py --help
python scripts/run_phase4_trend_contract.py --help
python scripts/run_phase4_scaleout_readiness.py --help
python scripts/run_phase4_hotspot_ledger.py --help
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
  --jobs-base temp/slurm-jobs-s07 \
  --tmp-root temp/slurm-tmp-s07 \
  --no-progress
test -s results/phase4/proof/phase4-trend-contract-dry-run.tsv
- [ ] **T02: Materialize the ten-region percentage and classification contract families** — Why: readiness and ledger cannot prove anything until the percentage and classification families exist materially for the full ordered ten-region set.

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
  - Estimate: 4h
  - Files: scripts/run_phase4_percentage_contract.py, scripts/run_phase4_classification_contract.py, src/WA/comparison/percentage_backbone.py, src/WA/comparison/percentage_hotspots.py, src/WA/comparison/classification_contract.py, tests/test_comparison/test_percentage_backbone.py, tests/test_comparison/test_classification_contract.py, results/phase4/proof/phase4-producer-materialization.md
  - Verify: python scripts/run_phase4_percentage_contract.py \
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
- [ ] **T03: Submit and monitor the ten-region trend fanout to completion** — Why: the trend line is the only leg with one-region-per-job fanout and checkpointed rerun semantics, so it needs its own monitored operational boundary.

## Steps
1. Reuse the T01 command ladder to submit the real wrapper on HPC with explicit `--repo`, `--python-bin`, standardized root, `--subset ten`, annual `1990..2020`, `--no-progress`, and the five dataset ids `gwd30`, `giems_mc`, `topmodel`, `swamps`, `wad2m`.
2. Copy the wrapper summary TSV into `results/phase4/proof/phase4-trend-contract-submit.tsv`, then monitor the ten job ids until every region finishes; record retries or failed regions instead of trusting partial completion.
3. Spot-check representative agreement and hotspot outputs plus checkpoint reuse on rerun; if a job fails because of code, patch only the touched trend/wrapper/test files locally, rerun focused tests, resync, and resubmit only the failed region(s).
4. Write `results/phase4/proof/phase4-trend-fanout.md` in bilingual form, capturing the submit summary, rerun history, and the final participant-set key used by readiness and ledger.

## Must-Haves
- [ ] All ten regions complete under `participant_set_key=giems_mc+gwd30+swamps+topmodel+wad2m`.
- [ ] The copied submit summary TSV accounts for every region job and becomes part of the slice proof bundle.
- [ ] Trend reruns stay on the wrapper/checkpoint route; use direct `run_phase4_trend_contract.py` only for one-region debugging.

## Done when
The submit summary accounts for all ten region jobs, and representative first/last region trend agreement and hotspot outputs exist on disk for readiness to consume.
  - Estimate: 1d
  - Files: scripts/submit_phase4_trend_contract.sh, scripts/run_phase4_trend_contract.py, src/WA/comparison/trends.py, src/WA/comparison/trend_contract.py, tests/test_submit_phase4_trend_contract.py, tests/test_comparison/test_trend_contract.py, tests/test_comparison/test_trends.py, results/phase4/proof/phase4-trend-fanout.md
  - Verify: bash scripts/submit_phase4_trend_contract.sh \
  --repo "$HOME/repos/WA" \
  --python-bin "$HOME/repos/WA/.venv/bin/python" \
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
  --no-progress
test -s results/phase4/proof/phase4-trend-contract-submit.tsv
test -f results/phase4/trend_hotspot_manifests/amazon/giems_mc+gwd30+swamps+topmodel+wad2m__amazon__trend_hotspot_manifest.json
test -f results/phase4/trend_hotspot_manifests/northernaus/giems_mc+gwd30+swamps+topmodel+wad2m__northernaus__trend_hotspot_manifest.json
- [ ] **T04: Prove all-green readiness and rebuild the ten unified hotspot ledgers** — Why: readiness plus unified-ledger reopen is the actual S07 acceptance boundary, not file counting or one-region smoke output.

## Steps
1. Run `scripts/run_phase4_scaleout_readiness.py` with `--subset ten`, canonical percentage/classification keys, and the same five trend dataset ids used in T03; inspect the CSV/JSON first and rerun upstream producer families if any row is `missing` or `partial`.
2. Assert from the JSON payload that `ready_region_ids` exactly equals the ordered ten-region contract list, then capture the report paths and any rerun notes in `results/phase4/proof/phase4-readiness-ledger-proof.md`.
3. Run `scripts/run_phase4_hotspot_ledger.py --subset ten --no-skip` with the same keys/participant ids, then verify representative first/last region ledgers reopen cleanly from disk.
4. If readiness or ledger exposes a real code bug, patch only the touched readiness/ledger files and focused tests locally, resync, rerun readiness, then rerun ledger; do not hand-edit downstream artifacts.

## Must-Haves
- [ ] The readiness CSV/JSON exists and every region/family row is `ready`.
- [ ] Ten `canonical__<region>__unified_hotspot_ledger.csv` files exist under `results/phase4/unified_hotspot_ledgers/`.
- [ ] The proof note records the report paths, representative ledger paths, and the exact remaining handoff to S08 strict pack proof.

## Done when
The ten-region readiness report is all-green and the unified ledgers reopen without family-context errors, making S07's producer -> readiness -> ledger ladder operationally true.
  - Estimate: 3h
  - Files: scripts/run_phase4_scaleout_readiness.py, scripts/run_phase4_hotspot_ledger.py, src/WA/comparison/scaleout_readiness.py, src/WA/comparison/hotspot_ledger.py, tests/test_comparison/test_scaleout_readiness.py, tests/test_comparison/test_hotspot_ledger.py, results/phase4/proof/phase4-readiness-ledger-proof.md
  - Verify: python scripts/run_phase4_scaleout_readiness.py \
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
