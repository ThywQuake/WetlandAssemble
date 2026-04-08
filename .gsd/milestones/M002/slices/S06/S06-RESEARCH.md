# M002/S06 Research — Paper-ready evidence pack and milestone integration proof

## Summary

S06 is **not** a new science slice. The science-side contract is already in place from S01–S05; the missing work is the **paper-facing packaging layer** plus a **milestone-level reintegration proof** that the ten-region outputs really reopen together.

This slice primarily owns **R113** and supports **R102 / R103 / R104 / R107**:

- **R113 (primary)** — emit paper-ready figure/table/summary packs aligned to the thesis narrative.
- **R102 / R103 / R104 (supporting)** — the pack must consume the already-defined percentage / classification / trend contract outputs without inventing a parallel schema.
- **R107 (supporting)** — the pack must sit *after* the S05 producer -> readiness -> ledger gate and must not blur local synthetic smoke outputs with real ten-region proof.

The key repo reality is:

1. **Contract-backed producers exist** for all three lines.
2. **Fail-closed readiness and unified ledger exist** and are the right preflight/final integration surfaces.
3. **There is no actual paper-pack assembler yet** — no Phase 4 figure/table pack script, no pack manifest, no milestone integration report producer.
4. **The local worktree does not contain real ten-region science outputs**. `results/phase4/` currently only contains readiness smoke files, so S06 must treat HPC materialization as a prerequisite, not as already-done input.

## Requirement Focus

### Primary
- **R113** — the slice must turn engineering artifacts into a thesis-usable pack.

### Supporting
- **R102** — package the percentage line in paper-usable form.
- **R103** — package the classification line in paper-usable form.
- **R104** — package the trend line in paper-usable form.
- **R107** — prove the ten-region path only through explicit HPC-safe rerun + readiness + ledger, not via ad hoc local assumptions.

## Skill Discovery (suggest only)

No installed skill list was exposed in-context. Directly relevant external skills that looked promising:

- **xarray**
  - `npx skills add tondevrel/scientific-agent-skills@xarray`
  - `npx skills add steadfastasart/geoscience-skills@xarray`
- **matplotlib**
  - `npx skills add mindrally/skills@matplotlib-best-practices`
  - `npx skills add davila7/claude-code-templates@matplotlib`
- **SLURM / HPC wrappers**
  - `npx skills add serendipityoneinc/srp-claude-code-marketplace@slurm`

Most of S06 can follow existing repo patterns without new skills, but `matplotlib-best-practices` is the most directly useful if the pack grows beyond the already-tested Phase 4 percentage plots.

## Implementation Landscape

### 1. The contract boundary is already stable

**`src/WA/comparison/evidence_contract.py`** is the anchor for:
- ordered `canonical` and `ten` selectors
- artifact-family relpaths
- reserved stem grammar (`<dataset_or_key>__<region>__<suffix>`)
- fail-closed token validation

This means S06 should **not** hand-roll region lists or filenames. Derived pack code should reopen contract outputs semantically and keep `EvidenceContract.resolve_regions(subset=...)` as the only owner of ten-region ordering.

### 2. Percentage inputs are pack-ready, but only partly surfaced as visualization APIs

**Science/contract files already present**:
- `src/WA/comparison/percentage_backbone.py`
- `src/WA/comparison/percentage_hotspots.py`
- `scripts/run_phase4_percentage_contract.py`

Useful existing data surfaces:
- contract surface bundle contains stacked per-dataset `wetland_fraction` plus
  - `mean_wetland_percentage`
  - `std_wetland_percentage`
  - `valid_dataset_count`
- contract summary contains annual + climatology rows via `PERCENTAGE_SUMMARY_COLUMNS`
- hotspot family already writes validated JSON + CSV pairs

**Important gap:** `src/WA/visualization/phase4.py` contains the only Phase 4 plotting functions today:
- `plot_phase4_interannual(...)`
- `plot_phase4_climatology(...)`

but those helpers are **not used by any production CLI**, only by tests. There is also **no percentage semantic reload wrapper** in `WA.visualization.phase4`; pack code currently has to import comparison-layer loaders directly.

**Important paper-pack consequence:** the existing S05 HPC percentage command used `--start-year 2016 --end-year 2016`, which is fine for scale-out proof, but it is **not enough for a publication-style interannual figure**. The tested interannual plot helper defaults to **1990–2020**, so S06 either needs:
- a broader percentage summary rerun (recommended), or
- a pack contract that explicitly limits itself to 2016-only percentage outputs.

The first option fits R113 better.

### 3. Classification contract inputs are stable and table-ready

**Files already present**:
- `src/WA/comparison/classification_contract.py`
- `scripts/run_phase4_classification_contract.py`
- classification reload wrappers in `src/WA/visualization/phase4.py`

Available reusable outputs:
- `classification_surface`
- `classification_regional_summary`
- `classification_hotspot_manifest` + CSV

The classification summary already exposes exactly the kind of pack fields S06 can elevate into tables:
- `mean_entropy`
- `max_entropy`
- `mean_agreement_count`
- agreement-count histogram columns
- hotspot quota / selected / shortfall / threshold metadata

This line is the easiest source for a **paper table** even if S06 avoids building a brand-new classification map figure.

### 4. Trend contract outputs exist, but agreement reload is still trapped inside the runner script

**Files already present**:
- `src/WA/comparison/trend_contract.py`
- `src/WA/comparison/trend_hotspots.py`
- `scripts/run_phase4_trend_contract.py`
- `scripts/submit_phase4_trend_contract.sh`

Available reusable outputs:
- per-dataset `trend_surface`
- per-dataset `trend_regional_summary`
- participant-set `trend_agreement_surface`
- participant-set `trend_agreement_summary`
- participant-set `trend_hotspot_manifest` + CSV

**Important gap:** the reusable agreement loader is currently only the private helper
`_load_trend_agreement_artifacts(...)` inside `scripts/run_phase4_trend_contract.py`.

There is **no public comparison/visualization API** for semantic reload of trend agreement summary/surface. `src/WA/visualization/phase4.py` only wraps trend hotspots, not agreement summaries.

For S06, this is the cleanest first foundational task: **promote agreement semantic reload out of the script** so the pack builder does not duplicate contract-path logic or import a script-private helper.

### 5. Unified hotspot ledger is already the best cross-line paper-table source

**Files already present**:
- `src/WA/comparison/hotspot_ledger.py`
- `scripts/run_phase4_hotspot_ledger.py`
- `src/WA/visualization/phase4.py` wrapper for semantic reload

The ledger already normalizes the three lines into long-form rows with exactly the fields a cross-line paper table needs:
- `analysis_object_id`
- `metric_family`
- `primary_score_name`
- `primary_score_value`
- `family_percentile`
- `line_specific_json`
- manifest/table/surface/summary provenance paths

This means S06 does **not** need to invent another cross-line hotspot schema. It needs a **derived table/summary layer** over the ledger.

### 6. Readiness is the pack preflight gate

**Files already present**:
- `src/WA/comparison/scaleout_readiness.py`
- `scripts/run_phase4_scaleout_readiness.py`

Readiness already classifies each `region × family` as:
- `ready`
- `missing`
- `partial`

with explicit `reason` and expected artifact paths.

This should become S06’s **preflight**:
- if readiness says `missing` or `partial`, the pack should fail closed (or produce an explicit incomplete-proof report, depending on CLI mode)
- do **not** let the pack silently skip incomplete families and still claim milestone integration proof

### 7. Current local output reality: no ten-region science artifacts exist here

Current local `results/phase4/` only contains:
- `scaleout_readiness/*.csv`
- `scaleout_readiness/*.json`

The existing readiness JSON for `amazon` reports all three families as **missing**. So any S06 code must assume that real input artifacts are expected to be regenerated on HPC first.

### 8. There is no S06 pack code yet

What does **not** currently exist:
- no `phase4_pack.py`-like module
- no `run_phase4_evidence_pack.py`-like CLI
- no pack manifest format
- no milestone integration proof markdown/CSV writer
- no test-selection trigger coverage for future pack files
- no docs/testing entry for the future pack test family

Also note two drift hazards:
- `.gsd/milestones/M002/slices/S01/S01-SUMMARY.md` is a **BLOCKER placeholder**, so do not rely on it as a canonical downstream handoff.
- Older summary/knowledge text is partially stale (for example, some notes still claim missing producer modules or wrappers that are now restored/changed). Per project knowledge rules, prefer **current code + latest S05 closeout** over older intent text.

## Don’t Hand-Roll

These rules should shape the implementation:

1. **Don’t guess artifact paths.** Use `EvidenceContract` relpaths or semantic reload helpers.
2. **Don’t hand-write ten-region lists.** Use `contract.resolve_regions(subset="ten")`.
3. **Don’t invent a second hotspot schema.** Reuse the unified ledger as the cross-line object layer.
4. **Don’t mark the pack complete from local smoke outputs.** Require readiness + ledger against real HPC-generated artifacts.
5. **Don’t blur contract outputs with paper-pack outputs.** Keep the paper pack as a derived layer, not a new contract family mixed into `results/phase4` science artifacts.

## Recommended Slice Decomposition

### Task seam 1 — Promote pack-safe semantic reload APIs

**Why first:** it removes the biggest accidental-complexity trap before any figure/table code exists.

Likely files:
- `src/WA/comparison/trend_contract.py` or a new small companion module for trend agreement reload
- `src/WA/visualization/phase4.py`
- `tests/test_visualization/test_phase4.py`
- possibly `tests/test_comparison/test_trend_contract.py`

Concrete goal:
- expose public semantic reload for the trend agreement surface/summary pair
- optionally add percentage reload wrappers into `WA.visualization.phase4` so all pack consumers use one downstream API surface

If this seam is skipped, the eventual pack builder will either duplicate reload logic or import script-private helpers.

### Task seam 2 — Build one derived paper-pack module + CLI

**This is the core S06 delivery.**

Recommended new files:
- `src/WA/visualization/phase4_pack.py`
- `scripts/run_phase4_evidence_pack.py`
- `tests/test_visualization/test_phase4_pack.py`

Recommended output pattern:
- keep inputs in `results/phase4/` untouched
- write derived pack outputs to a separate root such as `results/figures/phase4_pack/` with subdirs like:
  - `figures/`
  - `tables/`
  - `summaries/`
  - `manifest.json`

Recommended minimum pack contents for a first paper-usable delivery:

1. **Percentage figures**
   - reuse `plot_phase4_interannual(...)`
   - reuse `plot_phase4_climatology(...)`
   - one file per region, or a deterministic multi-region panel if needed later

2. **Regional evidence table**
   - one joined CSV/Markdown table across the ten regions combining:
     - percentage summary aggregates
     - classification summary metrics
     - trend agreement summary metrics
     - hotspot counts / ledger row counts

3. **Unified hotspot table**
   - derived from `unified_hotspot_ledger`
   - likely top-N per `region × metric_family`
   - preserve `primary_score_name/value`, `family_percentile`, and provenance paths

4. **Narrative summary markdown**
   - one machine-generated markdown summary describing:
     - regions included
     - dataset key / participant set key
     - input artifact paths
     - any incomplete regions (if non-strict mode exists)
     - where each thesis-facing figure/table landed

The pack manifest should record the exact contract inputs used so the pack remains replayable.

### Task seam 3 — Add a strict integration-proof mode

This is separate from “make files”. S06 also needs to prove M002 integration.

Recommended behavior:
- run/read readiness first
- fail closed if any requested region is not `ready`
- then require unified ledger reload for every requested region
- then generate a concise proof artifact (Markdown + CSV/JSON) that records:
  - resolved region ids
  - readiness verdict per region/family
  - unified ledger path per region
  - pack manifest path
  - figure/table counts written
  - dataset key / classification key / trend participant set key

This proof artifact is the best direct bridge into slice closeout and later milestone validation.

## Concrete Risks / Constraints

### A. Percentage paper figures need broader summaries than S05’s minimal scale-out command

If S06 wants the already-tested interannual plot to be meaningful, the percentage producer should likely be rerun as:
- `--surface-year 2016`
- `--start-year 1990`
- `--end-year 2020`

instead of the S05 minimal `2016..2016` summary window.

### B. Current defaults/doc text drift around trend participants

Older slice text said the trend contract should be limited to `gwd30, giems_mc, swamps, wad2m`, but **current code and S05 readiness defaults include `topmodel`**. S06 should follow **current code/readiness defaults**, not older summary prose.

### C. `run_related_tests.py` is advisory only

Per project knowledge, it only prints the recommended pytest command. It does **not** execute the tests. S06 verification still needs the real `python -m pytest ...` command.

### D. Project rules that affect implementation

From the project contract / instructions:
- do **not** modify `config/` without approval
- HPC commands should use **`--no-skip`**, not `--skip-existing`
- HPC deployment is via **`rsync`**, not git push/pull
- prefer **related tests** over a full-suite rerun for routine code changes
- keep progress visible for long-running GWD30 work
- default target year remains **2016** unless the slice explicitly needs a broader time window for summaries

## Verification Strategy

### Code-level verification

If S06 adds a pack module + CLI, the minimal related verification surface should be:

```bash
ruff check \
  src/WA/visualization/phase4.py \
  src/WA/visualization/phase4_pack.py \
  scripts/run_phase4_evidence_pack.py \
  src/WA/test_selection.py \
  docs/testing/test-categories.md \
  tests/test_visualization/test_phase4.py \
  tests/test_visualization/test_phase4_pack.py
```

```bash
python scripts/run_phase4_evidence_pack.py --help
```

```bash
python -m pytest \
  tests/test_visualization/test_phase4.py \
  tests/test_visualization/test_phase4_pack.py \
  tests/test_comparison/test_evidence_contract.py \
  tests/test_comparison/test_hotspot_ledger.py \
  tests/test_comparison/test_scaleout_readiness.py \
  tests/test_comparison/test_percentage_backbone.py \
  tests/test_comparison/test_classification_contract.py \
  tests/test_comparison/test_trend_contract.py \
  tests/test_comparison/test_trend_hotspots.py -q
```

And use `python scripts/run_related_tests.py <changed-paths...>` only as the selector, then run the suggested pytest command separately.

### Runtime-level verification

Use a narrow-first progression:
1. synthetic/fixture-backed local pack test
2. `--region amazon` pack build against real regenerated artifacts
3. `--subset ten` pack build only after readiness + ledger are clean

## Suggested HPC Run Order for Real S06 Proof

Use this as the real data ladder before claiming the pack is complete.

### 1. Percentage (broaden summary window for paper use)

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

### 2. Classification

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

### 3. Trend fanout

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

### 4. Readiness gate

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

### 5. Unified ledger final gate

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

### 6. New paper-pack step (to be implemented)

Recommended shape:

```bash
python scripts/run_phase4_evidence_pack.py \
  --subset ten \
  --phase4-output-root results/phase4 \
  --pack-output-root results/figures/phase4_pack \
  --ledger-key canonical \
  --percentage-key canonical \
  --classification-key canonical \
  --trend-dataset-id gwd30 \
  --trend-dataset-id giems_mc \
  --trend-dataset-id topmodel \
  --trend-dataset-id swamps \
  --trend-dataset-id wad2m \
  --strict
```

## Recommendation

Plan S06 as **three tasks in order**:

1. **Expose the missing semantic reload surface** needed by pack code (especially trend agreement, optionally percentage wrappers).
2. **Build one derived paper-pack module + CLI** that uses only contract reloads, produces deterministic figures/tables/summary markdown plus a pack manifest, and keeps outputs separate from `results/phase4` science artifacts.
3. **Add strict milestone integration proof mode** that requires readiness + ledger success across the requested regions before the pack can claim a complete ten-region deliverable.

That sequence is the lowest-risk path to R113 while staying faithful to S05’s execution boundary and the project rule to keep failures visible instead of silently reusing partial state.
