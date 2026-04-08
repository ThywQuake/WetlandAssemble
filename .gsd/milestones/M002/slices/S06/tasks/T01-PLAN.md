---
estimated_steps: 24
estimated_files: 6
skills_used:
  - stash
---

# T01: Promote pack-safe semantic reload helpers for percentage and trend agreement

The pack builder should reopen contract artifacts through public helpers, not through script-private code or filename guesses. This task removes the main accidental-complexity trap before any figure/table assembly starts.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/percentage_backbone.py`, `src/WA/comparison/trend_contract.py`, `src/WA/visualization/phase4.py`, and `scripts/run_phase4_trend_contract.py` | Fail semantic reload with `region_id`, dataset/participant key, and stage context; do not let pack code import script-private helpers. | Reload work is local and cheap; retries stay deterministic because no network or long-running job is involved. | Reject missing agreement surface/summary pairs, mixed participant ids, mismatched time windows, or malformed percentage metadata instead of inferring filenames or keys. |

## Load Profile

- **Shared resources**: contract-backed CSV/NetCDF artifacts plus the downstream visualization helper surface.
- **Per-operation cost**: one semantic reload per requested region/family; negligible next to science compute.
- **10x breakpoint**: API drift and duplicated path logic break before runtime cost matters.

## Negative Tests

- **Malformed inputs**: missing agreement surface/summary files, malformed `contract_metadata_json`, and mixed participant ids.
- **Error paths**: wrapped reload helpers must preserve the failing `region_id` and key instead of bubbling a naked lower-level exception.
- **Boundary conditions**: ordered participant-set keys, expected time-range checks, and regions with only partial percentage rows all stay deterministic.

## Steps

1. Move trend-agreement semantic reload out of `scripts/run_phase4_trend_contract.py` into a public contract helper with strict validation for the surface/summary pair.
2. Update `scripts/run_phase4_trend_contract.py` to reuse the public helper so the runner and future pack code share one reload path.
3. Extend `src/WA/visualization/phase4.py` with pack-facing wrappers for percentage summary/surface and trend agreement summary/surface, keeping error messages consistent with existing classification/ledger wrappers.
4. Add focused regression coverage in `tests/test_comparison/test_trend_contract.py` and `tests/test_visualization/test_phase4.py` for successful semantic reopen plus wrapped failure diagnostics.

## Must-Haves

- [ ] Pack consumers never import `_load_trend_agreement_artifacts(...)` or duplicate contract path logic.
- [ ] Percentage summary/surface and trend agreement summary/surface reopen through public semantic helpers with stable signatures.
- [ ] Failure messages keep `region_id` plus dataset/participant key context.

## Done when

- A later pack task can load percentage and trend-agreement artifacts entirely through public helpers under `src/WA/comparison/` and `src/WA/visualization/phase4.py`.

## Inputs

- `src/WA/comparison/trend_contract.py`
- `scripts/run_phase4_trend_contract.py`
- `src/WA/comparison/percentage_backbone.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_trend_contract.py`
- `tests/test_visualization/test_phase4.py`

## Expected Output

- `src/WA/comparison/trend_contract.py`
- `scripts/run_phase4_trend_contract.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_trend_contract.py`
- `tests/test_visualization/test_phase4.py`

## Verification

ruff check src/WA/comparison/trend_contract.py scripts/run_phase4_trend_contract.py src/WA/comparison/percentage_backbone.py src/WA/visualization/phase4.py tests/test_comparison/test_trend_contract.py tests/test_visualization/test_phase4.py
python scripts/run_phase4_trend_contract.py --help
python -m pytest tests/test_comparison/test_trend_contract.py tests/test_visualization/test_phase4.py -q

## Observability Impact

Reload failures become inspectable through one public helper path with stage/key context instead of a script-private traceback.
