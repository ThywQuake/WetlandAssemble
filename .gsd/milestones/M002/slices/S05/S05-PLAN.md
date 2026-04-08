# S05: Ten-region scale-out with reproducible HPC-safe execution

**Goal:** 把 canonical subset 上已经闭合的 shared evidence contract 扩到十个 contract regions，并把 percentage / classification / trend / ledger 的宽范围执行收敛为 explicit subset + cache/split/merge/reload surfaces，让 amazon → canonical → ten 的 HPC rerun 可以按同一合同复跑而不是依赖手写 region 列表或 stale producer 假设。
**Demo:** After this: After this: 从 canonical subset 扩到十个大区时，三条主线都能沿同一合同输出结果，并且关键宽范围运行仍然是 split/cache/merge 可复跑的。

## Tasks
- [x] **T01: Added a shared ordered ten-region selector and explicit subset/logging plumbing across the Phase 4 regional, trend, and ledger CLIs.** — Freeze one ordered ten-region selector before restoring missing producers, so wide runs stop depending on hand-written region lists or `run_phase4_regional.py`'s macro+priority default.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/evidence_contract.py`, the current contract-aware CLIs, and `config/priority_regions.yaml` | Fail before any wide run starts, with the bad subset/region combination or unknown region id named explicitly. | N/A for the selector layer; keep resolution deterministic so retries do not depend on hidden state. | Reject invalid subset names, duplicate region ids, or `--subset` + `--region` ambiguity instead of falling back to macro-region defaults. |

## Load Profile

- **Shared resources**: one YAML-backed region catalog and the CLI argument surface for the current Phase 4 runners.
- **Per-operation cost**: trivial metadata parsing plus CLI validation.
- **10x breakpoint**: semantic drift, not runtime load — the main risk is accidentally reintroducing macro-region leakage once the ten-region ladder is automated.

## Negative Tests

- **Malformed inputs**: unknown subset names, duplicate canonical/ten aliases, and simultaneous `--subset` + `--region` requests.
- **Error paths**: bad region ids or missing catalog payload fields must fail loudly instead of silently broadening the run.
- **Boundary conditions**: canonical order stays stable, ten-region order matches contract priority order, and no-arg legacy regional behavior remains explicit instead of pretending to be the contract ten-region route.

## Steps

1. Extend `src/WA/comparison/evidence_contract.py` with one explicit ordered ten-region alias/helper that reuses the existing contract catalog, keeps `config/priority_regions.yaml` read-only, and rejects ambiguous selector combinations.
2. Plumb that selector through `scripts/run_phase4_regional.py`, `scripts/run_phase4_trend_contract.py`, and `scripts/run_phase4_hotspot_ledger.py`, keeping old no-arg behavior explicit instead of silently redefining it, and log the resolved region list before execution starts.
3. Add focused tests in `tests/test_comparison/test_evidence_contract.py` and `tests/test_comparison/test_phase4_regional.py` that pin canonical vs ten ordering, invalid subset names, and the no-manual-list path for the touched CLIs.

## Must-Haves

- [ ] One ordered ten-region selector exists in the contract layer and is the only supported shared source for wide Phase 4 runs.
- [ ] The touched CLIs expose the selector in `--help` and log the resolved region list so macro-region leakage is visible immediately.

## Done when

- `resolve_regions(subset="ten")` returns exactly the ten contract regions in stable order, and the touched CLIs can target that set without any manual ten-item `--region` list.
  - Estimate: 90m
  - Files: src/WA/comparison/evidence_contract.py, scripts/run_phase4_regional.py, scripts/run_phase4_trend_contract.py, scripts/run_phase4_hotspot_ledger.py, tests/test_comparison/test_evidence_contract.py, tests/test_comparison/test_phase4_regional.py
  - Verify: ruff check src/WA/comparison/evidence_contract.py scripts/run_phase4_regional.py scripts/run_phase4_trend_contract.py scripts/run_phase4_hotspot_ledger.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_phase4_regional.py
python scripts/run_phase4_regional.py --help
python scripts/run_phase4_trend_contract.py --help
python scripts/run_phase4_hotspot_ledger.py --help
python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_phase4_regional.py -q
- [x] **T02: Restored the real percentage producer chain with a shared backbone, GWD30 Stage-1 surface recovery, atomic hotspot pairs, and a contract-aware runner for one region, `canonical`, or `ten`.** — The current snapshot is missing `src/WA/comparison/percentage_backbone.py`, `src/WA/comparison/percentage_hotspots.py`, and `scripts/run_phase4_percentage_contract.py` even though older slice text claims they already exist. Restore that percentage producer chain intentionally on top of the real `phase4_regional.py` and `0.25°` surface backbones so the unified ledger can consume real percentage families instead of synthetic fixtures.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/phase4_regional.py`, `scripts/plot_tropical_wetland_025deg.py`, and Stage-1 GWD30 pixel-statistics tiles under `results/phase4/pixel_stats/...` | Fail with `dataset_id`, `region_id`, and stage context; never emit a hotspot pair or contract surface from incomplete upstream data. | Preserve visible cache reuse and per-region progress so long reruns can resume without recomputing all ten regions. | Reject empty coarse surfaces, missing Stage-1 manifests, malformed hotspot metadata, or partial JSON/CSV pairs instead of backfilling guesses. |

## Load Profile

- **Shared resources**: staged coarse-surface caches under `results/cache/tropical_025deg`, Stage-1 GWD30 pixel-statistics tiles, per-region summaries from `results/phase4`, and contract hotspot JSON/CSV outputs.
- **Per-operation cost**: one dataset surface load or many tile reads plus coarse aggregation, then per-region hotspot ranking and manifest serialization.
- **10x breakpoint**: disk I/O and surface materialization dominate first when the canonical subset widens to all ten regions without disciplined cache reuse.

## Negative Tests

- **Malformed inputs**: unknown region ids, missing Stage-1 manifests, stale coarse-cache metadata, malformed hotspot bbox payloads, and duplicate hotspot ids.
- **Error paths**: loader failure, unreadable cache files, or zero-cell hotspot candidates surface explicit stage-tagged exceptions.
- **Boundary conditions**: Berkeley year handling, GWD30 inclusion, canonical vs ten subset selection, and partial manifest/table corruption all stay deterministic.

## Steps

1. Add `src/WA/comparison/percentage_backbone.py` as the reusable contract-aware `0.25°` surface/cache adapter: keep non-GWD30 surface generation on the live plot-route logic, add the missing GWD30 Stage-1-backed surface path, and resolve regions through the T01 contract selector instead of direct catalog assumptions.
2. Refactor `scripts/plot_tropical_wetland_025deg.py` into a thin CLI over the new backbone without losing its visible cache-stage logging, and add `src/WA/comparison/percentage_hotspots.py` to rank/write contract-backed percentage hotspot JSON/CSV pairs with atomic writes and semantic reload validation.
3. Add `scripts/run_phase4_percentage_contract.py` as a thin orchestration CLI that composes `phase4_regional.py` summaries, the new backbone surfaces, and hotspot writes for one region, `--subset canonical`, or `--subset ten`, always keeping dataset selection and `--no-skip` decisions visible.
4. Add `tests/test_comparison/test_percentage_backbone.py`, `tests/test_comparison/test_percentage_hotspots.py`, and extend `tests/test_plot_tropical_wetland_025deg.py` to pin cache reuse, GWD30 adapter behavior, contract metadata, hotspot ranking, and help/smoke expectations.

## Must-Haves

- [ ] The percentage line is restored as a real contract-backed producer chain, not a stale doc reference or synthetic test-only family.
- [ ] GWD30 can participate in the shared-grid percentage contract path through resumable Stage-1-backed logic instead of being permanently excluded from the restored producer surface.
- [ ] Percentage hotspot JSON/CSV pairs are atomic and semantically reloadable before any ledger step trusts them.

## Done when

- One contract-aware CLI can write percentage surfaces, regional summaries, and hotspot manifests for a single region and for `--subset ten`, and focused tests prove cache/reload behavior on both the backbone and hotspot layers.
  - Estimate: 3h
  - Files: src/WA/comparison/percentage_backbone.py, src/WA/comparison/percentage_hotspots.py, scripts/run_phase4_percentage_contract.py, scripts/plot_tropical_wetland_025deg.py, tests/test_comparison/test_percentage_backbone.py, tests/test_comparison/test_percentage_hotspots.py, tests/test_plot_tropical_wetland_025deg.py
  - Verify: ruff check src/WA/comparison/percentage_backbone.py src/WA/comparison/percentage_hotspots.py scripts/run_phase4_percentage_contract.py scripts/plot_tropical_wetland_025deg.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_plot_tropical_wetland_025deg.py
python scripts/run_phase4_percentage_contract.py --help
python -m pytest tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_plot_tropical_wetland_025deg.py -q
python scripts/run_related_tests.py src/WA/comparison/percentage_backbone.py src/WA/comparison/percentage_hotspots.py scripts/run_phase4_percentage_contract.py scripts/plot_tropical_wetland_025deg.py
- [x] **T03: Restored the real Phase 4 classification contract adapter, runner, and semantic reload helpers over the existing Phase 3.6/3.7 producers.** — The current snapshot is also missing `src/WA/comparison/classification_contract.py` and `scripts/run_phase4_classification_contract.py` even though older slice artifacts say they landed already. Restore that adapter/runner path on top of `phase36.py` and `phase37_hotspots.py` so the ten-region proof has a real classification producer instead of stale planner text.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/phase36.py`, `src/WA/phase37_hotspots.py`, and `src/WA/visualization/phase4.py` | Fail before any contract artifact is trusted, with `region_id`, `participant_set_key`, and source artifact path in the exception/log context. | Keep region-scoped reruns restartable so one bad region does not force a full ten-region restart. | Reject malformed bbox payloads, mixed-region hotspot rows, missing `joint_valid_mask` / dominant-class variables, or participant-set mismatches instead of inferring silently. |

## Load Profile

- **Shared resources**: Phase 3.6 global disagreement outputs, Phase 3.7 hotspot manifest/CSV inputs, and the shared `results/phase4` contract tree.
- **Per-operation cost**: reopen one global metrics surface plus hotspot-source trio, subset to one contract bbox, then rewrite one region-scoped surface/summary/hotspot family.
- **10x breakpoint**: repeated NetCDF slicing/materialization and hotspot-manifest rewrites become the first I/O bottleneck when widening to all ten regions.

## Negative Tests

- **Malformed inputs**: missing source-dominant variables, malformed bbox JSON, wrong region ids, and participant-set mismatches.
- **Error paths**: missing Phase 3.6 outputs, malformed Phase 3.7 source trios, or bad contract metadata must fail before any output pair looks complete.
- **Boundary conditions**: descending-lat datasets, hotspot shortfall regions, and `amazon → canonical → ten` ordering must all preserve the same participant-set key and relpaths.

## Steps

1. Add `src/WA/comparison/classification_contract.py` as the thin contract adapter over `phase36.py` and `phase37_hotspots.py`, with stable relpaths, region-scoped surface/summary writers, and hotspot rewrite helpers for the fixed `g2017+glwd_v2+gwd30` participant set.
2. Add `scripts/run_phase4_classification_contract.py` as the thin orchestration CLI that resolves one region, `--subset canonical`, or `--subset ten`, keeps the project default year at `2016`, and reuses existing producers instead of moving the science into the runner.
3. Extend `src/WA/visualization/phase4.py` with classification semantic reload helpers so downstream checks can reopen summaries/hotspot tables by semantics instead of guessed filenames.
4. Add `tests/test_comparison/test_classification_contract.py` and extend `tests/test_visualization/test_phase4.py` so relpaths, metadata, malformed-source failures, and runner help/reload behavior are pinned explicitly.

## Must-Haves

- [ ] The classification line is restored as a real contract adapter/runner over `phase36.py` and `phase37_hotspots.py`; no duplicate disagreement science is introduced.
- [ ] Region-scoped classification outputs keep the full entropy / agreement / dominant-class diagnostic payload needed by the ledger and later paper surfaces.
- [ ] Semantic reload helpers make malformed or mixed-region artifacts fail loudly before any ten-region readiness step trusts them.

## Done when

- A real classification contract CLI plus reload helpers can materialize and reopen one region's contract surface/summary/hotspot family, and the same path can widen to `--subset ten` without manual filename guessing.
  - Estimate: 150m
  - Files: src/WA/comparison/classification_contract.py, scripts/run_phase4_classification_contract.py, src/WA/visualization/phase4.py, tests/test_comparison/test_classification_contract.py, tests/test_visualization/test_phase4.py
  - Verify: ruff check src/WA/comparison/classification_contract.py scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py
python scripts/run_phase4_classification_contract.py --help
python -m pytest tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py -q
- [x] **T04: Restored dataset-scoped Phase 4 trend outputs and resumable trend-contract fanout via explicit checkpoints.** — Current `scripts/run_phase4_trend_contract.py` only persists agreement/hotspot artifacts and still recomputes region-scoped trend inputs from staged tiles for each run. S05 must restore the missing per-dataset trend surface/summary writes and add a resumable submit/checkpoint path before any ten-region trend proof is credible.

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
  - Estimate: 3h
  - Files: src/WA/comparison/trend_contract.py, src/WA/comparison/trends.py, scripts/run_phase4_trend_contract.py, scripts/submit_phase4_trend_contract.sh, tests/test_comparison/test_trend_contract.py, tests/test_comparison/test_trends.py, tests/test_submit_phase4_trend_contract.py
  - Verify: ruff check src/WA/comparison/trend_contract.py src/WA/comparison/trends.py scripts/run_phase4_trend_contract.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_submit_phase4_trend_contract.py
bash -n scripts/submit_phase4_trend_contract.sh
python scripts/run_phase4_trend_contract.py --help
python -m pytest tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_submit_phase4_trend_contract.py -q
- [ ] **T05: Add ten-region readiness reporting and keep the ledger fail-closed** — Once real percentage, classification, and trend producers exist again, close the slice with one operator-facing readiness surface that scans `--subset ten`, reports which regions have complete three-line families, and leaves `scripts/run_phase4_hotspot_ledger.py` as the fail-closed final gate.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Contract hotspot families under `results/phase4`, `src/WA/comparison/hotspot_ledger.py`, and the new readiness CLI | Fail with `region_id`, `metric_family`, and manifest/table path context; never report an incomplete region as ready. | Scans remain region-scoped so one bad region still yields a full ten-region readiness report instead of aborting silently. | Reject partial JSON/CSV pairs, mixed-region rows, malformed metadata JSON, or missing provenance paths instead of coercing them into a fake ready state. |

## Load Profile

- **Shared resources**: three hotspot families plus the shared contract tree across ten regions.
- **Per-operation cost**: one semantic reload/status check per family × region plus one optional ledger build for already-ready regions.
- **10x breakpoint**: repeated manifest/table validation across all regions is still cheap relative to science compute; the main scaling risk is diagnostic clarity, not wall time.

## Negative Tests

- **Malformed inputs**: missing one family, partial manifest/table pairs, mixed-region hotspot rows, and malformed metadata JSON.
- **Error paths**: incomplete regions must stay incomplete in the readiness report, and the ledger runner must still fail closed rather than writing a partial cross-line artifact.
- **Boundary conditions**: ready vs missing vs partial states, canonical vs ten subset scans, and a fully ready region that can still build a ledger all stay deterministic.

## Steps

1. Add `src/WA/comparison/scaleout_readiness.py` that semantically inspects percentage / classification / trend families per region, records ready / missing / partial reasons, and emits machine-readable rows without pretending incomplete regions are fine.
2. Add `scripts/run_phase4_scaleout_readiness.py` as a thin CLI for `--region`, `--subset canonical`, and `--subset ten`, writing a readiness CSV/JSON report that operators can inspect before attempting a wide ledger run.
3. Keep `scripts/run_phase4_hotspot_ledger.py` fail-closed but extend its logs/help to point at the readiness surface and to emit per-region family context rather than a naked first exception.
4. Update `src/WA/test_selection.py`, `tests/test_comparison/test_scaleout_readiness.py`, `tests/test_comparison/test_hotspot_ledger.py`, and `CHANGELOG.md` so related-test routing and release notes both cover the new scale-out gate.

## Must-Haves

- [ ] The readiness report distinguishes `ready`, `missing`, and `partial` per family × region with explicit reasons and artifact paths.
- [ ] The unified ledger remains fail-closed and never writes a region ledger unless all three hotspot families are complete and semantically valid.
- [ ] Related-test routing and changelog notes make the new ten-region gate discoverable for future operators.

## Done when

- One CLI can report ten-region readiness before a wide rerun, and a ready region can still build a ledger while incomplete regions fail closed with explicit family-specific diagnostics.
  - Estimate: 2h
  - Files: src/WA/comparison/scaleout_readiness.py, scripts/run_phase4_scaleout_readiness.py, scripts/run_phase4_hotspot_ledger.py, src/WA/test_selection.py, tests/test_comparison/test_scaleout_readiness.py, tests/test_comparison/test_hotspot_ledger.py, CHANGELOG.md
  - Verify: ruff check src/WA/comparison/scaleout_readiness.py scripts/run_phase4_scaleout_readiness.py scripts/run_phase4_hotspot_ledger.py src/WA/test_selection.py tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py CHANGELOG.md
python scripts/run_phase4_scaleout_readiness.py --help
python scripts/run_phase4_hotspot_ledger.py --help
python -m pytest tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py -q
python scripts/run_related_tests.py src/WA/comparison/scaleout_readiness.py scripts/run_phase4_scaleout_readiness.py scripts/run_phase4_hotspot_ledger.py src/WA/test_selection.py
