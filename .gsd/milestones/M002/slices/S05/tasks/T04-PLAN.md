---
estimated_steps: 24
estimated_files: 7
skills_used: []
---

# T04: Restore trend surface writes and add checkpointed HPC submit fanout

Current `scripts/run_phase4_trend_contract.py` only persists agreement/hotspot artifacts and still recomputes region-scoped trend inputs from staged tiles for each run. S05 must restore the missing per-dataset trend surface/summary writes and add a resumable submit/checkpoint path before any ten-region trend proof is credible.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/trends.py`, staged GWD30 manifests, `src/WA/comparison/trend_agreement.py`, and the new submit wrapper | Fail with stage, `dataset_id`, `region_id`, and participant-set context; never treat a half-written checkpoint or partial artifact pair as reusable. | Resume at the region/dataset boundary through explicit checkpoint and submit surfaces instead of recomputing the whole ladder. | Reject malformed participant keys, missing staged tiles, mixed checkpoint metadata, or invalid submit arguments instead of silently broadening or reusing bad state. |

## Load Profile

- **Shared resources**: staged GWD30 tile manifests, trend checkpoint caches, trend NetCDF/CSV outputs, and one submit-summary surface per fanout run.
- **Per-operation cost**: one trend surface load/checkpoint plus Mann-Kendall write per dataset×region, then one agreement/hotspot pass per region.
- **10x breakpoint**: staged-tile I/O and agreement stacking become the first wall-time bottleneck when the canonical subset widens to all ten regions.

## Negative Tests

- **Malformed inputs**: missing staged GWD30 manifests, bad participant ids, mixed checkpoint metadata, and illegal submit-script flag combinations.
- **Error paths**: partial checkpoints, missing trend output files, or empty agreement overlap windows must surface explicit failures with region/dataset context.
- **Boundary conditions**: dataset-id order differences, `amazon → canonical → ten` widening, and `--repo` / `--no-skip` submit generation remain deterministic.

## Steps

1. Add `src/WA/comparison/trend_contract.py` to write and semantically reload per-dataset `trend_surface` and `trend_regional_summary` artifacts keyed by dataset id + region, keeping participant-set handling only for agreement/hotspot families.
2. Extend `src/WA/comparison/trends.py` and `scripts/run_phase4_trend_contract.py` so wide runs can write and reuse explicit region/dataset/time-window checkpoints before agreement, with logs that distinguish compute vs reload and with `--subset ten` using the shared selector.
3. Add `scripts/submit_phase4_trend_contract.sh` to fan out one region per job on HPC with explicit `--repo`, `--no-skip`, participant dataset lists, and summary-file output instead of relying on ad hoc manual command editing.
4. Add `tests/test_comparison/test_trend_contract.py`, extend `tests/test_comparison/test_trends.py`, and add `tests/test_submit_phase4_trend_contract.py` covering checkpoint writes/reloads, per-dataset trend outputs, invalid participant sets, and generated SLURM commands.

## Must-Haves

- [ ] The trend line regains real contract-backed `trend_surface` and `trend_regional_summary` outputs in addition to the existing agreement/hotspot families.
- [ ] Trend wide runs can resume from explicit region/dataset checkpoints instead of recomputing everything after one failure.
- [ ] The trend submit wrapper makes `--repo` and `--no-skip` explicit so operators do not silently fall back to stale defaults like `$HOME/repos/WA2`.

## Done when

- The trend contract runner can materialize per-dataset trend surfaces/summaries plus agreement/hotspot families for one region and `--subset ten`, and the new submit wrapper plus focused tests prove the ladder is resumable and HPC-safe.

## Inputs

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/trends.py`
- `src/WA/comparison/trend_agreement.py`
- `scripts/run_phase4_trend_contract.py`
- `scripts/hpc_probe_trends.py`

## Expected Output

- `src/WA/comparison/trend_contract.py`
- `src/WA/comparison/trends.py`
- `scripts/run_phase4_trend_contract.py`
- `scripts/submit_phase4_trend_contract.sh`
- `tests/test_comparison/test_trend_contract.py`
- `tests/test_comparison/test_trends.py`
- `tests/test_submit_phase4_trend_contract.py`

## Verification

ruff check src/WA/comparison/trend_contract.py src/WA/comparison/trends.py scripts/run_phase4_trend_contract.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_submit_phase4_trend_contract.py
bash -n scripts/submit_phase4_trend_contract.sh
python scripts/run_phase4_trend_contract.py --help
python -m pytest tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_submit_phase4_trend_contract.py -q

## Observability Impact

Expose `stage=trend-load`, `stage=trend-write`, `stage=agreement`, `stage=trend-hotspots`, and checkpoint `action=compute|reload` logs plus one submit summary file so long ten-region reruns can be diagnosed without reopening raw SLURM scripts.
