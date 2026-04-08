# S06: Paper-ready evidence pack and milestone integration proof

**Goal:** 把 S01-S05 已落地的十区 percentage / classification / trend / ledger 合同结果重开成论文可直接引用的 derived evidence pack，并让 pack 的完整性声明只能来自 readiness + unified ledger + strict integration proof，而不是本地 smoke artifacts 或手写路径。
**Demo:** After this: After this: 至少一套可直接支撑论文结构的 figure/table/summary pack 已形成，且三条主线在十区上的核心产物都经过重新集成验证。

## Tasks
- [x] **T01: Promoted public trend-agreement semantic reload helpers and added phase4 percentage/trend wrapper reload APIs for pack-safe reuse.** — The pack builder should reopen contract artifacts through public helpers, not through script-private code or filename guesses. This task removes the main accidental-complexity trap before any figure/table assembly starts.

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
  - Estimate: 2h
  - Files: src/WA/comparison/trend_contract.py, scripts/run_phase4_trend_contract.py, src/WA/comparison/percentage_backbone.py, src/WA/visualization/phase4.py, tests/test_comparison/test_trend_contract.py, tests/test_visualization/test_phase4.py
  - Verify: ruff check src/WA/comparison/trend_contract.py scripts/run_phase4_trend_contract.py src/WA/comparison/percentage_backbone.py src/WA/visualization/phase4.py tests/test_comparison/test_trend_contract.py tests/test_visualization/test_phase4.py
python scripts/run_phase4_trend_contract.py --help
python -m pytest tests/test_comparison/test_trend_contract.py tests/test_visualization/test_phase4.py -q
- [x] **T02: Added a contract-reload Phase 4 paper-pack builder and CLI with deterministic manifesting.** — This is the primary R113 delivery: turn contract-backed science artifacts into thesis-facing figures, joined evidence tables, narrative summaries, and a deterministic pack manifest without mutating the science contract tree.

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
  - Estimate: 3h
  - Files: src/WA/visualization/phase4_pack.py, scripts/run_phase4_evidence_pack.py, tests/test_visualization/test_phase4_pack.py, src/WA/test_selection.py, docs/testing/test-categories.md, CHANGELOG.md
  - Verify: ruff check src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py tests/test_visualization/test_phase4_pack.py src/WA/test_selection.py docs/testing/test-categories.md CHANGELOG.md
python scripts/run_phase4_evidence_pack.py --help
python -m pytest tests/test_visualization/test_phase4_pack.py tests/test_visualization/test_phase4.py -q
python scripts/run_related_tests.py src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py src/WA/test_selection.py
- [ ] **T03: Gate complete-pack claims behind strict readiness and ledger proof** — The slice is not done when files merely exist. This task makes the pack itself the milestone integration proof surface by requiring clean readiness plus unified-ledger reopen before a ten-region pack can claim completeness.

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
  - Estimate: 2h
  - Files: src/WA/visualization/phase4_pack.py, scripts/run_phase4_evidence_pack.py, tests/test_visualization/test_phase4_pack.py
  - Verify: ruff check src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py tests/test_visualization/test_phase4_pack.py
python scripts/run_phase4_evidence_pack.py --help
python -m pytest tests/test_visualization/test_phase4_pack.py tests/test_comparison/test_hotspot_ledger.py tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_classification_contract.py tests/test_comparison/test_trend_hotspots.py -q
python scripts/run_related_tests.py src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py
