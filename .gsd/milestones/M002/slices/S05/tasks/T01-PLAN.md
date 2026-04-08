---
estimated_steps: 22
estimated_files: 6
skills_used: []
---

# T01: Freeze one ordered ten-region selector and explicit subset plumbing

Freeze one ordered ten-region selector before restoring missing producers, so wide runs stop depending on hand-written region lists or `run_phase4_regional.py`'s macro+priority default.

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

## Inputs

- `config/priority_regions.yaml`
- `src/WA/comparison/evidence_contract.py`
- `scripts/run_phase4_regional.py`
- `scripts/run_phase4_trend_contract.py`
- `scripts/run_phase4_hotspot_ledger.py`
- `tests/test_comparison/test_evidence_contract.py`
- `tests/test_comparison/test_phase4_regional.py`

## Expected Output

- `src/WA/comparison/evidence_contract.py`
- `scripts/run_phase4_regional.py`
- `scripts/run_phase4_trend_contract.py`
- `scripts/run_phase4_hotspot_ledger.py`
- `tests/test_comparison/test_evidence_contract.py`
- `tests/test_comparison/test_phase4_regional.py`

## Verification

ruff check src/WA/comparison/evidence_contract.py scripts/run_phase4_regional.py scripts/run_phase4_trend_contract.py scripts/run_phase4_hotspot_ledger.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_phase4_regional.py
python scripts/run_phase4_regional.py --help
python scripts/run_phase4_trend_contract.py --help
python scripts/run_phase4_hotspot_ledger.py --help
python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_phase4_regional.py -q

## Observability Impact

Log `subset`, ordered `region_ids`, and selector-validation failures before job fanout so wide-run mistakes are visible in CLI output instead of only after artifacts land.
