---
estimated_steps: 24
estimated_files: 7
skills_used: []
---

# T02: Restore the percentage contract backbone, hotspots, and runner

The current snapshot is missing `src/WA/comparison/percentage_backbone.py`, `src/WA/comparison/percentage_hotspots.py`, and `scripts/run_phase4_percentage_contract.py` even though older slice text claims they already exist. Restore that percentage producer chain intentionally on top of the real `phase4_regional.py` and `0.25°` surface backbones so the unified ledger can consume real percentage families instead of synthetic fixtures.

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

## Inputs

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/phase4_regional.py`
- `src/WA/comparison/trends.py`
- `src/WA/phase37_hotspots.py`
- `scripts/plot_tropical_wetland_025deg.py`
- `tests/test_plot_tropical_wetland_025deg.py`

## Expected Output

- `src/WA/comparison/percentage_backbone.py`
- `src/WA/comparison/percentage_hotspots.py`
- `scripts/run_phase4_percentage_contract.py`
- `scripts/plot_tropical_wetland_025deg.py`
- `tests/test_comparison/test_percentage_backbone.py`
- `tests/test_comparison/test_percentage_hotspots.py`
- `tests/test_plot_tropical_wetland_025deg.py`

## Verification

ruff check src/WA/comparison/percentage_backbone.py src/WA/comparison/percentage_hotspots.py scripts/run_phase4_percentage_contract.py scripts/plot_tropical_wetland_025deg.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_plot_tropical_wetland_025deg.py
python scripts/run_phase4_percentage_contract.py --help
python -m pytest tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_plot_tropical_wetland_025deg.py -q
python scripts/run_related_tests.py src/WA/comparison/percentage_backbone.py src/WA/comparison/percentage_hotspots.py scripts/run_phase4_percentage_contract.py scripts/plot_tropical_wetland_025deg.py

## Observability Impact

Expose `stage=percentage-surface` / `stage=percentage-hotspots` logs, surface-cache hit/miss paths, GWD30 tile-restore counts, and hotspot write/reload decisions so operators can see exactly where a ten-region run stopped.
