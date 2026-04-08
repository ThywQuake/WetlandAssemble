# S04: Unified hotspot ledger and cross-line evidence surfaces

**Goal:** 先补齐 trend hotspot contract，再把 percentage / trend / classification 三条线归一到一个共享的 hotspot ledger 与 cross-line reload surface，让 canonical subset 上层可以按 region / metric family / hotspot_id 稳定引用同一种 analysis object。
**Demo:** After this: After this: 三条主线的热点都能落到同一种 analysis object，上层可以按 region / metric family / hotspot_id 统一引用、排序、和交叉比较。

## Must-Haves

- Trend line emits contract-stable hotspot manifests keyed by the sorted participant set and re-openable through `src/WA/visualization/phase4.py`.
- Percentage, classification, and trend hotspot families normalize into one `unified_hotspot_ledger` artifact family with stable `analysis_object_id` rows and family-local score semantics.
- `scripts/run_phase4_hotspot_ledger.py` can rebuild or reload one region / canonical subset and refuses to write incomplete ledgers when any hotspot family is missing or invalid.
- Focused Phase 4 contract tests plus `python -m pytest tests/` prove the new artifact families, loaders, runner help text, and fail-closed behavior.

## Threat Surface

- **Abuse**: This slice has no auth or public input surface, but it reopens JSON/CSV/NetCDF metadata written by earlier stages. Treat mixed-region rows, spoofed participant-set keys, malformed `bbox` JSON, and stale or missing artifact paths as the trust-boundary abuse cases; fail closed instead of reconstructing filenames or silently dropping rows.
- **Data exposure**: No PII or secrets should flow through the ledger. Persist only dataset ids, region metadata, hotspot geometry, score fields, and contract/source paths already present in phase outputs.
- **Input trust**: Untrusted inputs are CLI `--region/--subset` selectors plus on-disk contract artifacts reopened from `results/phase4`; every loader must validate region, participant set, row counts, and metadata JSON before a ledger write.

## Requirement Impact

- **Requirements touched**: `R105` (owned) and `R101` (supported) because S04 must expose one shared hotspot analysis object while preserving the three-line evidence contract established in S01-S03.
- **Re-verify**: Re-run percentage/classification/trend hotspot reload tests, the new ledger loader/CLI tests, `scripts/run_related_tests.py ...`, and full `python -m pytest tests/` to prove downstream consumers still reopen artifacts semantically and fail closed on malformed or incomplete families.
- **Decisions revisited**: `D031`, `D034`, `D035`, and `D036` because the new trend-hotspot and unified-ledger stems must keep participant-set naming deterministic and continue reserving `__` for the outer evidence-contract separator.

## Proof Level

- This slice proves: contract + integration (real runtime required: yes for post-merge HPC smoke; human/UAT required: no)

## Verification

- `ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_hotspots.py src/WA/comparison/hotspot_ledger.py src/WA/visualization/phase4.py scripts/run_phase4_trend_contract.py scripts/run_phase4_hotspot_ledger.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md`
- `python scripts/run_phase4_trend_contract.py --help`
- `python scripts/run_phase4_hotspot_ledger.py --help`
- `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py -q`
- `python scripts/run_related_tests.py src/WA/comparison/trend_hotspots.py src/WA/comparison/hotspot_ledger.py scripts/run_phase4_trend_contract.py scripts/run_phase4_hotspot_ledger.py src/WA/visualization/phase4.py src/WA/test_selection.py`
- `python -m pytest tests/`
- Inspect stage-tagged logs `agreement`, `trend-hotspots`, and `ledger`, plus semantic reload failures in `src/WA/visualization/phase4.py`, to confirm incomplete or malformed families fail closed before a ledger write.

## Integration Closure

- Upstream surfaces consumed: `src/WA/comparison/percentage_hotspots.py`, `src/WA/comparison/classification_contract.py`, and the trend agreement artifacts from `src/WA/comparison/trend_contract.py`, all reopened semantically through `src/WA/visualization/phase4.py`.
- New wiring introduced in this slice: `src/WA/comparison/trend_hotspots.py`, `src/WA/comparison/hotspot_ledger.py`, `scripts/run_phase4_hotspot_ledger.py`, and phase4 reload helpers for trend hotspots / unified ledgers.
- What remains before the milestone is truly usable end-to-end: run the narrow-first HPC ladder (`--region amazon --no-skip` on percentage, trend, classification, then ledger; then `--subset canonical --no-skip`) and feed the ledger into S05 scale-out.

## Tasks
- [ ] **T01: Add contract-backed trend hotspot manifests and semantic reloads** — Close the main scientific gap first: trend outputs currently stop at agreement surfaces and summaries, so this task creates the missing contract-stable hotspot family before any cross-line ledger work starts.

## Steps

1. Extend `src/WA/comparison/evidence_contract.py` and `tests/test_comparison/test_evidence_contract.py` so the contract locks both `trend_hotspot_manifest` and `unified_hotspot_ledger` artifact families before new writers/runners are added.
2. Add `src/WA/comparison/trend_hotspots.py` with path helpers, disagreement-first hotspot selection over `TrendAgreementResult` (`disputed` candidate mask, `disagreement_score = 1 - agreement_ratio`, `slope_std` tie-breaker), JSON/CSV writers, validators, and provenance-rich manifest/table reload helpers.
3. Extend `scripts/run_phase4_trend_contract.py` with a dedicated `trend-hotspots` stage after agreement write/reload, and add `load_phase4_contract_trend_hotspot_table(...)` to `src/WA/visualization/phase4.py` so downstream code reopens the new family by semantics instead of filename guessing.
4. Add focused tests in `tests/test_comparison/test_trend_hotspots.py` and `tests/test_visualization/test_phase4.py` covering stable relpaths, participant-set metadata, malformed bbox/metadata failures, trend hotspot reload behavior, and runner help/smoke expectations.

## Must-Haves

- [ ] Trend hotspot artifacts are keyed by sorted participant-set ids and stay contract-stable alongside the existing trend surface/summary/agreement families.
- [ ] Trend hotspot ranking is disagreement-first (`1 - agreement_ratio`) and never redefines trend correctness as raw slope magnitude.
- [ ] Runner logging exposes a dedicated `trend-hotspots` stage with region/participant context and fails before any partial JSON/CSV pair is treated as valid.

## Done when

- One region's trend agreement output can be written and reloaded as a hotspot manifest + CSV companion through stable contract helpers, and focused tests pin the ranking, metadata, and failure behavior.
  - Estimate: 2h
  - Files: src/WA/comparison/evidence_contract.py, src/WA/comparison/trend_hotspots.py, scripts/run_phase4_trend_contract.py, src/WA/visualization/phase4.py, tests/test_comparison/test_evidence_contract.py, tests/test_comparison/test_trend_hotspots.py, tests/test_visualization/test_phase4.py
  - Verify: ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_hotspots.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_visualization/test_phase4.py
python scripts/run_phase4_trend_contract.py --help
python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_visualization/test_phase4.py -q
- [ ] **T02: Build the unified hotspot ledger and ledger CLI** — Once all three lines have hotspot objects, normalize them into one ledger and expose a thin runner/reload surface so later slices can compare hotspots by region and metric family without reverse-engineering three separate schemas.

## Steps

1. Add `src/WA/comparison/hotspot_ledger.py` that reloads percentage, classification, and trend hotspot tables semantically, validates required families, and normalizes them into one long-form ledger keyed by `analysis_object_id` with shared provenance fields plus family-local JSON payloads.
2. Extend `src/WA/visualization/phase4.py` with `load_phase4_unified_hotspot_ledger(...)` (and any small derived comparison helper it needs), keeping path construction inside contract helpers and failing closed on missing families, mixed regions, malformed metadata JSON, or duplicate analysis-object ids.
3. Add `scripts/run_phase4_hotspot_ledger.py` as a thin CLI that resolves region/subset selection, reuses the semantic reload helpers, writes the ledger only when all three hotspot families are present and valid, and logs a dedicated `ledger` stage plus explicit skip/rebuild decisions.
4. Add focused tests in `tests/test_comparison/test_hotspot_ledger.py` and `tests/test_visualization/test_phase4.py`, then wire the new module/runner into `src/WA/test_selection.py` and `CHANGELOG.md` so related-test routing and user-facing release notes cover the new contract surface and HPC ladder.

## Must-Haves

- [ ] Ledger rows form one long-form shared analysis object while preserving family-local score semantics instead of pretending percentage, entropy, and disagreement are raw-score comparable.
- [ ] The ledger runner writes nothing for a region unless percentage, classification, and trend hotspot families are all present and semantically valid.
- [ ] Downstream loaders can reopen the unified ledger by semantics and expose enough provenance (`surface_output_path`, `summary_output_path`, metadata JSON) for later comparison and figure work.

## Done when

- A single CLI and loader can reopen or rebuild one region's unified hotspot ledger from the three contract hotspot families, and focused tests prove fail-closed behavior for missing/malformed families plus stable long-form row normalization.
  - Estimate: 2h
  - Files: src/WA/comparison/hotspot_ledger.py, src/WA/visualization/phase4.py, scripts/run_phase4_hotspot_ledger.py, tests/test_comparison/test_hotspot_ledger.py, tests/test_visualization/test_phase4.py, src/WA/test_selection.py, CHANGELOG.md
  - Verify: ruff check src/WA/comparison/hotspot_ledger.py src/WA/visualization/phase4.py scripts/run_phase4_hotspot_ledger.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md
python scripts/run_phase4_hotspot_ledger.py --help
python -m pytest tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py -q
python scripts/run_related_tests.py src/WA/comparison/hotspot_ledger.py scripts/run_phase4_hotspot_ledger.py src/WA/visualization/phase4.py src/WA/test_selection.py
