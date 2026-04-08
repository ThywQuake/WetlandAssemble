# 2026-04-09 M002/S07 research quick reference

## What was established
- S07 is an **execution/proof** slice, not a new contract or pack-code slice.
- The live ten-region order is:
  - `amazon, orinoco, pantanal, indogangetic, mekong, sudd, congo, okavango, borneo, northernaus`
- The real acceptance ladder is:
  1. `run_phase4_percentage_contract.py --subset ten --no-skip`
  2. `run_phase4_classification_contract.py --subset ten --no-skip`
  3. `submit_phase4_trend_contract.sh --subset ten ... --no-progress`
  4. `run_phase4_scaleout_readiness.py --subset ten ...`
  5. `run_phase4_hotspot_ledger.py --subset ten ... --no-skip`
- S07 should stop at real producer outputs + all-green readiness + ten reopened ledgers.
- Strict pack proof remains the S08 boundary.

## Current repo reality
- `results/phase4/` only contains the existing `amazon` readiness report.
- That readiness report marks percentage / classification / trend as `missing`.
- `results/figures/phase4_pack/` does not exist locally.

## Key alignment rules
- Keep `percentage_key=canonical`.
- Keep `classification_key=canonical`.
- Keep the trend participant set exactly:
  - `gwd30, giems_mc, topmodel, swamps, wad2m`
- That trend set sorts to:
  - `giems_mc+gwd30+swamps+topmodel+wad2m`
- Do not change keys/datasets unless readiness, ledger, and later strict pack proof are all updated together.

## Files refreshed
- `.gsd/milestones/M002/slices/S07/S07-RESEARCH.md`
- `.gsd/milestones/M002/M002-VALIDATION.md` (re-rendered so the validation artifact exists on disk again)

## Verification status
- `gsd_summary_save` for S07 research ✅
- `gsd_validate_milestone` re-run for M002 ✅
- `.gsd/milestones/M002/M002-VALIDATION.md` now exists on disk ✅

## Main risks / TODOs
1. Use the explicit HPC standardized path: `/lustre/home/2200013429/Wetland_Assemble/data/standardized`.
2. Use `--no-skip` for real proof runs.
3. Run trend wrapper dry-run once before submit if there is any doubt about job scripts.
4. Treat readiness as the acceptance gate; do not infer success from file counts alone.
5. Use the auto-written readiness diagnostics to target reruns if ledger fails.
