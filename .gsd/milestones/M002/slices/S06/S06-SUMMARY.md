---
id: S06
parent: M002
milestone: M002
provides:
  - A public semantic reopen surface for percentage and trend-agreement artifacts that downstream pack code can reuse safely.
  - A derived Phase 4 paper pack that emits figures, joined evidence tables, unified hotspot tables, a narrative summary, and a deterministic manifest under a dedicated pack root.
  - A strict complete-pack claim surface that binds readiness plus unified-ledger proof to manifest creation and exit semantics.
  - An operator-facing HPC rerun ladder that produces the real ten-region inputs needed for milestone-level strict proof.
requires:
  - slice: S05
    provides: The ordered ten-region selector, contract-backed percentage/classification/trend producers, readiness diagnostics, and unified-ledger gate that the paper pack reopens and proves.
affects:
  - M002 milestone validation
  - M003 (provisional)
  - M004 (provisional)
key_files:
  - src/WA/comparison/trend_contract.py
  - src/WA/visualization/phase4.py
  - src/WA/visualization/phase4_pack.py
  - scripts/run_phase4_trend_contract.py
  - scripts/run_phase4_evidence_pack.py
  - tests/test_comparison/test_trend_contract.py
  - tests/test_visualization/test_phase4.py
  - tests/test_visualization/test_phase4_pack.py
  - src/WA/test_selection.py
  - docs/testing/test-categories.md
  - CHANGELOG.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
  - docs/stashes/2026-04-09-016-m002-s06-slice-closeout.md
key_decisions:
  - D049 — Keep the paper pack split into one wide joined regional evidence CSV plus one long-form unified hotspot CSV, duplicate exact source provenance into the joined table and manifest, and clear stale manifests before rebuild.
  - D050 — Always write deterministic proof JSON/Markdown artifacts under the pack root; only `--strict` turns incomplete proof into a non-zero exit, while non-strict runs remain inspectable without claiming completeness.
  - D051 — Keep trend-agreement pair validation and semantic reload in `src/WA/comparison/trend_contract.py` and keep `src/WA/visualization/phase4.py` wrappers thin so pack code never imports runner-private helpers or infers contract paths.
patterns_established:
  - Keep paper-facing outputs as a derived layer under a dedicated pack root; never mutate the science contract tree under `results/phase4`.
  - Make readiness plus unified-ledger reopen the gate for any complete-pack claim instead of inferring completeness from file existence alone.
  - Keep semantic reload validation in the comparison layer and expose thin visualization wrappers so pack consumers do not duplicate filename/path logic.
  - Duplicate exact source provenance into both the joined evidence table and the manifest so pack reruns stay replayable and inspectable.
observability_surfaces:
  - `results/figures/phase4_pack/complete_pack_proof.json` and `complete_pack_proof.md` record readiness verdicts, ledger provenance, manifest path, and output counts for every pack run.
  - `run_phase4_evidence_pack.py` logs `stage=pack-proof action=complete|incomplete` and aligns its exit status with `--strict` vs non-strict proof semantics.
  - A fresh manifest is itself part of the health signal: incomplete proof clears stale manifests so old success claims cannot survive a failed rerun.
  - Proof artifacts preserve per-region readiness and ledger details, including participant-set mismatches, so operators can debug from deterministic outputs instead of transient logs alone.
drill_down_paths:
  - .gsd/milestones/M002/slices/S06/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S06/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S06/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-08T22:15:52.837Z
blocker_discovered: false
---

# S06: Paper-ready evidence pack and milestone integration proof

**S06 promoted pack-safe percentage/trend-agreement reload APIs, added a derived Phase 4 paper-pack builder/CLI, and made `run_phase4_evidence_pack.py --strict` the single readiness+ledger-backed complete-pack claim surface.**

## What Happened

## Slice Outcome

S06 closed the paper-facing delivery layer for M002. It did **not** add another science producer chain or mutate `results/phase4`; instead, it turned the existing contract outputs into a replayable derived pack and bound complete-pack claims to readiness plus unified-ledger proof.

### What actually shipped

- **T01 — public reload helpers for pack-safe reopen**
  - Promoted trend-agreement output-path and semantic reload helpers into `src/WA/comparison/trend_contract.py`.
  - Rewired `scripts/run_phase4_trend_contract.py` to reuse the public helpers instead of runner-private path logic.
  - Added pack-facing percentage summary/surface and trend-agreement summary/surface wrappers in `src/WA/visualization/phase4.py` so downstream code can reopen artifacts semantically instead of guessing filenames.
- **T02 — derived paper-pack builder and CLI**
  - Added `src/WA/visualization/phase4_pack.py` and `scripts/run_phase4_evidence_pack.py`.
  - The pack reopens percentage/classification/trend/ledger artifacts through semantic helpers, writes percentage interannual + climatology figures, one joined regional evidence table, one unified hotspot table, one narrative summary, and one deterministic manifest under a pack root outside `results/phase4`.
  - Pack output relpaths are deterministic, stale manifests are cleared before rebuild, and malformed inputs fail closed instead of producing a misleading pack claim.
- **T03 — strict readiness/ledger proof and claim semantics**
  - Extended the pack layer so every run writes deterministic `complete_pack_proof.json` and `complete_pack_proof.md` artifacts.
  - Proof now records resolved regions, readiness verdicts, ledger provenance, participant-set alignment, manifest path, and output counts.
  - `--strict` is now the only surface that can claim a complete pack: incomplete readiness or ledger proof returns non-zero and leaves no fresh manifest claim; non-strict runs still write explicit incomplete-proof artifacts for diagnosis.

### What this means for downstream work

- Downstream consumers no longer need script-private trend-agreement helpers or ad hoc filename guesses; public comparison-layer reload helpers are now the stable reopen surface.
- Paper-facing outputs are now a separate derived layer under `results/figures/phase4_pack` rather than a mutation of the science contract tree under `results/phase4`.
- `python scripts/run_phase4_evidence_pack.py --subset ten --strict ...` is now the single complete-pack claim surface for real ten-region reruns.

## Operational Readiness (Q8)

- **Health signal:** strict pack runs exit `0`, write a fresh manifest plus `complete_pack_proof.json` / `complete_pack_proof.md`, readiness rows are all `ready`, and the proof reports `complete_pack_claim_allowed: true`.
- **Failure signal:** CLI logs include `stage=pack-proof action=incomplete`, the manifest is absent, proof JSON/Markdown list blocking reasons, and ledger participant-set or hotspot-family mismatches stay fail-closed.
- **Recovery procedure:** rerun the missing upstream producers with explicit `--no-skip`, rerun readiness, rerun the unified ledger, then rerun `run_phase4_evidence_pack.py --strict`; do not hand-edit pack outputs or try to preserve stale manifests.
- **Monitoring gaps:** there is still no dashboard or automatic alerting for pack completeness; operators must inspect CLI logs plus proof JSON/Markdown manually, and this worktree still does not contain real ten-region external-input outputs.

## Handoff to Milestone Validation

Local closeout proves the pack/proof surfaces on fixture-backed contract artifacts. The remaining boundary is external: materialize the ten-region science outputs on HPC, then run the strict pack ladder to produce a real milestone-level complete-pack claim before M002 validation and completion.

## Verification

Re-ran the full S06 verification surface and all checks passed locally: a superset `ruff check` across the comparison/visualization/pack/test/docs files; `python scripts/run_phase4_trend_contract.py --help`; `python scripts/run_phase4_evidence_pack.py --help`; `python -m pytest tests/test_comparison/test_trend_contract.py tests/test_visualization/test_phase4.py -q` (`22 passed in 5.61s`); `python -m pytest tests/test_visualization/test_phase4_pack.py tests/test_visualization/test_phase4.py -q` (`28 passed in 13.23s`); `python -m pytest tests/test_visualization/test_phase4_pack.py tests/test_comparison/test_hotspot_ledger.py tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_classification_contract.py tests/test_comparison/test_trend_hotspots.py -q` (`47 passed in 16.61s`); plus both required `python scripts/run_related_tests.py ...` selector runs. The observability/proof surface was also confirmed by the `tests/test_visualization/test_phase4_pack.py` coverage of complete proof writing, incomplete-proof artifacts, strict vs non-strict exit behavior, and ledger participant mismatch rejection.

## Requirements Advanced

- R102 — S06 turns percentage contract summaries/surfaces into paper-facing interannual and climatology figures plus joined regional evidence rows without ad hoc filename logic.
- R103 — S06 reuses contract-backed classification summaries and unified-ledger rows inside deterministic paper-pack tables and proof artifacts.
- R104 — S06 promotes public trend-agreement reopen helpers and includes trend evidence in both the joined regional table and strict complete-pack proof.
- R105 — S06 consumes the unified hotspot ledger as the single hotspot table source for the paper pack, reinforcing the shared analysis-object model downstream.
- R107 — S06 makes complete-pack claims depend on readiness plus ledger proof, preserving the HPC-safe producer -> readiness -> ledger -> pack sequence instead of one-shot wide claims.
- R113 — S06 implements the traceable paper-ready figure/table/summary pack plus deterministic manifest/proof surfaces that map directly onto the thesis narrative.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

The local closeout proves the paper-pack and strict-proof surfaces on fixture-backed contract artifacts, not on freshly materialized ten-region external-input outputs. Repository-wide full-suite status also remains bounded by the unrelated baseline failure `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case`, which this slice did not touch.

## Follow-ups

Sync to HPC via `rsync`, run the ten-region percentage/classification/trend/readiness/ledger ladder with explicit `--no-skip` on the upstream science reruns, then run `python scripts/run_phase4_evidence_pack.py --subset ten --strict ...` and use its proof artifacts as the milestone validation input.

## Files Created/Modified

- `src/WA/comparison/trend_contract.py` — Promoted public trend-agreement output-path and semantic reload helpers with pair-level validation and context-rich failure messages.
- `scripts/run_phase4_trend_contract.py` — Switched the runner to reuse public trend-agreement helpers instead of runner-private reload logic.
- `src/WA/visualization/phase4.py` — Added pack-facing wrappers for percentage summary/surface and trend-agreement summary/surface reloads.
- `src/WA/visualization/phase4_pack.py` — Added the derived Phase 4 paper-pack builder plus deterministic readiness/ledger-backed proof artifact generation.
- `scripts/run_phase4_evidence_pack.py` — Added the paper-pack CLI, pack-root separation, and `--strict` complete-pack claim semantics.
- `tests/test_comparison/test_trend_contract.py` — Added regression coverage for trend-agreement semantic reopen success and failure envelopes.
- `tests/test_visualization/test_phase4.py` — Added wrapper-level regression coverage for the new percentage and trend-agreement pack-facing reload surfaces.
- `tests/test_visualization/test_phase4_pack.py` — Added fixture-backed coverage for pack outputs, proof artifacts, strict/non-strict CLI behavior, and ledger participant mismatch rejection.
- `src/WA/test_selection.py` — Routed the new paper-pack files into the Phase 4 related-test family.
- `docs/testing/test-categories.md` — Documented the expanded Phase 4 verification surface, including the paper-pack tests.
- `CHANGELOG.md` — Recorded the user-facing paper-pack and strict-proof CLI surfaces.
- `.gsd/DECISIONS.md` — Recorded D051 and preserved the S06 pack/proof architecture decisions.
- `.gsd/KNOWLEDGE.md` — Added guidance to avoid script-private trend-agreement helpers when building downstream pack consumers.
- `.gsd/PROJECT.md` — Refreshed project state so S06 is complete in-code and the next route is the HPC proof ladder plus milestone validation.
- `docs/stashes/2026-04-09-016-m002-s06-slice-closeout.md` — Added a quick-reference slice closeout note with verification results, open boundaries, and exact HPC commands.
