---
estimated_steps: 23
estimated_files: 3
skills_used: []
---

# T03: Wire contract-managed regional summaries across the canonical subset

Close the summary side by making the live Phase-4 Stage-2 regional route consume the new contract layer instead of writing one-off CSVs that later slices have to rediscover semantically.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Berkeley standardized files and Stage-1 GWD30 tile manifests | Fail with `region_id`, `dataset_id`, and source path in the log rather than returning partial tables. | Keep year-split cache reuse intact so a long rerun resumes from the last completed year/region. | Reject empty mask subsets, incomplete year tables, or missing contract metadata before writing final summary tables. |

## Load Profile

- **Shared resources**: Berkeley-valid mask caches, per-region CSV caches, and Stage-1 pixel-statistics tile dirs.
- **Per-operation cost**: one mask build plus per-year/per-region table reduction over potentially many tiles.
- **10x breakpoint**: spatial I/O and mask reprojection cost dominate first when widening from one region/year to many regions/years.

## Negative Tests

- **Malformed inputs**: bad `--region`/`--subset` selections, empty bbox masks, and tables missing `series_type` or contract fields.
- **Error paths**: missing Berkeley source slice, unreadable yearly cache, or absent Stage-1 manifest raises a region-specific error.
- **Boundary conditions**: 2016-only narrow-first runs, annual table completeness, and canonical subset expansion keep the same table schema.

## Steps

1. Update `src/WA/comparison/phase4_regional.py` to resolve regions through `src/WA/comparison/evidence_contract.py`, propagate Berkeley-valid semantics into contract metadata, and expose helpers for canonical subset summary output naming.
2. Refactor `scripts/run_phase4_regional.py` so it can target `--subset canonical` as well as explicit `--region` selections, while preserving `--no-skip`, year filters, and visible progress.
3. Extend `tests/test_comparison/test_phase4_regional.py` with assertions around contract region resolution, Berkeley-valid metadata, Stage-1 manifest restoration, and canonical subset naming/layout.
4. Keep the narrow-first operational ladder explicit in CLI help/comments: Stage-1 year build first, Stage-2 amazon summary second, canonical subset expansion only after those pass.

## Must-Haves

- [ ] Contract-managed regional summaries preserve the live Stage-1/Stage-2 route instead of reopening the stale full-tropics reducer path.
- [ ] Regional tables expose enough metadata that later slices can tell which grid/mask semantics produced them.

## Done when

- The Phase-4 regional route resolves canonical subset regions through the new contract, writes stable summary outputs, and the regional regression tests cover the new metadata/path semantics.

## Inputs

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/phase4_regional.py`
- `scripts/run_phase4_regional.py`
- `tests/test_comparison/test_phase4_regional.py`

## Expected Output

- `src/WA/comparison/phase4_regional.py`
- `scripts/run_phase4_regional.py`
- `tests/test_comparison/test_phase4_regional.py`

## Verification

python -m pytest tests/test_comparison/test_phase4_regional.py -q
python scripts/run_related_tests.py src/WA/comparison/phase4_regional.py scripts/run_phase4_regional.py

## Observability Impact

- Signals added/changed: Berkeley-valid mask source-window logs, per-region table cache write/hit logs, and dataset/year counts in the Stage-2 path.
- How a future agent inspects this: inspect `results/phase4/cache/masks/berkeley_valid/...`, `results/phase4/cache/<dataset>/<region>/regional_series.csv`, and CLI stdout/stderr.
- Failure state exposed: missing Berkeley slices, empty mask subsets, or incomplete annual tables are localized by dataset/region/year in logs and cache paths.
