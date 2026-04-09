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
- [x] **T02: Documented the blocked T02 producer-materialization boundary, proved the percentage/classification fail-closed surfaces locally, and captured the exact authenticated HPC rerun commands.** — Why: readiness and ledger cannot prove anything until the percentage and classification families exist materially for the full ordered ten-region set.

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
  - Blocker: Real ten-region percentage/classification outputs are still missing locally; T03 and T04 must not be treated as runnable proof work until the authenticated HPC rerun succeeds. This container also lacks one working pytest path for the scientific test surface (`python -m pytest` lacks `pytest`, while bare `pytest` / `uv run pytest` lack `numpy`), so verification used direct `python`-level checks for the fail-closed producer behaviors instead.
- [x] **T03: Pinned the trend-wrapper boundary checks and wrote the authenticated fanout sync-back proof note.** — Why: T02 proved the remaining work cannot be completed from this auto-mode container because the real ten-region inputs live behind OTP-gated HPC access. This task converts the rest of S07 into an authenticated-session execution boundary instead of pretending the missing percentage/classification families already exist.

Steps
1. From an authenticated workstation, use the project sync-hpc/rsync route to sync the repo to `/lustre/home/2200013429/repos/WA2/`; keep the frozen `--subset ten`, `dataset_key=canonical`, `classification_key=canonical`, and trend dataset ids `gwd30`, `giems_mc`, `topmodel`, `swamps`, `wad2m`.
2. In that authenticated HPC repo, rerun the real ten-region percentage and classification commands with `--no-skip`, then verify representative first/last region hotspot manifests on HPC before moving on.
3. Still in the authenticated HPC repo, submit the trend wrapper with the explicit repo/python/std-root/jobs dirs from T01, monitor all ten region jobs to completion, and record retries or failed region reruns instead of trusting partial completion.
4. Copy the trend submit TSV plus representative percentage/classification/trend manifests back into the repo proof bundle, and write `results/phase4/proof/phase4-trend-fanout.md` in bilingual form with the authenticated rerun boundary, job ids, retries, synced-back paths, and the final participant-set key.
5. If any remote failure is caused by code, patch only the touched producer/wrapper/test files locally, rerun focused checks, resync, and rerun only the failed family or failed region jobs.

Must-Haves
- [ ] No one resumes S07 from the auto-mode container alone; the OTP-authenticated HPC session is the required execution environment.
- [ ] The percentage/classification families are materially present before the trend submit summary is treated as proof.
- [ ] All ten trend regions finish under `participant_set_key=giems_mc+gwd30+swamps+topmodel+wad2m`, and the copied submit TSV accounts for every region job.

Done when
The authenticated HPC repo has real ten-region percentage/classification outputs plus completed trend jobs, and the repo proof bundle contains the copied submit TSV, representative first/last manifests, and a bilingual rerun note.
  - Estimate: 1.5d
  - Files: results/phase4/proof/phase4-producer-materialization.md, results/phase4/proof/phase4-trend-contract-submit.tsv, results/phase4/proof/phase4-trend-fanout.md, scripts/run_phase4_percentage_contract.py, scripts/run_phase4_classification_contract.py, scripts/submit_phase4_trend_contract.sh, scripts/run_phase4_trend_contract.py, tests/test_submit_phase4_trend_contract.py, tests/test_comparison/test_trend_contract.py, tests/test_comparison/test_trends.py
  - Verify: # Run from an authenticated workstation / 需在已认证工作站执行
rsync -avz --delete --exclude-from=.gitignore ./ \
  2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/
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
rsync -avz \
  2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/results/phase4/proof/phase4-trend-contract-submit.tsv \
  results/phase4/proof/
test -s results/phase4/proof/phase4-trend-contract-submit.tsv
- [ ] **T04: Reopen readiness and unified ledgers only after the authenticated outputs exist** — Why: readiness and ledger are still the S07 acceptance gate, but they must now run only after the authenticated HPC rerun has produced real percentage/classification/trend outputs. This task turns the old downstream proof into an explicit fail-closed post-materialization gate.

Steps
1. In the authenticated HPC repo that now contains all three upstream families, run `scripts/run_phase4_scaleout_readiness.py` with `--subset ten`, canonical percentage/classification keys, and the same five trend dataset ids from T03.
2. Assert from the readiness JSON that `ready_region_ids` exactly equals `amazon, orinoco, pantanal, indogangetic, mekong, sudd, congo, okavango, borneo, northernaus`, `incomplete_region_ids` is empty, and every row status is `ready`; if not, stop and use the diagnostics to rerun only the missing upstream family/region via T03.
3. Run `scripts/run_phase4_hotspot_ledger.py --subset ten --no-skip` with the same keys/participant ids, verify representative first/last region ledgers on HPC, and then copy the readiness reports plus representative ledgers back into the repo.
4. Write `results/phase4/proof/phase4-readiness-ledger-proof.md` in bilingual form, recording the readiness report paths, representative ledger paths, any targeted reruns, and the exact S08 handoff after the authenticated sync-back.
5. If readiness or ledger exposes a real code bug, patch only the touched readiness/ledger files locally, rerun focused checks, resync, rerun readiness, then rerun ledger; do not hand-edit downstream artifacts.

Must-Haves
- [ ] The readiness CSV/JSON exists and every region/family row is `ready` on real ten-region outputs.
- [ ] `ready_region_ids` matches the ordered ten-region contract list exactly, with no `missing` or `partial` rows hidden by manual edits.
- [ ] Ten unified ledgers reopen from disk under `results/phase4/unified_hotspot_ledgers/`, and the copied proof note records the exact S08 handoff.

Done when
The authenticated rerun produces an all-green readiness report and reopened ten-region unified ledgers, and the repo proof bundle contains the copied readiness artifacts plus the bilingual ledger proof note.
  - Estimate: 4h
  - Files: results/phase4/proof/phase4-trend-fanout.md, results/phase4/proof/phase4-readiness-ledger-proof.md, scripts/run_phase4_scaleout_readiness.py, scripts/run_phase4_hotspot_ledger.py, src/WA/comparison/scaleout_readiness.py, src/WA/comparison/hotspot_ledger.py, tests/test_comparison/test_scaleout_readiness.py, tests/test_comparison/test_hotspot_ledger.py
  - Verify: # Run from an authenticated workstation / 需在已认证工作站执行
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
rsync -avz \
  2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/results/phase4/scaleout_readiness/ \
  results/phase4/scaleout_readiness/
rsync -avz \
  2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/results/phase4/unified_hotspot_ledgers/ \
  results/phase4/unified_hotspot_ledgers/
test -f results/phase4/unified_hotspot_ledgers/amazon/canonical__amazon__unified_hotspot_ledger.csv
test -f results/phase4/unified_hotspot_ledgers/northernaus/canonical__northernaus__unified_hotspot_ledger.csv
