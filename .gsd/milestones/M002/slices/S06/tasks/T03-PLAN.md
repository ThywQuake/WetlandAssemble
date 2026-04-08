---
estimated_steps: 24
estimated_files: 3
skills_used:
  - stash
  - sync-hpc
---

# T03: Gate complete-pack claims behind strict readiness and ledger proof

The slice is not done when files merely exist. This task makes the pack itself the milestone integration proof surface by requiring clean readiness plus unified-ledger reopen before a ten-region pack can claim completeness.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/scaleout_readiness.py`, `src/WA/comparison/hotspot_ledger.py`, and the new pack CLI/module | Exit non-zero with `region_id`, `metric_family`, and proof-stage context; never emit a “strict success” report from partial inputs. | Preflight remains region-scoped so one incomplete region yields explicit proof diagnostics instead of blocking discovery of other gaps. | Reject missing readiness rows, `partial` family states, absent ledgers, or ledger/selector mismatches instead of silently downgrading to a best-effort pack. |

## Load Profile

- **Shared resources**: readiness CSV/JSON reports, unified ledgers, and the final pack output tree.
- **Per-operation cost**: one readiness inspection plus one ledger reopen per region; still cheap compared to the science reruns.
- **10x breakpoint**: diagnostic clarity and proof-artifact size degrade before runtime cost matters.

## Negative Tests

- **Malformed inputs**: missing readiness reports, mixed-region readiness rows, absent ledger CSVs, and proof outputs pointed inside `results/phase4`.
- **Error paths**: `--strict` must fail closed on `missing`/`partial`, while the non-strict path must still write an explicit incomplete-proof report instead of pretending the pack is complete.
- **Boundary conditions**: one-region `--strict` proof, ordered ten-region proof, and mismatched participant ids all keep deterministic verdicts and logs.

## Steps

1. Extend `src/WA/visualization/phase4_pack.py` so pack assembly runs a readiness preflight, reopens unified ledgers for every requested region, and writes machine-readable plus Markdown proof artifacts summarizing readiness, ledger provenance, manifest path, and figure/table counts.
2. Extend `scripts/run_phase4_evidence_pack.py` with `--strict` and explicit incomplete-proof behavior, keeping the exit code and logs aligned with the proof verdict.
3. Expand `tests/test_visualization/test_phase4_pack.py` to cover strict failure on incomplete readiness, success when readiness/ledgers are clean, and proof-artifact contents; keep comparison-boundary tests in the verification command so the pack stays wired to the real contract surfaces.
4. In the task summary and UAT, hand off the exact HPC rerun ladder for real proof: percentage (`--start-year 1990 --end-year 2020 --surface-year 2016 --no-skip`), classification (`--year 2016 --no-skip`), trend submit fanout, readiness, ledger, then `python scripts/run_phase4_evidence_pack.py --subset ten --strict ...`.

## Must-Haves

- [ ] `--strict` never reports success unless readiness and ledger reopen cleanly for every requested region.
- [ ] Proof artifacts record the resolved regions, readiness verdicts, ledger paths, participant keys, manifest path, and pack output counts.
- [ ] The handoff commands for HPC reruns stay explicit, use `--no-skip`, and match the current trend participant defaults that include `topmodel`.

## Done when

- `python scripts/run_phase4_evidence_pack.py --subset ten --strict ...` becomes the single complete-pack claim surface, and missing science inputs produce explicit proof diagnostics instead of a misleading paper pack.

## Inputs

- `src/WA/visualization/phase4_pack.py`
- `scripts/run_phase4_evidence_pack.py`
- `tests/test_visualization/test_phase4_pack.py`
- `src/WA/comparison/scaleout_readiness.py`
- `src/WA/comparison/hotspot_ledger.py`
- `src/WA/comparison/trend_contract.py`

## Expected Output

- `src/WA/visualization/phase4_pack.py`
- `scripts/run_phase4_evidence_pack.py`
- `tests/test_visualization/test_phase4_pack.py`

## Verification

ruff check src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py tests/test_visualization/test_phase4_pack.py
python scripts/run_phase4_evidence_pack.py --help
python -m pytest tests/test_visualization/test_phase4_pack.py tests/test_comparison/test_hotspot_ledger.py tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_classification_contract.py tests/test_comparison/test_trend_hotspots.py -q
python scripts/run_related_tests.py src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py

## Observability Impact

Strict mode writes proof artifacts and stage-tagged diagnostics that show which region/family blocked completion and where the failing readiness/ledger evidence lives.
