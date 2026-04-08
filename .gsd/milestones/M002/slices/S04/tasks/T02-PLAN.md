---
estimated_steps: 12
estimated_files: 7
skills_used: []
---

# T02: Build the unified hotspot ledger and ledger CLI

Once all three lines have hotspot objects, normalize them into one ledger and expose a thin runner/reload surface so later slices can compare hotspots by region and metric family without reverse-engineering three separate schemas.

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

## Inputs

- `src/WA/comparison/percentage_hotspots.py`
- `src/WA/comparison/classification_contract.py`
- `src/WA/comparison/trend_hotspots.py`
- `src/WA/visualization/phase4.py`
- `src/WA/test_selection.py`
- `CHANGELOG.md`

## Expected Output

- `src/WA/comparison/hotspot_ledger.py`
- `src/WA/visualization/phase4.py`
- `scripts/run_phase4_hotspot_ledger.py`
- `tests/test_comparison/test_hotspot_ledger.py`
- `tests/test_visualization/test_phase4.py`
- `src/WA/test_selection.py`
- `CHANGELOG.md`

## Verification

ruff check src/WA/comparison/hotspot_ledger.py src/WA/visualization/phase4.py scripts/run_phase4_hotspot_ledger.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md
python scripts/run_phase4_hotspot_ledger.py --help
python -m pytest tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py -q
python scripts/run_related_tests.py src/WA/comparison/hotspot_ledger.py scripts/run_phase4_hotspot_ledger.py src/WA/visualization/phase4.py src/WA/test_selection.py

## Observability Impact

- Signals added/changed: `ledger` stage logging plus per-family completeness validation and skip/rebuild decisions.
- How a future agent inspects this: run `python scripts/run_phase4_hotspot_ledger.py --help`, reload the ledger via `load_phase4_unified_hotspot_ledger(...)`, and compare `analysis_object_id` / provenance fields against the three source hotspot tables.
- Failure state exposed: missing hotspot families, malformed JSON, duplicate analysis-object ids, and mixed-region rows prevent a ledger write and surface explicit family-specific errors.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/percentage_hotspots.py`, `src/WA/comparison/classification_contract.py`, `src/WA/comparison/trend_hotspots.py`, and the new ledger CLI/reload surfaces | Fail the region before any ledger file is written and call out which hotspot family or reload step was missing or invalid. | Keep skip/rebuild behavior region-scoped so reruns can resume without silently reusing an incomplete ledger. | Reject mixed regions, duplicate `analysis_object_id` values, malformed metadata JSON, or missing provenance fields rather than coercing a partial cross-line row set.

## Load Profile

- **Shared resources**: three hotspot families under `results/phase4`, shared phase4 reload helpers, and the long-form ledger outputs.
- **Per-operation cost**: reopen three hotspot families per region, normalize row schemas, compute family-local ranks or percentiles, and write one region ledger plus semantic-loader tests.
- **10x breakpoint**: repeated cross-family reload and concat plus per-region completeness validation become the first wall-time bottleneck when scaling from the canonical subset to all ten regions.

## Negative Tests

- **Malformed inputs**: missing one hotspot family, malformed `line_specific_json` / `contract_metadata_json`, mixed region ids, and duplicate `analysis_object_id` candidates.
- **Error paths**: missing contract artifacts, participant-set mismatches, or ledger writes attempted with incomplete families must fail closed.
- **Boundary conditions**: regions with hotspot shortfalls, different family row counts, and family-local percentiles/ranks that must stay deterministic without pretending raw scores are globally comparable.
