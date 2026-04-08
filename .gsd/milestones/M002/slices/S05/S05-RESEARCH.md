# S05 — Research

**Date:** 2026-04-09

## Summary

S05 directly owns **R107** (the ten-region analysis must be reproducible through HPC-safe cache / split / merge execution) and supports **R102** and **R106**. In practice it is also the first slice that can expose hidden gaps in **R101 / R103 / R104 / R105**, because the ten-region proof only counts if all three evidence lines still land on one contract and the unified ledger can reopen them semantically.

The main surprise is **repo reality drift**.

What is real in the current snapshot:
- a real percentage regional backbone with GWD30 Stage-1 / Stage-2 cache discipline in `src/WA/comparison/phase4_regional.py`
- real GWD30 HPC submit surfaces for Stage 1 and Stage 2:
  - `scripts/submit_phase4_gwd30_pixel_stats.sh`
  - `scripts/submit_phase4_gwd30_regional_year_split.sh`
  - `scripts/submit_phase4_gwd30_tropical_shards.sh`
- a real trend agreement + trend-hotspot runner in `scripts/run_phase4_trend_contract.py`
- a real fail-closed unified ledger in `src/WA/comparison/hotspot_ledger.py` / `scripts/run_phase4_hotspot_ledger.py`

What earlier slice docs still claim, but **does not exist** in this repo snapshot:
- `src/WA/comparison/percentage_hotspots.py`
- `scripts/run_phase4_percentage_contract.py`
- `src/WA/comparison/classification_contract.py`
- `scripts/run_phase4_classification_contract.py`
- `src/WA/comparison/trend_contract.py`

That drift matters because the ledger only **reloads** percentage / classification / trend hotspot families; it does not generate them. Current ledger / phase4 tests prove the reload and normalization logic mostly with **synthetic percentage/classification manifests**, not with a real end-to-end producer chain. So S05 cannot honestly be treated as “just add scale-out automation” until the producer-reality gap is retired.

## Recommendation

1. **Retire the producer-reality gap before ten-region automation.**
   - Recommended: restore minimal thin contract producers for the missing percentage and classification surfaces using the existing science backbones, instead of trusting stale GSD text.
   - Do **not** narrow S05 to trend-only scale-out; that would leave `R102 / R103 / R105` operationally unproven.

2. **Add one shared ten-region selector at the contract layer.**
   - `EvidenceContract.resolve_regions()` currently supports only `canonical` or explicit region ids.
   - `run_phase4_regional.py` defaults to **16** regions (6 macro regions + the 10 priority regions), so a no-arg “all regions” run is the wrong S05 target.
   - Add a stable ordered helper / subset alias for the ten contract regions and reuse it across percentage, trend, and ledger orchestration.

3. **Keep percentage scale-out on the existing split/cache/merge backbone.**
   - Reuse:
     - Stage 1: `build_phase4_gwd30_pixel_stats.py` / `submit_phase4_gwd30_pixel_stats.sh`
     - Stage 2: `submit_phase4_gwd30_regional_year_split.sh`
     - escalation path: `submit_phase4_gwd30_tropical_shards.sh` when region-year jobs are still too heavy
   - This is already the strongest in-repo HPC-safe path and best matches `R107`.

4. **Treat trend scale-out as the next true runtime risk.**
   - `run_phase4_trend_contract.py` currently recomputes region-scoped trend inputs from source loaders / staged tiles and only caches final agreement + hotspot artifacts.
   - If the amazon → canonical ladder is already expensive, add intermediate checkpointing or a submit wrapper before widening to all ten regions.

5. **Use the unified ledger as the final integration gate, not the generator.**
   - Run it only after percentage / classification / trend hotspot families are all present and validated for the same region.
   - A thin readiness/orchestration surface is more valuable here than deeper ledger refactoring.

## Project-rule constraints

These repo rules should shape the implementation plan:
- **Do not modify `config/` without approval.** Keep `config/priority_regions.yaml` read-only; add any new ten-region alias/helper in code, not by annotating config.
- **HPC deployment is rsync-based, not git-based.** Any S05 instructions should assume `rsync` to HPC and explicit `--repo`, not `git push/pull`.
- **Use `--no-skip` on first proof runs.** The project explicitly wants visible cache decisions rather than silent reuse.
- **Prefer visible progress.** Keep tqdm/progress-enabled routes when loops are long.
- **Any new HPC parallel reducer should follow the existing broad-`Exception` → serial fallback pattern** already present in `scripts/reduce_phase4_gwd30_tropical_shards.py`.

## Implementation Landscape

- `src/WA/comparison/evidence_contract.py`
  - Current owner of the contract-region list and artifact-family semantics.
  - Loads only the 10 contract regions from `config/priority_regions.yaml`.
  - Canonical subset is hard-coded as:
    - `amazon`
    - `pantanal`
    - `sudd`
    - `borneo`
  - The full 10-region set in config is:
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
  - `resolve_regions()` currently accepts only `subset="canonical"` or explicit region ids. This is the clean seam for an S05 `ten` / `all_contract` alias or a helper returning the ordered ten-region list.

- `src/WA/comparison/phase4_regional.py`
  - Real percentage backbone.
  - `compute_phase4_region_dataset_table()` routes GWD30 through `build_phase4_gwd30_monthly_series_from_pixel_stats_tiles()`; this is already a resumable Stage-1/Stage-2 design.
  - Existing HPC-safe pieces worth reusing directly:
    - `phase4_dataset_region_year_cache_path(...)`
    - `build_phase4_gwd30_monthly_series_from_pixel_stats_tiles(...)`
    - `build_phase4_gwd30_reduced_tile_index_for_staged_tiles(...)`
    - `build_or_load_phase4_gwd30_tropical_tile_cache(...)`
  - Important default mismatch: `load_phase4_regions()` adds 6 macro regions on top of the 10 priority regions. S05 should not rely on the default “all regions” behavior.

- `scripts/run_phase4_regional.py`
  - Thin regional percentage runner.
  - Supports repeated `--region` and repeated `--dataset-id`, but no contract `--subset`.
  - With no `--region`, it runs all macro + priority regions. With no `--dataset-id`, it also includes auxiliary `berkeley_rwawc`.
  - For S05, region ids and dataset ids should stay explicit.

- `scripts/build_phase4_gwd30_pixel_stats.py` + `scripts/submit_phase4_gwd30_pixel_stats.sh`
  - Concrete Stage-1 year fanout for GWD30 pixel-statistics tiles.
  - Best existing submit surface for large percentage reruns.

- `scripts/submit_phase4_gwd30_regional_year_split.sh`
  - Concrete Stage-2 per-region yearly fanout plus dependent merge job.
  - Natural operational wrapper for amazon → canonical → ten-region scale-out.
  - Important operational pitfall: default `REPO` is `$HOME/repos/WA2`, so S05 docs / orchestration should pass `--repo` explicitly after rsync.

- `scripts/build_phase4_gwd30_shard_lists.py` / `scripts/run_phase4_gwd30_tropical_shard.py` / `scripts/reduce_phase4_gwd30_tropical_shards.py` / `scripts/submit_phase4_gwd30_tropical_shards.sh`
  - Shared full-tropics shard/reduce path.
  - Good escalation route if repeated per-region year jobs are still too heavy, but note that `run_phase4_regional.py` does not call this path automatically.

- `src/WA/comparison/trends.py`
  - `build_gwd30_native_pixel_statistics_tiles()` is reusable Stage-1 infrastructure.
  - `load_trend_surface()` still loads GWD30 directly from standardized `_staging` via `merge_staged_time_fraction_tiles()` for each region/year; it does **not** reuse Stage-1 pixel-stats or regional year caches.
  - That makes trend scale-out less HPC-safe than the percentage route today.

- `scripts/run_phase4_trend_contract.py`
  - Real runner, but narrower than stale docs suggest.
  - In the current code it writes:
    - `trend_agreement_surface`
    - `trend_agreement_summary`
    - `trend_hotspot_manifest` (+ CSV companion)
  - It does **not** materialize per-dataset `trend_surface` / `trend_regional_summary` files anywhere in the current snapshot, even though those artifact kinds exist in `EvidenceContract`.
  - Supports `--subset canonical` or repeated `--region`.
  - Current default participant set is:
    - `gwd30`
    - `giems_mc`
    - `topmodel`
    - `swamps`
    - `wad2m`
  - Earlier slice docs described a narrower supported set. S05 should stabilize and document the actual supported participant set before wide reruns.

- `src/WA/comparison/trend_hotspots.py`
  - Stable contract writer / validator / reloader for trend hotspot JSON/CSV pairs.
  - Good endpoint, not the main blocker.

- `src/WA/comparison/hotspot_ledger.py` + `scripts/run_phase4_hotspot_ledger.py`
  - Good final integration gate.
  - Correctly fails closed unless percentage / classification / trend hotspot families are all present and valid for the same region.
  - Current tests create percentage / classification families synthetically via helpers like `_write_generic_hotspot_family(...)`; they do not prove a real producer chain exists in this snapshot.

- `src/WA/visualization/phase4.py`
  - The only real semantic reload helpers in this snapshot are:
    - `load_phase4_contract_trend_hotspot_table(...)`
    - `load_phase4_unified_hotspot_ledger(...)`
  - Earlier docs mention additional phase4 reload helpers that are not present.

- `src/WA/comparison/phase36.py` + `src/WA/phase37_hotspots.py`
  - Real classification science backbones still exist.
  - If S05 has to restore the missing classification contract runner / adapter, these are the upstream modules to wrap.

- `scripts/plot_tropical_wetland_025deg.py`
  - Still the live 0.25° percentage surface builder / cacher.
  - Important caveat preserved from the earlier task summary: it intentionally excludes `gwd30`.
  - If the missing percentage contract producer is restored, this script remains the non-GWD30 surface source rather than a full standalone replacement.

- **Missing but still referenced in GSD docs**
  - `src/WA/comparison/percentage_hotspots.py`
  - `scripts/run_phase4_percentage_contract.py`
  - `src/WA/comparison/classification_contract.py`
  - `scripts/run_phase4_classification_contract.py`
  - `src/WA/comparison/trend_contract.py`
  - Planner should treat these as **absent**, not as safe edit targets.

### Task-sized seams

1. **Reality-check / missing-producer recovery**
   - Highest-risk seam.
   - Decide whether S05 restores the missing percentage/classification contract surfaces or formally replans because three-line scale-out is not executable in the current snapshot.

2. **Shared ten-region selector / orchestration**
   - Small, high-leverage seam.
   - Centralize ordered contract-region resolution so all runners stop inventing their own “all regions” behavior.

3. **Percentage HPC fanout**
   - Mostly orchestration and observability around already-real Stage-1/Stage-2 split/cache/merge surfaces.

4. **Trend operational fanout**
   - Main runtime unknown.
   - Needs either explicit submission/checkpointing support or a documented proof that region-by-region recompute is acceptable.

5. **Ledger integration / readiness proof**
   - Final gate once the upstream families are materially present.

### Natural build order

1. **Producer reality gap first**
2. **Shared ten-region selector second**
3. **Percentage + trend wide-run orchestration third**
4. **Ledger integration / end-to-end proof last**

## Risks / Unknowns

- **Doc/code drift is already large.** Earlier slice summaries and `.gsd/PROJECT.md` describe several files and reload helpers that do not exist in this snapshot.
- **`run_phase4_regional.py` overshoots the target by default.** A no-arg run includes macro regions and the auxiliary Berkeley dataset, which is not the S05 target surface.
- **Trend scale-out is less HPC-safe than percentage scale-out today.** The current runner recomputes from staged/source inputs per region and only caches final agreement/hotspot artifacts.
- **Ledger end-to-end proof is still missing.** Unit tests prove reload/normalization logic, but not a real wide-run producer chain for percentage + classification.
- **Submit-script defaults are stale enough to bite operators.** In particular, multiple scripts still default `REPO` to `$HOME/repos/WA2`.
- **Trend participant-set truth is inconsistent across docs.** Current code includes `topmodel` by default; some earlier summaries said it should not.
- **Repo-wide test proof is still a boundary issue.** S04 documented unrelated full-suite trouble (`tests/test_mgrs_tiling.py` / later exit `137`), so S05 verification should keep that boundary explicit rather than hiding behind focused tests.

## Skill Suggestions

No directly relevant professional skill is already installed in `<available_skills>`.

Promising external skills, not installed:
- `npx skills add tondevrel/scientific-agent-skills@xarray` — strongest hit for the xarray-heavy reduction / artifact work (`18 installs`)
- `npx skills add serendipityoneinc/srp-claude-code-marketplace@slurm` — relevant if S05 adds or rewrites submit/orchestration surfaces (`11 installs`)

## Verification

Focused local iteration for S05 changes should stay on the Phase 4 family first:

```bash
ruff check \
  src/WA/comparison/evidence_contract.py \
  src/WA/comparison/phase4_regional.py \
  src/WA/comparison/trends.py \
  src/WA/comparison/trend_hotspots.py \
  src/WA/comparison/hotspot_ledger.py \
  src/WA/visualization/phase4.py \
  scripts/build_phase4_gwd30_pixel_stats.py \
  scripts/run_phase4_regional.py \
  scripts/run_phase4_trend_contract.py \
  scripts/run_phase4_hotspot_ledger.py \
  scripts/submit_phase4_gwd30_pixel_stats.sh \
  scripts/submit_phase4_gwd30_regional_year_split.sh \
  scripts/submit_phase4_gwd30_tropical_shards.sh
```

```bash
python -m pytest \
  tests/test_comparison/test_evidence_contract.py \
  tests/test_comparison/test_phase4_regional.py \
  tests/test_comparison/test_trends.py \
  tests/test_comparison/test_trend_agreement.py \
  tests/test_comparison/test_trend_hotspots.py \
  tests/test_comparison/test_hotspot_ledger.py \
  tests/test_visualization/test_phase4.py \
  tests/test_submit_phase4_gwd30_pixel_stats.py \
  tests/test_submit_phase4_gwd30_regional_year_split.py \
  tests/test_submit_phase4_gwd30_tropical_shards.py -q
```

If submit scripts are edited, keep shell syntax checks explicit:

```bash
bash -n \
  scripts/submit_phase4_gwd30_pixel_stats.sh \
  scripts/submit_phase4_gwd30_regional_year_split.sh \
  scripts/submit_phase4_gwd30_tropical_shards.sh
```

`run_related_tests.py` is still useful as a selector, but only as a selector:

```bash
python scripts/run_related_tests.py <changed-paths...>
```

Then run the suggested `python -m pytest ...` subset for real.

CLI help smoke should stay in the loop for any touched orchestration surfaces:

```bash
python scripts/run_phase4_regional.py --help
python scripts/run_phase4_trend_contract.py --help
python scripts/run_phase4_hotspot_ledger.py --help
```

If S05 restores the missing percentage/classification contract producers, add their help surfaces and focused pytest files immediately.

For final closeout, S05 will likely touch enough shared execution/orchestration surfaces that a broader regression should still be attempted:

```bash
python -m pytest tests/
```

If the previously documented unrelated full-suite boundary (`tests/test_mgrs_tiling.py` and/or later exit `137`) still appears, record it explicitly rather than suppressing it.

## HPC commands

After **rsyncing** the repo to HPC (not git push/pull), pass `--repo` explicitly so the submit scripts do not silently use their stale `$HOME/repos/WA2` default.

### Available now: percentage Stage-1 / Stage-2 backbone

Build Stage-1 GWD30 monthly pixel-statistics tiles:

```bash
bash scripts/submit_phase4_gwd30_pixel_stats.sh \
  --repo "$HOME/repos/WA" \
  --python-bin "$HOME/repos/WA/.venv/bin/python" \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --years 2013,2014,2015,2016,2017,2018,2019,2020,2021,2022 \
  --aggregation monthly \
  --worker-count 4 \
  --cpus 4 \
  --no-skip
```

Then prove one region on the Stage-2 year-split path:

```bash
bash scripts/submit_phase4_gwd30_regional_year_split.sh \
  --repo "$HOME/repos/WA" \
  --python-bin "$HOME/repos/WA/.venv/bin/python" \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --region amazon \
  --years 2013,2014,2015,2016,2017,2018,2019,2020,2021,2022 \
  --no-skip
```

Only if that is still too heavy, escalate to the shared full-tropics shard/reduce path:

```bash
bash scripts/submit_phase4_gwd30_tropical_shards.sh \
  --repo "$HOME/repos/WA" \
  --python-bin "$HOME/repos/WA/.venv/bin/python" \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --years 2013,2014,2015,2016,2017,2018,2019,2020,2021,2022 \
  --task-lists 16 \
  --task-cpus 4 \
  --reduce-cpus 4 \
  --no-skip
```

### Available now: trend amazon → canonical → ten-region ladder

One-region trend proof:

```bash
python scripts/run_phase4_trend_contract.py \
  --region amazon \
  --dataset-id gwd30 \
  --dataset-id giems_mc \
  --dataset-id topmodel \
  --dataset-id swamps \
  --dataset-id wad2m \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --aggregation annual \
  --start-year 1990 \
  --end-year 2020 \
  --top-hotspots 10 \
  --no-skip
```

Canonical subset:

```bash
python scripts/run_phase4_trend_contract.py \
  --subset canonical \
  --dataset-id gwd30 \
  --dataset-id giems_mc \
  --dataset-id topmodel \
  --dataset-id swamps \
  --dataset-id wad2m \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --aggregation annual \
  --start-year 1990 \
  --end-year 2020 \
  --top-hotspots 10 \
  --no-skip
```

Ten contract regions with the current codebase require explicit region ids:

```bash
python scripts/run_phase4_trend_contract.py \
  --region amazon \
  --region orinoco \
  --region pantanal \
  --region indogangetic \
  --region mekong \
  --region sudd \
  --region congo \
  --region okavango \
  --region borneo \
  --region northernaus \
  --dataset-id gwd30 \
  --dataset-id giems_mc \
  --dataset-id topmodel \
  --dataset-id swamps \
  --dataset-id wad2m \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --aggregation annual \
  --start-year 1990 \
  --end-year 2020 \
  --top-hotspots 10 \
  --no-skip
```

### Blocked until the missing producer surfaces are restored or otherwise materialized

The unified ledger command is already real, but it will fail closed until the percentage and classification hotspot families exist for the same regions:

```bash
python scripts/run_phase4_hotspot_ledger.py \
  --region amazon \
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

Once a real three-line producer chain exists again, the same pattern should widen to the ten-region list above.
