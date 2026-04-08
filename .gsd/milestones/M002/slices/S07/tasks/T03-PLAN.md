---
estimated_steps: 12
estimated_files: 8
skills_used:
  - hpc-analyze
  - sync-hpc
---

# T03: Submit and monitor the ten-region trend fanout to completion

Why: the trend line is the only leg with one-region-per-job fanout and checkpointed rerun semantics, so it needs its own monitored operational boundary.

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

## Inputs

- `results/phase4/proof/phase4-ten-region-command-ladder.md`
- `results/phase4/proof/phase4-trend-contract-dry-run.tsv`
- `scripts/submit_phase4_trend_contract.sh`
- `scripts/run_phase4_trend_contract.py`
- `src/WA/comparison/trends.py`
- `src/WA/comparison/trend_contract.py`

## Expected Output

- `results/phase4/proof/phase4-trend-contract-submit.tsv`
- `results/phase4/trend_hotspot_manifests/amazon/giems_mc+gwd30+swamps+topmodel+wad2m__amazon__trend_hotspot_manifest.json`
- `results/phase4/trend_hotspot_manifests/northernaus/giems_mc+gwd30+swamps+topmodel+wad2m__northernaus__trend_hotspot_manifest.json`
- `results/phase4/proof/phase4-trend-fanout.md`

## Verification

bash scripts/submit_phase4_trend_contract.sh \
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
