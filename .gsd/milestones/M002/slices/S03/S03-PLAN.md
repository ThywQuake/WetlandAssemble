# S03: Classification-disagreement backbone on the shared contract

**Goal:** 把 `phase36.py` 的全球 500m 分类分歧产品与 `phase37_hotspots.py` 的热点选择接到 S01/S02 已建立的 shared evidence contract：让 canonical subset 的 classification disagreement surfaces、regional summaries、hotspot manifests、以及 phase4 reload/runner 入口都走稳定 relpath/metadata，而不是停留在 legacy 全局文件与 ad hoc 清单。
**Demo:** After this: After this: `G2017 / GLWD / GWD30` 能在 `500m` / unified-8-class 口径下产出 contract-aligned entropy / majority / agreement products 与 classification hotspot manifests。

## Tasks
- [x] **T01: Added classification artifact families and dataset-slot stem validation to the shared evidence contract.** — Define the naming/layout contract before adding any new orchestration so the classification line cannot drift into a second filename grammar.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/evidence_contract.py`, existing trend artifact semantics, and the real priority-region catalog | Fail before any downstream writer work starts, with the missing artifact kind or region/metadata collision called out explicitly. | N/A for the pure contract layer; keep the naming API deterministic so later retries do not depend on hidden state. | Reject unknown artifact kinds, non-JSON-safe metadata, and any accidental collision with the established percentage/trend stem structure. |

## Load Profile

- **Shared resources**: in-memory contract metadata and the stable relpath namespace under the Phase 4 output root.
- **Per-operation cost**: trivial path/metadata generation plus focused test assertions.
- **10x breakpoint**: namespace drift, not runtime load — the real failure mode is semantic collision once more artifact families are added.

## Negative Tests

- **Malformed inputs**: unknown classification artifact kind, non-serializable extra metadata, and bad participant-set-like dataset ids.
- **Error paths**: missing required artifact semantics should fail contract construction instead of silently omitting a family.
- **Boundary conditions**: classification stems must stay distinct from the existing percentage/trend stems while still following the same `<dataset_or_key>__<region>__<suffix>` grammar.

## Steps

1. Extend `src/WA/comparison/evidence_contract.py` so `ArtifactKind`, contract validation, and `default_artifact_semantics()` include dedicated classification families for region-scoped surfaces, summaries, and hotspot manifests.
2. Keep the classification file-stem grammar aligned with the trend-agreement convention: the participant-set key lives in the dataset slot, while `__` remains reserved for the outer stem separator.
3. Extend `tests/test_comparison/test_evidence_contract.py` so the new relpaths, metadata payloads, and participant-set naming are locked before any adapter code is added.

## Must-Haves

- [ ] Classification artifact families exist without renaming or destabilizing the S01/S02 percentage/trend families.
- [ ] The contract tests prove deterministic classification relpaths and JSON-safe metadata for the shared `participant_set_key` convention.

## Done when

- `EvidenceContract` can describe the classification surface/summary/hotspot families and focused contract tests pin the exact relpaths/metadata that later tasks will consume.
  - Estimate: 75m
  - Files: src/WA/comparison/evidence_contract.py, tests/test_comparison/test_evidence_contract.py, src/WA/comparison/trend_contract.py
  - Verify: ruff check src/WA/comparison/evidence_contract.py tests/test_comparison/test_evidence_contract.py
python -m pytest tests/test_comparison/test_evidence_contract.py -q
- [x] **T02: Write classification contract adapters for phase3.6 surfaces and phase3.7 hotspots** — Create the adapter layer that turns the proven global disagreement/hotspot producers into region-scoped contract artifacts before any CLI orchestration is added.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/phase36.py`, `src/WA/phase37_hotspots.py`, `src/WA/visualization/phase37.py`, and `src/WA/classification.py` | Fail before writing any contract artifact, with `region_id`, `participant_set_key`, and source artifact path included in the exception/log context. | Region slicing or hotspot rewrite must remain restartable at the region boundary; never leave partially written JSON/CSV pairs that look complete. | Reject missing `joint_valid_mask` / `*_source_dominant_class` variables, mixed-region hotspot rows, malformed bbox payloads, or participant-set metadata mismatches instead of inferring silently. |

## Load Profile

- **Shared resources**: global 500m phase3.6 NetCDF outputs, phase3.7 hotspot manifest/CSV inputs, and the Phase 4 contract output root.
- **Per-operation cost**: reopen one metrics NetCDF plus one dominant-class NetCDF, subset them to a contract bbox, derive region-scoped summary stats, and rewrite one hotspot JSON/CSV pair per region.
- **10x breakpoint**: repeated NetCDF slicing/materialization and hotspot-manifest rewriting become the first I/O bottleneck when widening from the canonical subset to all ten regions.

## Negative Tests

- **Malformed inputs**: missing source-dominant variables, malformed bbox JSON, wrong region ids, and reordered participant ids.
- **Error paths**: missing phase3.6 source files, malformed phase3.7 hotspot manifests, or empty-region summaries all raise explicit validation errors.
- **Boundary conditions**: descending-lat datasets, hotspot shortfall regions, and compatibility with existing `entropy-<region>-NNN` hotspot ids stay intact while the contract metadata adds participant-set context.

## Steps

1. Add `src/WA/comparison/classification_contract.py` with stable output-path helpers plus a deterministic `participant_set_key` builder for the fixed `g2017` / `glwd_v2` / `gwd30` trio.
2. Write region-scoped classification surface builders that subset the phase3.6 metrics/dominant datasets with `subset_phase37_plot_dataset_to_bbox(...)`, preserve the entropy/agreement/joint-valid fields, and keep all three unified + source dominant-class layers.
3. Add summary/hotspot writer + validator helpers that attach contract metadata, explicit source artifact paths, quota/shortfall status, and region-scoped summary rows without reimplementing the phase3.6 or phase3.7 math.
4. Add `tests/test_comparison/test_classification_contract.py` to prove stable relpaths, metadata JSON, summary validation, hotspot manifest rewriting, and readable failure modes on malformed inputs.

## Must-Haves

- [ ] The adapter layer wraps existing phase3.6 / phase3.7 outputs; it does not fork the disagreement math or hotspot-selection rules.
- [ ] Region-scoped contract surfaces keep the full dominant/source-dominant diagnostic payload needed by downstream plotting and S04 ledger work.

## Done when

- Synthetic tests can round-trip phase3.6 + phase3.7 fixtures into stable contract surfaces, summaries, and hotspot manifests, and malformed inputs fail before any partial artifact pair is left behind.
  - Estimate: 2h
  - Files: src/WA/comparison/classification_contract.py, src/WA/comparison/phase36.py, src/WA/phase37_hotspots.py, src/WA/visualization/phase37.py, src/WA/classification.py, tests/test_comparison/test_classification_contract.py
  - Verify: ruff check src/WA/comparison/classification_contract.py tests/test_comparison/test_classification_contract.py
python -m pytest tests/test_comparison/test_classification_contract.py -q
- [x] **T03: Added the canonical Phase 4 classification-contract runner and semantic reload helpers.** — Close the slice with a real contract-aware entrypoint and downstream reload helpers so S04 can consume classification artifacts without guessing filenames.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/classification_contract.py`, `src/WA/comparison/phase36.py`, `src/WA/phase37_hotspots.py`, `src/WA/visualization/phase4.py`, and related-test routing | Fail with stage, `region_id`, `participant_set_key`, and source-path context; never emit a half-written region directory that looks complete. | Keep `--skip` / `--no-skip` behavior visible in logs so long canonical-subset reruns can resume at the region boundary. | Reject bad `--subset` + `--region` combinations, missing source artifacts on reload, and malformed contract metadata instead of inferring filenames or participant sets from directory scans. |

## Load Profile

- **Shared resources**: phase3.6 cache directories, phase3.7 candidate cache/hotspot outputs, and the shared `results/phase4` contract tree.
- **Per-operation cost**: one global disagreement run/reload, one hotspot-selection run/reload, and one contract write/reload cycle per selected region.
- **10x breakpoint**: GWD30-backed phase3.6 materialization and repeated hotspot selection dominate wall time once the canonical subset expands to all ten regions.

## Negative Tests

- **Malformed inputs**: unknown region ids, illegal `--subset` + `--region` combinations, and broken classification metadata JSON during reload.
- **Error paths**: missing phase3.6 outputs, missing phase3.7 hotspot artifacts, or malformed classification summaries/hotspot CSVs surface explicit CLI/reload failures.
- **Boundary conditions**: canonical-subset ordering, one-region smoke runs, and reloads from already-written contract outputs all preserve the same participant-set key and region relpaths.

## Steps

1. Add `scripts/run_phase4_classification_contract.py` as a thin CLI patterned after `scripts/run_phase4_trend_contract.py`: resolve evidence-contract regions/subsets, preserve `--standardized-dir`, `--output-root`, `--year`, `--progress`, and `--no-skip`, and document the narrow-first HPC ladder in the help text.
2. Compose the existing producers instead of rewriting them: call `run_phase36_analysis()` for the global backbone, run or reuse `run_phase37_hotspot_selection()` for hotspot candidates, then write region-scoped contract artifacts through `src/WA/comparison/classification_contract.py`.
3. Extend `src/WA/visualization/phase4.py` with classification reload helpers for region summaries and hotspot tables, and expand `tests/test_visualization/test_phase4.py` to prove missing-path, malformed-metadata, and participant-set/region mismatch failures stay explicit.
4. Update `src/WA/test_selection.py`, `docs/testing/test-categories.md`, and `CHANGELOG.md` so related-test routing and user-facing release notes both know about the new classification contract path.

## Must-Haves

- [ ] The new runner stays a thin orchestration layer over `phase36.py`, `phase37_hotspots.py`, and `classification_contract.py`; it does not absorb scientific logic from those modules.
- [ ] Downstream reload helpers can reopen classification contract summaries/hotspot tables by semantics, and related-test routing covers the new runner/adapter files.

## Done when

- One CLI plus reload helpers cover execution and consumption, the help text documents the HPC ladder, and focused tests/related-test routing prove the classification contract is wired end to end.
  - Estimate: 2h
  - Files: scripts/run_phase4_classification_contract.py, src/WA/comparison/classification_contract.py, src/WA/visualization/phase4.py, tests/test_visualization/test_phase4.py, src/WA/test_selection.py, docs/testing/test-categories.md, CHANGELOG.md
  - Verify: ruff check scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py tests/test_visualization/test_phase4.py src/WA/test_selection.py docs/testing/test-categories.md CHANGELOG.md
python scripts/run_phase4_classification_contract.py --help
python -m pytest tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py -q
python scripts/run_related_tests.py src/WA/comparison/classification_contract.py scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py
