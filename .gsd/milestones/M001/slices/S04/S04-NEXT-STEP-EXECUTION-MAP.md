# S04 Next-Step Execution Map

Framing rule: treat `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` as the route-truth input and `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` as the proof-boundary input. This S04 artifact sequences those two inputs into one operator ladder; it does not replace either source.

## Canonical Read Order

1. Route truth first: read `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` all the way through, with special attention to `## Current Recommended Routes`, `## Historical/Stale or Misleading Routes`, `## Risk Register`, and `## Requirement Coverage`.
2. Proof boundary second: read `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`, specifically the `Phase 4 current Stage-1 / Stage-2 route` row and `## Open Proof Gaps`.
3. Only after those two documents agree in your head should you touch the live entry scripts below: `scripts/build_phase4_gwd30_pixel_stats.py`, `scripts/submit_phase4_gwd30_pixel_stats.sh`, `scripts/run_phase4_regional.py`, and `scripts/hpc_probe_trends.py`.

## Ordered Continuation Path

1. Narrow Stage-1 proof first. Do not start with the broad submit wrapper.

   ```bash
   python scripts/build_phase4_gwd30_pixel_stats.py \
     --year 2016 \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --aggregation monthly \
     --worker-count 1 \
     --no-skip
   ```

2. Narrow Stage-2 proof second. Keep the time window aligned with the Stage-1 manifest you just built, and keep the region narrow.

   ```bash
   python scripts/run_phase4_regional.py \
     --dataset-id gwd30 \
     --region amazon \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --start-year 2016 \
     --end-year 2016 \
     --no-skip
   ```

3. Widen Stage 1 only after the narrow 2016 proof passes. If you need the batch wrapper, make the year fanout explicit instead of relying on defaults.

   ```bash
   bash scripts/submit_phase4_gwd30_pixel_stats.sh \
     --years 2013,2014,2015,2016,2017,2018,2019,2020,2021,2022 \
     --aggregation monthly \
     --worker-count 1 \
     --cpus 1 \
     --time 480 \
     --partition C064M0256G \
     --no-skip
   ```

4. Widen Stage 2 only after `gwd30` + `amazon` + `2016-2016` is clean. Keep `gwd30` explicit and extend the time range before you widen datasets or regions.

   ```bash
   python scripts/run_phase4_regional.py \
     --dataset-id gwd30 \
     --region amazon \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --start-year 2013 \
     --end-year 2022 \
     --no-skip
   ```

5. Supporting diagnostic lane only after the current mainline is freshly re-proven. `scripts/hpc_probe_trends.py` is still useful, but it is not the continuation mainline.

   ```bash
   python scripts/hpc_probe_trends.py \
     --dataset-id gwd30 \
     --aggregation annual \
     --bbox -65 -20 -45 5 \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --json-out results/phase4/probe_gwd30_annual.json
   ```

## Proof Targets / Exit Criteria

Stage-1 proof is clean only when all of the following are true:

- `scripts/build_phase4_gwd30_pixel_stats.py` finished on `--year 2016 --no-skip`.
- `results/phase4/pixel_stats/gwd30/gwd30_2016/monthly/tile_manifest.json` exists.
- The manifest points at real `results/phase4/pixel_stats/gwd30/gwd30_2016/monthly/tiles/tile_*.nc` files.
- The Stage-1 log contains `Phase4 cache write: gwd30_native_pixel_stats`.

Stage-2 proof is clean only when all of the following are true:

- `scripts/run_phase4_regional.py` finished for `--dataset-id gwd30 --region amazon --start-year 2016 --end-year 2016 --no-skip`.
- `results/phase4/cache/masks/berkeley_valid/amazon_2016_2016.nc` exists.
- `results/phase4/cache/gwd30/amazon/regional_series.csv` exists.
- `results/phase4/tables/amazon.csv` exists.
- `results/phase4/tables/amazon.csv` contains `series_type` rows for `monthly`, `annual`, and `climatology`.

Do not treat the current route as freshly re-proven on HPC until both the Stage-1 and Stage-2 proof targets above are present.

## Do Not Touch First

Historical or stale route family to avoid at the start:

- `scripts/submit_phase4_gwd30_tropical_shards.sh`
- `scripts/build_phase4_gwd30_shard_lists.py`
- `scripts/run_phase4_gwd30_tropical_shard.py`
- `scripts/reduce_phase4_gwd30_tropical_shards.py`

Missing route to avoid planning around:

- `scripts/run_phase4_trend_analysis.py` is not present in this worktree, so do not assume a broad batch trend-analysis runner already exists.

Broad default invocations that silently fan out and should not be your first move:

- `python scripts/build_phase4_gwd30_pixel_stats.py`
- `bash scripts/submit_phase4_gwd30_pixel_stats.sh`
- `python scripts/run_phase4_regional.py`

Stale flags from older stash notes that do not belong on the current CLI surfaces:

- `--berkeley-raw-path`
- `--phase36-cache-dir`
- `--gwd30-cache-dir`
- `--gwd30-worker-count`

Current-route reminder: the safe first rung is `scripts/build_phase4_gwd30_pixel_stats.py` for `--year 2016 --no-skip`, then `scripts/run_phase4_regional.py` for `--dataset-id gwd30 --region amazon --start-year 2016 --end-year 2016 --no-skip`, and only then any broader wrapper or wider time range.

## Requirement Coverage

- **R006** — This artifact is the validation surface for the milestone’s next-step execution contract because it consolidates the canonical read order, the ordered continuation path, the exact proof targets, and the avoid-first guardrails into one ordered map. The validation is about continuation clarity and execution order; it does **not** claim that the fresh HPC rerun already happened.
- **R003** — Inherited and preserved by sequencing the S03 route-truth judgment into a concrete operator ladder. This document does not re-argue which route is current; it operationalizes the S03 conclusion that the safe current chain is Stage 1 pixel stats first and Stage 2 regional tables second.
- **R005** — Inherited and preserved by keeping the proof-gap boundary explicit. The Stage-1 and Stage-2 proof targets above define what must exist before the route counts as freshly re-proven, and the map explicitly keeps the HPC-only rerun gap open until those artifacts are produced.
