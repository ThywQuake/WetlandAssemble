# M002/S07 Research — Ten-region HPC materialization and readiness/ledger proof

## Summary

S07 is an **operational materialization + proof** slice, not a new contract-design slice.

The code surfaces S07 needs already exist from S05/S06:
- ordered region selection in `src/WA/comparison/evidence_contract.py`
- producer CLIs for percentage / classification / trend
- the trend SLURM fanout wrapper in `scripts/submit_phase4_trend_contract.sh`
- semantic readiness inspection in `src/WA/comparison/scaleout_readiness.py`
- fail-closed unified-ledger generation in `src/WA/comparison/hotspot_ledger.py`

What is still missing is the **real ten-region runtime proof** on HPC.

Current repo reality is still the same gap that triggered the remediation split:
- `results/phase4/` currently contains only one readiness report for `amazon`
- that report marks **percentage / classification / trend all `missing`**
- `results/figures/phase4_pack/` does not exist locally

So S07 should be planned as: **materialize the ten real producer outputs, prove readiness is all-green, then build/reopen the ten unified ledgers**. S07 should stop there. The strict paper-pack claim stays in S08.

This slice primarily retires the runtime/proof part of:
- **R102** — ten-region percentage outputs must exist materially
- **R103** — ten-region classification outputs must exist materially
- **R104** — ten-region trend outputs must exist materially
- **R105** — unified ledgers must reopen on real outputs, not only fixtures
- **R107** — the wide run must be reproducible through the explicit producer -> readiness -> ledger ladder

It also prepares **R113** by generating the real science inputs S08 will need for the strict pack proof.

## Requirement Focus

### Primary
- **R102** — materialize the contract-backed percentage family across the ordered ten-region set.
- **R103** — materialize the contract-backed classification family across the ordered ten-region set.
- **R104** — materialize the trend/agreement/hotspot family across the ordered ten-region set.
- **R105** — prove the unified hotspot ledger reopens cleanly on real ten-region outputs.
- **R107** — close the operational proof boundary using explicit resumable HPC-safe execution surfaces.

### Supporting
- **R113** — S07 should keep keys/participant sets aligned so S08 can run `run_phase4_evidence_pack.py --strict` without another producer rerun.

## Skill Discovery (suggest only)

No installed skill list was exposed in-context. Directly relevant external skills that looked useful:

- **SLURM / HPC**
  - `npx skills add serendipityoneinc/srp-claude-code-marketplace@slurm`
  - `npx skills add heshamfs/materials-simulation-skills@slurm-job-script-generator`
- **xarray**
  - `npx skills add tondevrel/scientific-agent-skills@xarray`
  - `npx skills add steadfastasart/geoscience-skills@xarray`

S07 can probably execute with existing repo patterns, but the SLURM skill is the most directly relevant if the executor needs help debugging fanout or job-script issues on HPC.

## Implementation Landscape

### 1. `EvidenceContract` is already the single owner of the ten-region run set

**File:** `src/WA/comparison/evidence_contract.py`

Current ordered selectors from live code:
- `canonical = ('amazon', 'pantanal', 'sudd', 'borneo')`
- `ten = ('amazon', 'orinoco', 'pantanal', 'indogangetic', 'mekong', 'sudd', 'congo', 'okavango', 'borneo', 'northernaus')`

Planner implication:
- do **not** hand-write ten region lists in task plans or scripts
- every wide producer / readiness / ledger step should keep using `--subset ten`
- keep family keys stable so downstream proof surfaces resolve the same artifacts semantically

Important nuance:
- the producer CLIs default to `canonical` when neither `--subset` nor `--region` is passed
- the trend submit wrapper defaults to `ten` when neither `--subset` nor `--region` is passed
- for S07, make `--subset ten` explicit everywhere so the run intent is visible in logs and summaries

### 2. Percentage wide-run surface already exists and should be reused as-is

**Files:**
- `scripts/run_phase4_percentage_contract.py`
- `src/WA/comparison/percentage_backbone.py`
- `src/WA/comparison/percentage_hotspots.py`

What it does:
- resolves one region / canonical / ten through the contract
- writes one contract `surface` bundle, one `regional_summary`, and one hotspot manifest/CSV pair per region
- default dataset bundle is the `canonical` six-dataset family:
  - `gwd30`
  - `giems_mc`
  - `topmodel`
  - `swamps`
  - `wad2m`
  - `berkeley_rwawc`
- default `dataset_key` stays `canonical` when the default bundle is used

Planner implication:
- **do not override dataset ids** unless you are prepared to propagate a different `dataset_key` into readiness, ledger, and later pack proof
- safest S07 path is to keep the default bundle and therefore keep `percentage_key=canonical`
- S06 handoff already assumes a paper-usable percentage summary window, so S07 should materialize percentage with:
  - `--surface-year 2016`
  - `--start-year 1990`
  - `--end-year 2020`
  - `--no-skip`

That is slightly broader than the narrowest S05 infrastructure proof, but it prevents S08 from needing an immediate percentage rerun just to build interannual outputs.

### 3. Classification wide-run is intentionally a thin adapter over Phase 3.6 / 3.7

**Files:**
- `scripts/run_phase4_classification_contract.py`
- `src/WA/comparison/classification_contract.py`

What it does:
- keeps Phase 3.6 as the disagreement producer and Phase 3.7 as the hotspot-source producer
- rewrites those outputs into contract-scoped:
  - `classification_surface`
  - `classification_regional_summary`
  - `classification_hotspot_manifest` + CSV
- fixed classification family identity is:
  - `classification_key=canonical`
  - participant set `g2017+glwd_v2+gwd30`

Planner implication:
- do not invent a separate classification rewrite path for S07
- one `--subset ten --no-skip` run through the existing CLI is the intended materialization surface
- use the explicit HPC standardized dir and the explicit Phase 3.6 / 3.7 dirs from the S05/S06 handoff

### 4. Trend wide-run is split correctly into checkpoints + per-region SLURM fanout

**Files:**
- `scripts/run_phase4_trend_contract.py`
- `src/WA/comparison/trends.py`
- `src/WA/comparison/trend_contract.py`
- `scripts/submit_phase4_trend_contract.sh`

What it does:
- one region at a time, per participant dataset, it materializes resumable checkpoints under `results/phase4/trend_checkpoints/...`
- then writes stable downstream contract artifacts:
  - per-dataset `trend_surface`
  - per-dataset `trend_regional_summary`
  - participant-set `trend_agreement_surface`
  - participant-set `trend_agreement_summary`
  - participant-set `trend_hotspot_manifest` + CSV
- the wrapper generates **one job per region** and always passes `--no-skip`
- it also writes a summary TSV with region / job name / job id / script path

Live default trend participant set from current code and readiness/ledger defaults:
- `('gwd30', 'giems_mc', 'topmodel', 'swamps', 'wad2m')`
- participant-set key becomes `giems_mc+gwd30+swamps+topmodel+wad2m`

Planner implication:
- keep the participant set **exactly aligned** across trend run, readiness, ledger, and later pack proof
- older prose in the repo mentioned a smaller trend set, but current code/readiness/ledger defaults **include `topmodel`**; S07 should follow current code, not stale text
- do a wrapper `--dry-run` first if there is any doubt about the job scripts, then submit the real fanout

### 5. Readiness is the real S07 proof gate, not file counting

**Files:**
- `scripts/run_phase4_scaleout_readiness.py`
- `src/WA/comparison/scaleout_readiness.py`

What it actually checks:
- percentage family semantic reload
- classification family semantic reload
- trend family semantic reload
- expected manifest/table/surface/summary paths for each region × family

Important semantics from live code:
- `status=ready` only when semantic reload succeeds for the hotspot manifest/table pair **and** provenance outputs
- `status=missing` only when both manifest and CSV are absent
- `status=partial` when the pair is incomplete **or** semantic reload fails

Planner implication:
- S07 completion must require **all rows `ready`** for all ten regions
- do not accept “files exist” as enough proof
- the deterministic report under `results/phase4/scaleout_readiness/` is a required proof artifact for this slice

Current local evidence confirms the gap:
- `results/phase4/scaleout_readiness/regions-amazon__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json`
- shows `ready_region_ids=[]`
- and all three families missing for `amazon`

### 6. Unified ledger is the final S07 integration closure

**Files:**
- `scripts/run_phase4_hotspot_ledger.py`
- `src/WA/comparison/hotspot_ledger.py`

What it does:
- semantically reopens the percentage, classification, and trend hotspot families
- normalizes them into one long-form ledger keyed by stable `analysis_object_id`
- writes one CSV per region under `results/phase4/unified_hotspot_ledgers/<region>/...`
- fails closed if any family is missing or malformed
- auto-writes a single-region readiness report when a ledger build fails

Planner implication:
- readiness is the preflight; ledger is the final S07 integration proof
- the slice is not done until ledger succeeds across the full ten-region selector
- failed ledgers should be debugged from the auto-written readiness report, not by hand-editing artifacts

Expected family identity for S07 proof:
- `ledger_key=canonical`
- `percentage_key=canonical`
- `classification_key=canonical`
- `trend_participant_set_key=giems_mc+gwd30+swamps+topmodel+wad2m`

### 7. S08 starts only after S07 produces real science outputs + ledgers

**Files already waiting downstream:**
- `scripts/run_phase4_evidence_pack.py`
- `src/WA/visualization/phase4_pack.py`

Planner implication:
- S07 should **not** spend context on new pack logic
- S07 should focus on creating the real producer/readiness/ledger inputs that S08 will consume with `--strict`
- the only S08 concern S07 needs to remember is key alignment: if S07 changes dataset keys or participant ids, S08 proof will fail selector checks

## Don’t Hand-Roll

1. **Don’t change dataset ids or keys casually.** If you change them, readiness, ledger, and strict pack proof must all be updated to match. Safest path is the existing defaults.
2. **Don’t infer success from file existence.** Use the readiness CSV/JSON and semantic ledger reopen as the completion signal.
3. **Don’t bypass the trend submit wrapper for wide proof.** Use direct `run_phase4_trend_contract.py` only for one-region debugging.
4. **Don’t claim S07 complete from one-region proof.** `amazon` is only a useful smoke/debug surface; the slice owns the full ordered ten-region set.
5. **Don’t use git on HPC.** Per project rules, sync via `rsync`, not git push/pull.
6. **Don’t use `--skip` for the proof run.** S07 is specifically the real materialization/proof slice; use `--no-skip`.
7. **Don’t run the strict paper pack as S07’s closeout.** That remains the explicit S08 boundary.

## Recommended Slice Decomposition

### Task seam 1 — HPC preflight and selector/key freeze

Why first:
- this is the cheapest way to catch drift before launching wide jobs
- it locks the exact family keys the later proof steps must use

Likely files touched (if any runtime bug appears):
- `scripts/submit_phase4_trend_contract.sh`
- `scripts/run_phase4_percentage_contract.py`
- `scripts/run_phase4_classification_contract.py`
- `scripts/run_phase4_trend_contract.py`
- `scripts/run_phase4_scaleout_readiness.py`
- `scripts/run_phase4_hotspot_ledger.py`

Concrete goals:
- confirm the resolved ten-region order from live code
- run trend wrapper `--dry-run` and inspect the summary TSV / generated scripts
- make the command block for percentage / classification / trend / readiness / ledger explicit with the exact keys and participant ids

Output of this seam:
- one frozen command ladder the executor can run directly on HPC
- no ambiguity about keys or region order

### Task seam 2 — Materialize percentage + classification families for `--subset ten`

Why second:
- both are single-command wide producer surfaces
- readiness/ledger will otherwise fail immediately and unhelpfully

Concrete goals:
- run percentage with the paper-usable summary window (`1990..2020`) and `surface_year=2016`
- run classification with explicit Phase 3.6 / 3.7 dirs and `year=2016`
- verify at least the first completed region(s) show the expected surface / summary / hotspot outputs before declaring the producer stage healthy

Expected artifacts per region:
- percentage:
  - `surfaces/<region>/canonical__<region>__surface.nc`
  - `regional_summaries/<region>/canonical__<region>__regional_summary.csv`
  - `hotspot_manifests/<region>/canonical__<region>__hotspot_manifest.json`
  - `hotspot_manifests/<region>/canonical__<region>__hotspot_manifest.csv`
- classification:
  - `classification_surfaces/<region>/canonical__<region>__classification_surface.nc`
  - `classification_regional_summaries/<region>/canonical__<region>__classification_regional_summary.csv`
  - `classification_hotspot_manifests/<region>/canonical__<region>__classification_hotspot_manifest.json`
  - `classification_hotspot_manifests/<region>/canonical__<region>__classification_hotspot_manifest.csv`

### Task seam 3 — Submit and monitor trend fanout

Why separate:
- trend is the only leg with per-region job fanout and resumable checkpoint semantics
- it has the most HPC-specific failure modes

Concrete goals:
- run wrapper dry-run first if needed
- submit one job per region with the default five trend datasets
- retain the summary TSV path
- wait for all ten jobs to finish
- confirm checkpoint + agreement/hotspot outputs exist for each region

Expected runtime signals:
- wrapper prints the region list, dataset list, and `Skip mode: --no-skip`
- each job logs `stage=trend-load` and `stage=trend-write`
- agreement/hotspot outputs land under the contract tree with the participant-set key `giems_mc+gwd30+swamps+topmodel+wad2m`

### Task seam 4 — Readiness report + unified-ledger proof capture

Why last:
- this is the real slice acceptance surface

Concrete goals:
- run readiness for `--subset ten` with the same keys/participant ids used by the producers
- require `ready_region_ids` to equal the ten contract regions
- then run unified ledger build for `--subset ten --no-skip`
- verify ten ledger CSVs exist and reopen semantically
- retain readiness CSV/JSON plus the ten ledger paths as the S07 proof bundle for S08

This seam is where executor time should go if there are reruns. If readiness shows `missing` or `partial`, rerun the specific producer family instead of trying to repair downstream artifacts.

## Concrete Risks / Constraints

### A. Trend participant-set drift will break readiness, ledger, and S08 proof together

The default participant set in live code is:
- `gwd30`
- `giems_mc`
- `topmodel`
- `swamps`
- `wad2m`

That sorts to the participant-set key:
- `giems_mc+gwd30+swamps+topmodel+wad2m`

If the executor drops `topmodel` or uses a different participant set, the readiness and ledger steps will look for different filenames and report false incompleteness.

### B. Producer CLIs have local-ish defaults; S07 should pass the HPC paths explicitly

Important defaults drift toward local use:
- percentage/classification/trend standardized-dir defaults are not the target HPC path
- the trend wrapper default standardized dir is `$HOME/Wetland_Assemble/data/standardized`

For S07 proof, pass explicitly:
- `/lustre/home/2200013429/Wetland_Assemble/data/standardized`

### C. Current worktree has no real science outputs

The only current `results/phase4` artifacts are the `amazon` readiness CSV/JSON. That means:
- local inspection can prove gaps and filename expectations
- it cannot prove the slice
- the planner should assume HPC execution is the primary work, not a postscript

### D. Classification may be slower than it looks because it wraps Phase 3.6 / 3.7

`run_phase4_classification_contract.py` is the right surface to use, but it is still orchestrating Phase 3.6 / 3.7 inputs underneath. That is expected. Do not replace it with a hand-rolled region rewrite path just to avoid the cost.

### E. Readiness / ledger are already the debugging surfaces

The code already gives the operator the right observability:
- readiness rows tell you `ready / missing / partial`
- ledger failures print family-specific `status/path/reason`
- ledger auto-writes single-region readiness reports on failure

So if the wide proof fails, the correct recovery is:
1. inspect readiness rows
2. rerun the missing producer family with `--no-skip`
3. rerun readiness
4. rerun ledger

### F. Project rules that matter here

From `AGENTS.md` / project contract:
- use `rsync`, not git, for HPC sync
- use `--no-skip`, not `--skip-existing`, in HPC commands
- do not modify `config/` without approval
- keep progress visible for GWD30-heavy work when practical
- do not silently suppress errors or silently trust stale cache state

## Verification Strategy

### Operational verification (primary)

S07 is successful only when all of the following are true:

1. **Percentage** completes for `--subset ten` and writes the contract surface / summary / hotspot pair for every region.
2. **Classification** completes for `--subset ten` and writes the contract surface / summary / hotspot pair for every region.
3. **Trend** completes across ten SLURM jobs and writes checkpoints plus agreement/hotspot artifacts for every region.
4. **Readiness** writes a deterministic report whose `ready_region_ids` equals:
   - `amazon`
   - `orinoco`
   - `pantanal`
   - `indogangetic`
   - `mekong`
   - `sudd`
   - `congo`
   - `okavango`
   - `borneo`
   - `northernaus`
5. **Ledger** succeeds for `--subset ten --no-skip` and writes ten `unified_hotspot_ledger.csv` files.

### Useful local / code-level verification if runtime bugs force code changes

If executors have to patch code during S07, the most relevant regression surface is:

```bash
bash -n scripts/submit_phase4_trend_contract.sh
```

```bash
python -m pytest \
  tests/test_comparison/test_percentage_backbone.py \
  tests/test_comparison/test_classification_contract.py \
  tests/test_comparison/test_trend_contract.py \
  tests/test_comparison/test_trends.py \
  tests/test_comparison/test_scaleout_readiness.py \
  tests/test_comparison/test_hotspot_ledger.py \
  tests/test_submit_phase4_trend_contract.py -q
```

If selector/help behavior changes, also rerun:

```bash
python scripts/run_phase4_percentage_contract.py --help
python scripts/run_phase4_classification_contract.py --help
python scripts/run_phase4_trend_contract.py --help
python scripts/run_phase4_scaleout_readiness.py --help
python scripts/run_phase4_hotspot_ledger.py --help
```

## Suggested HPC Run Order

Sync via `rsync` first if the repo changed; do not use git on HPC.

### 1. Percentage ten-region materialization

```bash
python scripts/run_phase4_percentage_contract.py \
  --subset ten \
  --output-root results/phase4 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --surface-year 2016 \
  --start-year 1990 \
  --end-year 2020 \
  --no-skip
```

### 2. Classification ten-region materialization

```bash
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
```

### 3. Trend wrapper dry-run (recommended once before submit)

```bash
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
  --no-progress \
  --dry-run
```

### 4. Trend ten-region submit

```bash
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
```

### 5. Ten-region readiness proof

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

### 6. Ten-region unified-ledger proof

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

## Recommendation

Plan S07 as an **execution-first four-task slice**:

1. freeze the exact selector / keys / participant set and dry-run the trend wrapper
2. materialize percentage + classification for `--subset ten`
3. submit and monitor the ten trend jobs
4. run readiness and unified-ledger proof, and retain those artifacts as the slice closeout evidence

Do **not** spend planner budget on new pack logic, milestone validation logic, or ad hoc filename repair here. The repo already has the right contract, readiness, and ledger surfaces. S07’s job is to make them true on real ten-region outputs.