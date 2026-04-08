# M001 / S04 — Research

**Date:** 2026-04-07

## Summary

S04 directly owns **R006** and supports the later **R008** handoff, but it should stay documentation-first. The slice should not restate S03’s route audit in prose. Instead, it should convert the now-validated route truth into an **ordered execution ladder** that an operator can actually follow: what to read first, what to run first, what files prove success, what to widen only after the narrow proof passes, and which stale or misleading paths to leave alone.

The current code surface makes that ladder narrower than several older stash notes suggest. `scripts/build_phase4_gwd30_pixel_stats.py` is the Stage-1 builder and writes `tile_manifest.json` under `results/phase4/pixel_stats/...`; `scripts/run_phase4_regional.py` is the Stage-2 regional-table runner and now consumes those manifests via `src/WA/comparison/phase4_regional.py`; `scripts/hpc_probe_trends.py` is still a supporting diagnostic lane, not the current continuation mainline. Just as importantly, the scripts default broad: omitting `--year` in the Stage-1 builder selects all `gwd30` years from `config/datasets.yaml`; omitting `--years` in the submit wrapper queues one job per discovered year; omitting `--dataset-id` or `--region` in `run_phase4_regional.py` fans out across all datasets and all configured regions. S04 should turn that implicit fanout risk into explicit “do this first / do not do this first” guidance.

Use current code over older stash command snippets. Several historical command forms are already stale relative to the live scripts: `run_phase4_regional.py` no longer exposes `--berkeley-raw-path` or `--phase36-cache-dir`, and `hpc_probe_trends.py` no longer exposes the old `--gwd30-cache-dir` / `--gwd30-worker-count` flags from 2026-04-05 notes. This follows the installed `doc-coauthoring` skill’s core rule: keep one canonical reader-facing document, ground it in the live source of truth, and avoid multiplying competing summaries. I also reran the focused current-route regression surface — `python -m pytest tests/test_comparison/test_trends.py tests/test_comparison/test_phase4_regional.py tests/test_submit_phase4_gwd30_pixel_stats.py -q` — and it passed **38 tests**, so S04 can stay documentation-first and treat the open gap as **fresh HPC proof**, not local code uncertainty.

## Recommendation

Create one canonical artifact, ideally:

- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`

That document should have five required blocks:

1. **Canonical read order**
   - Read `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` first.
   - Read `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` second, specifically the `Open Proof Gaps` and Phase 4 rows.
   - State that S04 turns those two inputs into the next executable route and does not replace them.

2. **Ordered continuation path**
   - **Step 0 — Documentary re-entry**: confirm the operator is starting from the current route truth, not old plan/stash language.
   - **Step 1 — First fresh proof target (narrow Stage 1)**: use the project-default year **2016** and run the direct builder first, not the broad submit wrapper.
     ```bash
     python scripts/build_phase4_gwd30_pixel_stats.py \
       --year 2016 \
       --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
       --output-root results/phase4 \
       --aggregation monthly \
       --worker-count 1 \
       --no-skip
     ```
   - **Step 2 — First fresh proof target (narrow Stage 2)**: keep the time window aligned with the manifests just built; use `gwd30` only and a single region such as `amazon`.
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
   - **Step 3 — Broaden only after the narrow proof passes**: either use the submit wrapper with an explicit `--years` filter first, or intentionally widen to the full 2013–2022 span only after the single-year proof is clean.
     ```bash
     bash scripts/submit_phase4_gwd30_pixel_stats.sh \
       --years 2013,2014,2015,2016,2017,2018,2019,2020,2021,2022 \
       --aggregation monthly \
       --worker-count 1 \
       --cpus 1 \
       --time 480 \
       --partition C064M0256G \
       --no-skip

     python scripts/run_phase4_regional.py \
       --dataset-id gwd30 \
       --region amazon \
       --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
       --output-root results/phase4 \
       --start-year 2013 \
       --end-year 2022 \
       --no-skip
     ```
   - **Step 4 — Deferred / supporting lane only after current-route proof**: keep `scripts/hpc_probe_trends.py` explicitly secondary. If S04 includes a probe example, derive it from the current script surface, not old stash flags:
     ```bash
     python scripts/hpc_probe_trends.py \
       --dataset-id gwd30 \
       --aggregation annual \
       --bbox -65 -20 -45 5 \
       --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
       --json-out results/phase4/probe_gwd30_annual.json
     ```

3. **Proof targets / exit criteria**
   - Stage 1 success should name the exact proof files:
     - `results/phase4/pixel_stats/gwd30/gwd30_2016/monthly/tile_manifest.json`
     - referenced `tiles/tile_*.nc` files exist
     - builder logs include `Phase4 cache write: gwd30_native_pixel_stats ...`
   - Stage 2 success should name the exact proof files:
     - `results/phase4/cache/masks/berkeley_valid/amazon_2016_2016.nc`
     - `results/phase4/cache/gwd30/amazon/regional_series.csv`
     - `results/phase4/tables/amazon.csv`
     - table includes `series_type` rows for `monthly`, `annual`, and `climatology`
   - Only after those outputs exist should the operator treat the current route as freshly re-proven on HPC.

4. **Do not touch first / explicit avoid list**
   - Historical/stale full-tropics shard/reduce family:
     - `scripts/submit_phase4_gwd30_tropical_shards.sh`
     - `scripts/build_phase4_gwd30_shard_lists.py`
     - `scripts/run_phase4_gwd30_tropical_shard.py`
     - `scripts/reduce_phase4_gwd30_tropical_shards.py`
   - Missing broad runner: `scripts/run_phase4_trend_analysis.py`
   - Broad default invocations that silently fan out:
     - bare `python scripts/build_phase4_gwd30_pixel_stats.py` without `--year`
     - bare `bash scripts/submit_phase4_gwd30_pixel_stats.sh` without `--years`
     - bare `python scripts/run_phase4_regional.py` without `--dataset-id gwd30 --region ...`
   - Stale flags copied from older notes:
     - `--berkeley-raw-path`
     - `--phase36-cache-dir`
     - `--gwd30-cache-dir`
     - `--gwd30-worker-count`

5. **Requirement coverage**
   - Close R006 by explicitly showing:
     - the entry scripts,
     - the ordered proof sequence,
     - the output files that prove each rung,
     - the routes / flags not to touch first.

Keep S04 canonical and execution-focused. Do **not** spend S04 on a compact recovery-pack note unless the executor can keep it clearly subordinate to the canonical document; that packaging work belongs mainly to S05.

## Implementation Landscape

### Key Files

- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` — recommended new canonical S04 artifact; should be the only source of truth for the ordered continuation ladder.
- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` — authoritative route truth from S03; S04 should cite it as input, not rewrite it.
- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` — authoritative proof-boundary source; S04 should cite its Phase 4 split and `Open Proof Gaps` section.
- `scripts/build_phase4_gwd30_pixel_stats.py` — current Stage-1 builder. Important details:
  - `--year` is optional; omitting it widens to all configured years.
  - writes `tile_manifest.json` per year/aggregation.
  - logs `Phase4 cache write: gwd30_native_pixel_stats ...`.
- `scripts/submit_phase4_gwd30_pixel_stats.sh` — current Stage-1 HPC batch wrapper.
  - `--years` exists and should be used for narrow first proof.
  - omitting `--years` submits one job per `gwd30` year from `config/datasets.yaml`.
  - respects `--no-skip`, matching project HPC rules.
- `scripts/run_phase4_regional.py` — current Stage-2 entrypoint.
  - if `--dataset-id` is omitted, it expands to all Phase 4 datasets.
  - if `--region` is omitted, it expands to all configured regions.
  - current live flags are `--standardized-dir`, `--region`, `--dataset-id`, `--start-year`, `--end-year`, etc.; older stash flags like `--berkeley-raw-path` are stale.
- `src/WA/comparison/phase4_regional.py` — current output and cache truth for Stage 2.
  - `compute_phase4_region_dataset_table(...)` dispatches `gwd30` to `build_phase4_gwd30_monthly_series_from_pixel_stats_tiles(...)`.
  - `phase4_gwd30_pixel_stats_manifest_path(...)` fixes the Stage-1 manifest location.
  - `build_or_load_phase4_berkeley_valid_mask(...)` writes `results/phase4/cache/masks/berkeley_valid/<region>_<start>_<end>.nc`.
  - `phase4_dataset_region_cache_path(...)` and `phase4_region_table_path(...)` fix the Stage-2 output locations.
- `scripts/hpc_probe_trends.py` — diagnostic-only trend probe.
  - still loads GWD30 from `_staging` via `load_trend_surface(...)`.
  - current live flag for GWD30 input is `--standardized-dir`, not the old cache-specific flags from older notes.
- `config/datasets.yaml` — proves `gwd30` spans 2013–2022; this is why the Stage-1 builder and submit wrapper widen if no year filter is supplied.
- `config/priority_regions.yaml` — proves `amazon` exists as a stable narrow first-proof region.
- `tests/test_comparison/test_trends.py` — proves Stage-1 transformed tile generation and output layout.
- `tests/test_comparison/test_phase4_regional.py` — proves Stage-2 `gwd30` regional tables consume Stage-1 manifests and write caches/tables.
- `tests/test_submit_phase4_gwd30_pixel_stats.py` — proves the submit wrapper generates one SLURM script per selected year and respects `--no-skip`.
- `docs/stashes/2026-04-06-005-phase4-stage2-pixel-stats-regional-integration.md` — useful history for the route shift, but its old `--berkeley-raw-path` command should not be copied into S04.
- `docs/stashes/2026-04-06-008-phase4-recall-entry.md` — useful history for “Stage 1 -> Stage 2” recovery, but S04 should update the execution map to current-code flags and a narrower first-proof ladder.
- `docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md` — useful compact breadcrumb back to S03; S04 should cite it only as a pointer, not as the new canonical execution map.

### Build Order

1. **Write the canonical S04 map first.**
   Draft the document from live code plus S02/S03, not from older stash command snippets.
2. **Lock the ordered ladder before adding narrative detail.**
   The planner/executor should settle the actual execution order first: re-entry -> narrow Stage 1 -> narrow Stage 2 -> broader batch -> optional probe.
3. **Add proof markers next.**
   After the ladder is stable, add the exact output paths and log markers that prove each rung passed.
4. **Then add the explicit avoid list.**
   This is where stale routes, stale flags, and broad default invocations should be frozen in writing.
5. **Only after the document is stable, update metadata.**
   Update `.gsd/REQUIREMENTS.md` to validate `R006`, and add a `CHANGELOG.md` breadcrumb. A decision entry is only needed if execution wants to freeze a new rule like “single-year proof before broad batch.”
6. **Defer compact packaging.**
   If an executor wants a short stash note, keep it strictly secondary; otherwise leave re-entry packaging to S05.

### Verification Approach

Use structural verification for the S04 artifact, because the slice is documentation-first:

```bash
test -s .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md
rg -n '^## (Canonical Read Order|Ordered Continuation Path|Proof Targets / Exit Criteria|Do Not Touch First|Requirement Coverage)$' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md
rg -n 'scripts/build_phase4_gwd30_pixel_stats.py|scripts/submit_phase4_gwd30_pixel_stats.sh|scripts/run_phase4_regional.py|scripts/hpc_probe_trends.py|scripts/submit_phase4_gwd30_tropical_shards.sh|scripts/run_phase4_gwd30_tropical_shard.py|scripts/reduce_phase4_gwd30_tropical_shards.py' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md
rg -n 'results/phase4/pixel_stats/gwd30/gwd30_2016/monthly/tile_manifest.json|results/phase4/cache/masks/berkeley_valid/amazon_2016_2016.nc|results/phase4/cache/gwd30/amazon/regional_series.csv|results/phase4/tables/amazon.csv' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md
rg -n 'R006' .gsd/REQUIREMENTS.md
```

The live route code surface is already green under the focused regression suite:

```bash
python -m pytest tests/test_comparison/test_trends.py tests/test_comparison/test_phase4_regional.py tests/test_submit_phase4_gwd30_pixel_stats.py -q
```

Current result in this worktree: **38 passed**.

## Constraints

- S04 directly serves **R006**. Do not drift into S05’s larger recovery-pack scope before the canonical execution map exists.
- Follow the installed `doc-coauthoring` skill’s reader-first rule: one canonical document first, then validate readability/structure; do not scatter execution truth across multiple notes.
- Use **current code** over older stash command examples. Several early-April notes now contain stale CLI flags.
- Follow project HPC conventions:
  - use `--no-skip`, not `--skip-existing`
  - assume rsync-to-HPC workflow, not git push/pull on HPC
  - keep errors and cache reuse visible in the documented route
- Respect the project default target year: **2016** is the safest first proof year unless a later slice explicitly chooses another year.
- Do not modify `config/` for S04.
- Keep the local/HPC proof boundary explicit: S04 is defining the next proof sequence, not claiming the HPC rerun already happened.

## Common Pitfalls

- **Turning S04 into a second route-audit summary** — S03 already settled route truth. S04’s job is sequencing, not re-arguing which route is current.
- **Copying stale flags from old stash notes** — `--berkeley-raw-path`, `--phase36-cache-dir`, `--gwd30-cache-dir`, and `--gwd30-worker-count` no longer match the live scripts.
- **Using broad default invocations as the first proof** — the current Stage-1 and Stage-2 entrypoints silently widen to all years / all datasets / all regions unless constrained.
- **Mismatching Stage-1 manifests and Stage-2 time ranges** — if Stage 1 builds only 2016, Stage 2 must also target 2016 first or it will chase manifests for years that were never built.
- **Treating `hpc_probe_trends.py` as the next mainline step** — it remains a diagnostic/supporting route and still uses the `_staging`-based trend load path.
- **Creating a compact recovery note before the canonical map exists** — that risks starting S05’s packaging work too early and creating another competing document.

## Open Risks

- **The first fresh Stage-2 proof may still surface runtime issues on large windows** — keep the first proof narrow (`amazon`, `2016` only) before widening the range.
- **Remote staged data presence is still an external dependency** — Stage 1 and the probe lane both depend on the real `/lustre/.../standardized/_staging/gwd30_<year>/` surfaces being present after rsync.
- **Stage vocabulary drift still exists in older notes** — S04 should define its own ladder labels clearly so later slices do not reuse ambiguous “Stage 2” wording.
- **Broad full-range proof remains more expensive and riskier than the narrow rung** — if S04 jumps straight to 2013–2022 all-years/all-regions language, it loses the practical recovery value R006 wants.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Structured documentation workflow | `doc-coauthoring` | installed |
| xarray / scientific-array workflows | `tondevrel/scientific-agent-skills@xarray` | available — `npx skills add tondevrel/scientific-agent-skills@xarray` |
| SLURM / HPC batch workflows | `serendipityoneinc/srp-claude-code-marketplace@slurm` | available — `npx skills add serendipityoneinc/srp-claude-code-marketplace@slurm` |
