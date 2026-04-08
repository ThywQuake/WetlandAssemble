---
estimated_steps: 24
estimated_files: 6
skills_used:
  - stash
---

# T02: Build the derived paper-pack module and CLI

This is the primary R113 delivery: turn contract-backed science artifacts into thesis-facing figures, joined evidence tables, narrative summaries, and a deterministic pack manifest without mutating the science contract tree.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/visualization/phase4.py`, `src/WA/comparison/percentage_backbone.py`, `src/WA/comparison/classification_contract.py`, `src/WA/comparison/trend_contract.py`, and `src/WA/comparison/hotspot_ledger.py` | Abort pack assembly before claiming success; do not write a final manifest that hides missing figures or tables. | Figure/table generation stays region-scoped so retries can resume after fixing one bad region or one malformed input family. | Reject mixed-region summaries, incomplete joined-table inputs, or malformed ledger rows instead of silently dropping columns or regions. |

## Load Profile

- **Shared resources**: ten-region contract artifacts plus the new derived pack output tree under `results/figures/phase4_pack/`.
- **Per-operation cost**: two percentage plots per region plus table joins and markdown/JSON serialization.
- **10x breakpoint**: figure rendering and wide joined-table materialization dominate before contract reload cost does.

## Negative Tests

- **Malformed inputs**: empty region selection, missing annual/climatology rows, malformed ledger JSON columns, and invalid output-root paths.
- **Error paths**: if one family fails semantic reload, the CLI must exit before emitting a “complete” pack manifest.
- **Boundary conditions**: one-region smoke packs and ordered ten-region packs both keep deterministic relpaths and region ordering.

## Steps

1. Add `src/WA/visualization/phase4_pack.py` to reopen contract-backed inputs semantically and assemble percentage figures, one joined regional evidence table, one unified hotspot table, one narrative summary, and a deterministic pack manifest.
2. Add `scripts/run_phase4_evidence_pack.py` as a thin CLI over the pack module, supporting `--region` and `--subset ten`, explicit keys/participant ids, and a pack output root separate from `results/phase4`.
3. Add fixture-backed tests in `tests/test_visualization/test_phase4_pack.py` that assert figure/table/summary/manifest existence, joined-table schema, provenance capture, and deterministic output relpaths.
4. Wire the new paths into `src/WA/test_selection.py`, `docs/testing/test-categories.md`, and `CHANGELOG.md` so targeted verification and user-facing notes both cover the pack CLI.

## Must-Haves

- [ ] The pack writes derived outputs only under the dedicated pack root and never mutates the underlying science contract artifacts.
- [ ] The manifest records resolved regions, dataset/participant keys, and exact source artifact paths so the pack is replayable.
- [ ] At minimum the pack emits percentage interannual + climatology figures, a joined regional evidence table, a unified hotspot table, and a narrative summary.

## Done when

- A fixture-backed pack run can assemble the paper-facing deliverables from semantic reload helpers alone, and the CLI help/docs make that surface discoverable.

## Inputs

- `src/WA/visualization/phase4.py`
- `src/WA/comparison/percentage_backbone.py`
- `src/WA/comparison/classification_contract.py`
- `src/WA/comparison/trend_contract.py`
- `src/WA/comparison/hotspot_ledger.py`
- `src/WA/test_selection.py`
- `docs/testing/test-categories.md`
- `CHANGELOG.md`

## Expected Output

- `src/WA/visualization/phase4_pack.py`
- `scripts/run_phase4_evidence_pack.py`
- `tests/test_visualization/test_phase4_pack.py`
- `src/WA/test_selection.py`
- `docs/testing/test-categories.md`
- `CHANGELOG.md`

## Verification

ruff check src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py tests/test_visualization/test_phase4_pack.py src/WA/test_selection.py docs/testing/test-categories.md CHANGELOG.md
python scripts/run_phase4_evidence_pack.py --help
python -m pytest tests/test_visualization/test_phase4_pack.py tests/test_visualization/test_phase4.py -q
python scripts/run_related_tests.py src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py src/WA/test_selection.py

## Observability Impact

Add pack-stage logs and a deterministic `manifest.json` so figure/table assembly failures can be localized to one region or one source family.
