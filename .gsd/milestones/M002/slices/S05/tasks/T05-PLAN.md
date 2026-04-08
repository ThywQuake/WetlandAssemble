---
estimated_steps: 24
estimated_files: 7
skills_used: []
---

# T05: Add ten-region readiness reporting and keep the ledger fail-closed

Once real percentage, classification, and trend producers exist again, close the slice with one operator-facing readiness surface that scans `--subset ten`, reports which regions have complete three-line families, and leaves `scripts/run_phase4_hotspot_ledger.py` as the fail-closed final gate.

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

## Inputs

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/hotspot_ledger.py`
- `src/WA/comparison/trend_hotspots.py`
- `scripts/run_phase4_hotspot_ledger.py`
- `src/WA/test_selection.py`
- `CHANGELOG.md`

## Expected Output

- `src/WA/comparison/scaleout_readiness.py`
- `scripts/run_phase4_scaleout_readiness.py`
- `scripts/run_phase4_hotspot_ledger.py`
- `src/WA/test_selection.py`
- `tests/test_comparison/test_scaleout_readiness.py`
- `tests/test_comparison/test_hotspot_ledger.py`
- `CHANGELOG.md`

## Verification

ruff check src/WA/comparison/scaleout_readiness.py scripts/run_phase4_scaleout_readiness.py scripts/run_phase4_hotspot_ledger.py src/WA/test_selection.py tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py CHANGELOG.md
python scripts/run_phase4_scaleout_readiness.py --help
python scripts/run_phase4_hotspot_ledger.py --help
python -m pytest tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py -q
python scripts/run_related_tests.py src/WA/comparison/scaleout_readiness.py scripts/run_phase4_scaleout_readiness.py scripts/run_phase4_hotspot_ledger.py src/WA/test_selection.py

## Observability Impact

Write readiness CSV/JSON rows with `region_id`, `metric_family`, `status`, `reason`, and artifact paths, and have ledger logs point back to those statuses so operators can distinguish science gaps from artifact-integrity gaps immediately.
