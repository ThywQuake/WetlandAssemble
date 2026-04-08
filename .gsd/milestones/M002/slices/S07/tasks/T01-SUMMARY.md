---
id: T01
parent: S07
milestone: M002
key_files:
  - scripts/submit_phase4_trend_contract.sh
  - tests/test_submit_phase4_trend_contract.py
  - results/phase4/proof/phase4-ten-region-command-ladder.md
  - results/phase4/proof/phase4-trend-contract-dry-run.tsv
  - CHANGELOG.md
  - .gsd/KNOWLEDGE.md
  - docs/stashes/2026-04-09-020-m002-s07-t01-command-ladder-dry-run.md
key_decisions:
  - Kept the fix narrow to the wrapper preflight and routed region resolution through the explicit `--python-bin`.
  - Preserved the frozen S07 execution contract: `--subset ten`, canonical percentage/classification keys, and the five-dataset trend set including `topmodel`.
duration: 
verification_result: passed
completed_at: 2026-04-08T23:02:32.359Z
blocker_discovered: false
---

# T01: Fixed the trend submit preflight to use the repo interpreter and froze the ten-region Phase 4 command ladder with a copied dry-run proof bundle.

**Fixed the trend submit preflight to use the repo interpreter and froze the ten-region Phase 4 command ladder with a copied dry-run proof bundle.**

## What Happened

Reloaded the S07 slice/task contract, recent S07 stash notes, and the current project/requirement context, then verified from the live Phase 4 runners that the intended wide-run contract still centers on `--subset ten`, canonical percentage/classification keys, and the five-dataset trend set `gwd30, giems_mc, topmodel, swamps, wad2m`.

The local preflight shell/help surface passed, but the required trend-wrapper `--dry-run` failed before any job scripts were generated with `ModuleNotFoundError: No module named 'numpy'` plus `No regions resolved for submission.` Reading `scripts/submit_phase4_trend_contract.sh` showed that `resolve_region_ids()` was hardwired to `python3`, so it ignored the explicit `--python-bin` already supplied by the wrapper. I fixed that narrow preflight path to use the selected repo interpreter, updated `tests/test_submit_phase4_trend_contract.py` with a regression covering this interpreter-selection behavior, and reran the touched shell/help/pytest surface.

After the fix, the dry-run resolved the full ordered ten-region list, printed the five frozen dataset ids including `topmodel`, kept `Skip mode: --no-skip` visible, and generated one submit script per region. I copied the generated summary TSV to `results/phase4/proof/phase4-trend-contract-dry-run.tsv`, wrote `results/phase4/proof/phase4-ten-region-command-ladder.md` in bilingual form with the frozen region order / keys / exact HPC follow-up commands, and also updated `CHANGELOG.md`, `.gsd/KNOWLEDGE.md`, and a compact stash note for future re-entry.

## Verification

Verified `bash -n` on the wrapper, all five Phase 4 CLI `--help` surfaces, focused wrapper pytest coverage after the shell-script fix, the real trend-wrapper dry-run with explicit repo/python/std-root/jobs dirs, and the existence of `results/phase4/proof/phase4-trend-contract-dry-run.tsv`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/submit_phase4_trend_contract.sh` | 0 | ✅ pass | 1ms |
| 2 | `python scripts/run_phase4_percentage_contract.py --help` | 0 | ✅ pass | 1264ms |
| 3 | `python scripts/run_phase4_classification_contract.py --help` | 0 | ✅ pass | 1199ms |
| 4 | `python scripts/run_phase4_trend_contract.py --help` | 0 | ✅ pass | 1048ms |
| 5 | `python scripts/run_phase4_scaleout_readiness.py --help` | 0 | ✅ pass | 1210ms |
| 6 | `python scripts/run_phase4_hotspot_ledger.py --help` | 0 | ✅ pass | 1227ms |
| 7 | `python -m pytest tests/test_submit_phase4_trend_contract.py -q` | 0 | ✅ pass | 2291ms |
| 8 | `bash scripts/submit_phase4_trend_contract.sh --dry-run --repo "$PWD" --python-bin "$PWD/.venv/bin/python" --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --subset ten --dataset-id gwd30 --dataset-id giems_mc --dataset-id topmodel --dataset-id swamps --dataset-id wad2m --aggregation annual --start-year 1990 --end-year 2020 --min-observations 5 --min-overlap-years 5 --top-hotspots 10 --cpus 2 --time 480 --partition C064M0256G --jobs-base temp/slurm-jobs-s07 --tmp-root temp/slurm-tmp-s07 --no-progress` | 0 | ✅ pass | 1071ms |
| 9 | `test -s results/phase4/proof/phase4-trend-contract-dry-run.tsv` | 0 | ✅ pass | 0ms |

## Deviations

None beyond the plan-allowed wrapper fix triggered by the failed preflight dry-run.

## Known Issues

None within T01. Real ten-region producer/readiness/ledger materialization remains the planned HPC-only work for T02-T04.

## Files Created/Modified

- `scripts/submit_phase4_trend_contract.sh`
- `tests/test_submit_phase4_trend_contract.py`
- `results/phase4/proof/phase4-ten-region-command-ladder.md`
- `results/phase4/proof/phase4-trend-contract-dry-run.tsv`
- `CHANGELOG.md`
- `.gsd/KNOWLEDGE.md`
- `docs/stashes/2026-04-09-020-m002-s07-t01-command-ladder-dry-run.md`
