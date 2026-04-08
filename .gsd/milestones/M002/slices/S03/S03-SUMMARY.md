---
id: S03
parent: M002
milestone: M002
provides:
  - Contract-stable classification surface, regional summary, and hotspot-manifest families under `results/phase4`.
  - A canonical Phase 4 classification runner (`scripts/run_phase4_classification_contract.py`) with a documented narrow-first HPC ladder.
  - Semantic classification reload helpers in `src/WA/visualization/phase4.py` so downstream slices can reopen artifacts by semantics rather than guessed filenames.
  - Related-test routing that treats the classification contract adapter and runner as part of the Phase 4 verification family.
requires:
  - slice: S01
    provides: The shared evidence contract semantics and stable relpath/metadata pattern that classification artifacts now extend.
  - slice: S02
    provides: The participant-set keying, semantic reload pattern, and Phase 4 runner/reload conventions that S03 mirrored for the classification line.
affects:
  - S04
  - S05
  - S06
key_files:
  - src/WA/comparison/evidence_contract.py
  - src/WA/comparison/classification_contract.py
  - scripts/run_phase4_classification_contract.py
  - src/WA/visualization/phase4.py
  - tests/test_comparison/test_evidence_contract.py
  - tests/test_comparison/test_classification_contract.py
  - tests/test_visualization/test_phase4.py
  - src/WA/test_selection.py
  - docs/testing/test-categories.md
  - CHANGELOG.md
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
  - docs/stashes/2026-04-08-024-m002-s03-slice-closeout.md
key_decisions:
  - D034 — keep classification-disagreement contract logic in a thin adapter/runner layer over `phase36.py` and `phase37_hotspots.py` rather than moving the science into those producer modules.
  - D035 — encode the classification participant set as `g2017+glwd_v2+gwd30` in the contract dataset slot so the classification line matches the shared participant-set naming pattern.
  - D036 — reserve `__` for the outer evidence-contract stem separator and reject it inside dataset/participant tokens before relpaths or metadata are emitted.
patterns_established:
  - Thin contract adapter layers should own relpaths, metadata, validation, and summary normalization while core science modules remain focused on computation.
  - Classification disagreement artifacts use one fixed participant-set key (`g2017+glwd_v2+gwd30`) in the contract dataset slot, with `__` still reserved for the outer filename grammar.
  - Classification hotspot rewrites must validate the full Phase 3.7 source trio (manifest JSON + hotspot CSV + region CSV) before writing region-scoped contract hotspot pairs.
  - Semantic reload helpers double as downstream consumer APIs and skip/resume validation gates.
observability_surfaces:
  - Stage-tagged runner logging for `phase36`, `phase37`, `classification_contract_write`, and `classification_reload`, including `region_id` and `participant_set_key`.
  - Explicit reload failures for missing paired artifacts, malformed `contract_metadata_json`, participant-set mismatches, region mismatches, and hotspot row-count mismatches.
  - Contract hotspot metadata that preserves quota, selected-count, shortfall, threshold, and source provenance for downstream debugging and S04 ledger work.
drill_down_paths:
  - .gsd/milestones/M002/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-08T14:43:25.320Z
blocker_discovered: false
---

# S03: Classification-disagreement backbone on the shared contract

**Closed the classification-disagreement line on the shared evidence contract with stable 500m surfaces, regional summaries, hotspot manifests, a canonical Phase 4 runner, and semantic reload helpers for the fixed g2017+glwd_v2+gwd30 trio.**

## What Happened

# S03: Classification-disagreement backbone on the shared contract

## Outcome

S03 closed the third backbone evidence line: classification disagreement. `phase36.py` and `phase37_hotspots.py` outputs can now be projected into the same shared evidence contract already used by the percentage and trend lines. For the canonical classification participant set `g2017+glwd_v2+gwd30`, Phase 4 now has stable relpaths and semantic reload for region-scoped surfaces, regional summaries, and hotspot manifests. Downstream slices no longer need to consume legacy global Phase 3.6 / 3.7 filenames directly or rewrite ad hoc manifest payloads themselves.

## What this slice delivered

### T01 — Evidence-contract families and stem protection

- Extended `src/WA/comparison/evidence_contract.py` with:
  - `classification_surface`
  - `classification_regional_summary`
  - `classification_hotspot_manifest`
- Locked the contract stem grammar so the dataset slot can hold the classification `participant_set_key` while `__` remains reserved for the outer `<dataset_or_key>__<region>__<suffix>` separator.
- Added focused coverage in `tests/test_comparison/test_evidence_contract.py` so classification relpaths, metadata payloads, and bad-token failures are pinned before any adapter logic is added.
- Preserved the existing percentage and trend artifact families without renaming their stems.

### T02 — Classification contract adapter layer

Although the stored T02 task summary was blank, the implemented code and passing tests clearly show the slice work landed.

- Added `src/WA/comparison/classification_contract.py` as the contract-facing adapter layer for the classification line.
- Kept the scientific logic in the existing producers:
  - Phase 3.6 still owns disagreement math.
  - Phase 3.7 still owns hotspot-selection rules.
- Added deterministic helpers for the fixed participant-set key `g2017+glwd_v2+gwd30` and stable relpaths under `results/phase4/`.
- Built region-scoped surface writers that subset the global Phase 3.6 outputs to evidence-contract bboxes and preserve the full diagnostic payload needed downstream:
  - `entropy`
  - `majority_class`
  - `agreement_count`
  - `joint_valid_mask`
  - all three unified dominant-class layers
  - all three source dominant-class layers
- Built regional summary normalization/validation that records:
  - area-weighted entropy statistics
  - agreement-count histograms
  - majority-class area shares
  - source artifact paths
  - contract metadata JSON
- Built Phase 3.7 hotspot rewrites that preserve region quota / selected-count / shortfall / threshold context, attach source paths, and emit region-scoped contract JSON/CSV pairs.
- Added focused failure handling so malformed inputs fail before leaving partial surface/summary or hotspot-pair artifacts behind.
- Added `tests/test_comparison/test_classification_contract.py` to lock the stable relpaths, metadata, source validation, bbox parsing, unknown-region behavior, and no-partial-write guarantees.

### T03 — Canonical runner and semantic reload helpers

- Added `scripts/run_phase4_classification_contract.py` as the thin orchestration entrypoint for the classification route.
- The runner intentionally composes existing producers and the contract adapter instead of absorbing scientific logic.
- Execution flow is now explicit and stage-tagged:
  - `phase36`
  - `phase37`
  - `classification_contract_write`
  - `classification_reload`
- `src/WA/visualization/phase4.py` now reloads classification summaries and hotspot tables by contract semantics instead of guessed filenames.
- Reload failures are explicit for:
  - missing paired surface/summary artifacts
  - malformed `contract_metadata_json`
  - participant-set mismatch
  - region mismatch
  - selected-count versus hotspot-row mismatch
- `src/WA/test_selection.py`, `docs/testing/test-categories.md`, and `CHANGELOG.md` now route the classification contract path through the Phase 4 related-test family.

## Patterns established

1. **Thin contract adapter over stable producers.** Contract writing owns relpaths, metadata, summary normalization, and semantic reload. Existing disagreement and hotspot-selection science remains in `phase36.py` / `phase37_hotspots.py`.
2. **Participant-set key in the dataset slot.** The fixed classification trio uses `g2017+glwd_v2+gwd30` in the contract dataset slot, while `__` remains reserved for the outer filename grammar.
3. **Validate the full Phase 3.7 source trio before rewriting hotspots.** The contract layer cross-checks the manifest JSON, hotspot CSV, and region-summary CSV together, rather than trusting any single source file.
4. **Semantic reload as both consumer API and skip gate.** Downstream readers and the runner’s skip logic validate real contract artifacts semantically instead of assuming file existence is enough.

## Downstream handoff

This slice provides S04 and later slices with:

- contract-stable classification surface/summary/hotspot artifact families
- one canonical classification runner for narrow-first proof and later scale-out
- semantic reload helpers in `WA.visualization.phase4`
- hotspot metadata that preserves quota, selected-count, shortfall, threshold, and source provenance
- related-test routing that already knows the classification contract path belongs to the Phase 4 family

## Verification

All slice-plan verification passed locally:

- `ruff check src/WA/comparison/evidence_contract.py tests/test_comparison/test_evidence_contract.py`
- `python -m pytest tests/test_comparison/test_evidence_contract.py -q` → `12 passed`
- `ruff check src/WA/comparison/classification_contract.py tests/test_comparison/test_classification_contract.py`
- `python -m pytest tests/test_comparison/test_classification_contract.py -q` → `8 passed`
- `ruff check scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py tests/test_visualization/test_phase4.py src/WA/test_selection.py docs/testing/test-categories.md CHANGELOG.md`
- `python scripts/run_phase4_classification_contract.py --help`
- `python -m pytest tests/test_visualization/test_phase4.py -q` → `18 passed`
- `python scripts/run_related_tests.py src/WA/comparison/classification_contract.py scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py`

Per the repo’s standing verification rules, the full suite was also rerun:

- `python -m pytest tests/` → `476 passed`

The only residual noise in the full-suite run is pre-existing warning output (NumPy binary-compat warning on import plus existing pandas/xarray deprecation warnings); none of those warnings blocked the slice.

## Operational Readiness (Q8)

### Health signal

- `run_phase4_classification_contract.py` exposes a narrow-first HPC ladder in `--help`.
- Successful orchestration logs stage-tagged progress for `phase36`, `phase37`, `classification_contract_write`, and `classification_reload` with `region_id` and `participant_set_key` context.
- Semantic reload helpers can reopen the classification summary and hotspot table by contract semantics, confirming that skip/resume paths have real artifacts behind them.

### Failure signal

- Missing source artifacts raise explicit `FileNotFoundError` with region/participant/source-path context.
- Malformed contract metadata or hotspot bbox payloads raise explicit `ValueError` instead of silent fallback.
- Participant-set or region mismatches fail fast during reload, preventing downstream code from consuming mixed or misrouted artifacts.
- Atomic writes prevent half-written summary or hotspot pairs from looking complete.

### Recovery procedure

1. Fix or regenerate the relevant Phase 3.6 / Phase 3.7 source artifacts.
2. Inspect the whole Phase 3.7 source trio (manifest JSON + hotspot CSV + region CSV) rather than only one file.
3. Rerun the narrow-first path with `--no-skip` on one region first:
   - `python scripts/run_phase4_classification_contract.py --region amazon ... --no-skip`
4. Only after the one-region proof passes, rerun the canonical subset.
5. If a region’s contract outputs were partially corrupted manually, rebuild them rather than trusting skip detection.

### Monitoring gaps

- Fresh HPC/runtime proof on real standardized data is still missing.
- No slice-level telemetry yet summarizes wall time, I/O cost, or hotspot shortfall rates across the canonical subset.
- Ten-region behavior is still a future-scale concern for S05.

## Open limitations

- The classification contract path is currently fixed to the canonical `g2017 / glwd_v2 / gwd30` trio; it is not yet a generalized arbitrary-participant-set surface.
- Local proof is synthetic and structural. It does not yet prove real-data wall-time, cache behavior, or resumability on HPC.
- S04 still needs to unify percentage, classification, and trend hotspot objects into one ledger and comparison surface.

## HPC commands to run next

```bash
python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 512 \
  --static-worker-count 1 \
  --gwd30-worker-count 4
```

```bash
python scripts/run_phase4_classification_contract.py \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --year 2016 \
  --no-skip
```

```bash
python scripts/run_phase4_classification_contract.py \
  --subset canonical \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --year 2016 \
  --no-skip
```


## Verification

Slice-plan verification passed: three focused Ruff gates, three focused pytest gates (`12 + 8 + 18` passing tests), `python scripts/run_phase4_classification_contract.py --help`, and `python scripts/run_related_tests.py ...` all succeeded. Repo-wide regression was rerun per project rules and passed with `python -m pytest tests/` (`476 passed`). Remaining output was limited to pre-existing warning noise, not failures.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T02’s stored task summary was blank, so this slice closeout reconstructed its delivered behavior from the implemented `classification_contract.py` surface, the passing focused tests, and the current runner/reload wiring. In addition to the exact slice-plan gates, `python -m pytest tests/` was rerun because the repo’s standing verification rules require a full-suite pass after code changes.

## Known Limitations

Fresh HPC/runtime proof is still missing for the new classification-contract route. The classification contract path is fixed to the canonical `g2017 / glwd_v2 / gwd30` trio rather than a generalized arbitrary-participant-set surface. Full-suite pytest still emits pre-existing warning noise (NumPy binary-compat plus existing pandas/xarray deprecations), but the suite passes.

## Follow-ups

S04 should consume these new classification contract outputs to build one unified hotspot ledger across percentage / classification / trend. Operationally, the next proof step is the narrow-first HPC ladder: rebuild Phase 3.6 if needed, run `scripts/run_phase4_classification_contract.py --region amazon --year 2016 --no-skip`, then run `--subset canonical` before any wider-scale S05 work.

## Files Created/Modified

- `src/WA/comparison/evidence_contract.py` — Added classification artifact families and protected the shared stem grammar for participant-set keys.
- `src/WA/comparison/classification_contract.py` — Implemented the region-scoped classification contract adapter, summary validation, hotspot rewrite logic, and atomic write helpers.
- `scripts/run_phase4_classification_contract.py` — Added the canonical thin orchestration CLI for Phase 3.6 + Phase 3.7 + classification contract writing and semantic reload validation.
- `src/WA/visualization/phase4.py` — Added semantic classification summary/hotspot reload helpers and explicit mismatch/malformed-artifact failures.
- `tests/test_comparison/test_evidence_contract.py` — Locked classification artifact semantics, relpaths, metadata, and bad-token failures.
- `tests/test_comparison/test_classification_contract.py` — Added focused synthetic coverage for classification surface/summary/hotspot writing and malformed-source failures.
- `tests/test_visualization/test_phase4.py` — Added classification reload and runner negative tests for the new semantic contract path.
- `src/WA/test_selection.py` — Mapped the classification adapter and runner into the Phase 4 related-test family.
- `docs/testing/test-categories.md` — Documented the Phase 4 test family to include classification contract verification and kept the markdown Ruff-safe.
- `CHANGELOG.md` — Recorded the user-facing classification contract runner and reload-helper additions.
- `.gsd/KNOWLEDGE.md` — Captured the Ruff-sensitive markdown wrapper rule and the Phase 3.7 source-trio validation gotcha for classification hotspot rewrites.
- `.gsd/PROJECT.md` — Refreshed project state so S03 is marked complete and S04 is the next integration bottleneck.
- `docs/stashes/2026-04-08-024-m002-s03-slice-closeout.md` — Added a compact recovery/hand-off note for the closed slice, including the next HPC commands.
