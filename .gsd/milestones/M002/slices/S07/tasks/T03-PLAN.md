---
estimated_steps: 13
estimated_files: 10
skills_used: []
---

# T03: Run the authenticated HPC producer/trend bundle and sync back proof artifacts

Why: T02 proved the remaining work cannot be completed from this auto-mode container because the real ten-region inputs live behind OTP-gated HPC access. This task converts the rest of S07 into an authenticated-session execution boundary instead of pretending the missing percentage/classification families already exist.

## Execution Override
- Override `2026-04-09T03:32:26.852Z` has been applied and resolved in `.gsd/OVERRIDES.md`.
- Per D053 (superseding D052's temporary active-override note), auto-mode should carry this task through local prep, proof bookkeeping, and any code-fix loop, but it must stop at the OTP-authenticated HPC boundary instead of pretending the remote run is container-executable.
- If the authenticated HPC run exposes a real code defect, return to local auto-mode for the focused fix/test/resync cycle, then rerun only the failed family or region jobs.

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

## Inputs

- `results/phase4/proof/phase4-ten-region-command-ladder.md`
- `results/phase4/proof/phase4-trend-contract-dry-run.tsv`
- `results/phase4/proof/phase4-producer-materialization.md`
- `docs/stashes/2026-04-09-021-m002-s07-t02-producer-materialization-blocked.md`
- `scripts/run_phase4_percentage_contract.py`
- `scripts/run_phase4_classification_contract.py`
- `scripts/submit_phase4_trend_contract.sh`
- `scripts/run_phase4_trend_contract.py`

## Expected Output

- `results/phase4/proof/phase4-trend-contract-submit.tsv`
- `results/phase4/proof/phase4-trend-fanout.md`
- `results/phase4/hotspot_manifests/amazon/canonical__amazon__hotspot_manifest.json`
- `results/phase4/hotspot_manifests/northernaus/canonical__northernaus__hotspot_manifest.json`
- `results/phase4/classification_hotspot_manifests/amazon/canonical__amazon__classification_hotspot_manifest.json`
- `results/phase4/classification_hotspot_manifests/northernaus/canonical__northernaus__classification_hotspot_manifest.json`
- `results/phase4/trend_hotspot_manifests/amazon/giems_mc+gwd30+swamps+topmodel+wad2m__amazon__trend_hotspot_manifest.json`
- `results/phase4/trend_hotspot_manifests/northernaus/giems_mc+gwd30+swamps+topmodel+wad2m__northernaus__trend_hotspot_manifest.json`

## Verification

# Run from an authenticated workstation / 需在已认证工作站执行
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

## Observability Impact

- Signals added/changed: wrapper stdout plus per-job `job.<id>.out/err` logs, `stage=trend-load`, `stage=trend-write`, agreement, and hotspot logs remain the primary runtime diagnostics.
- How a future agent inspects this: start from `results/phase4/proof/phase4-trend-contract-submit.tsv`, then inspect the matching SLURM logs and representative `results/phase4/trend_hotspot_manifests/` files.
- Failure state exposed: stalled or failed regions remain visible by job id, copied submit summary, and region-scoped checkpoint/output paths rather than disappearing inside one wide batch run.

## Failure Modes

- **Dependencies**: `scripts/submit_phase4_trend_contract.sh`, `scripts/run_phase4_trend_contract.py`, trend checkpoints under `results/phase4`, SLURM queue health, and the five participant datasets.
- **On error**: inspect the copied submit summary and job logs, patch only the touched trend/wrapper code if needed, rerun focused tests, then resubmit only failed region(s).
- **On timeout**: keep monitoring at the region/job boundary rather than restarting all ten regions; checkpoint reuse is the planned timeout recovery surface.
- **On malformed response**: reject duplicate or missing participant ids, missing scripts, or partial checkpoint/output pairs instead of pretending the region succeeded.

## Load Profile

- **Shared resources**: SLURM slots, `temp` job directories, region/dataset checkpoints, and the `results/phase4/trend_*` artifact families.
- **Per-operation cost**: one SLURM job per region, each computing five dataset trends plus agreement/hotspots.
- **10x breakpoint**: queue wait time, checkpoint I/O, and agreement stacking become the first scaling wall, so the proof bundle must preserve job ids and rerun history.

## Negative Tests

- **Malformed inputs**: missing `topmodel`, wrong `--repo`, bad `--python-bin`, duplicate `--dataset-id`, or an incomplete copied submit summary.
- **Error paths**: failed regions must stay visible by job id and log path; direct wide reruns without the wrapper are not an acceptable recovery path.
- **Boundary conditions**: one-region debug reruns, first/last region hotspot outputs, and copied submit-summary accounting for all ten regions remain stable.
