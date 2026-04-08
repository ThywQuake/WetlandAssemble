# M001 / S02 — Research

**Date:** 2026-04-07

## Summary

S02 owns **R002** and **R007**. The slice is documentation-first: convert S01’s frozen inventory into one evidence-graded matrix that covers both major phases and module families, with every row carrying (a) a D002 grade, (b) concrete local evidence anchors, and (c) an explicit HPC/proof-gap note. Do **not** re-audit the repo from scratch. S01 already froze counts, drift rules, and proof boundaries; S02 should spend its effort on grading and synthesis.

The strongest evidence chain is docs-first. Use `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` for stable counts and representative anchors, `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` for weighting rules, and then fill matrix rows from phase stashes plus `CHANGELOG.md`. Earlier phases have stronger completion evidence than the late-phase routes: Phase 1 loader fixes, Phase 2 rough comparison/review baseline, and Phase 3 core fine-grained + S2 all have stash-backed verification, including sampled HPC proof. By contrast, Phase 1.5, Phase 1.6, Phase 2.5, Phase 3.5, Phase 3.6+, Phase 3.7, and the current Phase 4 route mostly have strong local verification but unresolved HPC freshness gaps. Phase 4 also needs an explicit split between the retained full-tropics reducer route and the newer Stage-1/Stage-2 regional chain so S03 does not inherit a flattened history.

## Recommendation

Create a single canonical file such as `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` with two tables:

1. **Phase Matrix** — rows for `Phase 1`, `1.1`, `1.5`, `1.6`, `2`, `2.5`, `2.6`, `3`, `3.5`, `3.6`, `3.6.1`, `3.7`, `4 current Stage-1/Stage-2 route`, and `4 historical full-tropics reducer route`.
2. **Module Matrix** — rows for `loaders/classification`, `standardized loader`, `standardization & GWD30 staging`, `rough comparison`, `fine-grained comparison`, `validation/GEE references`, `Phase 2.6 regional metrics`, `Phase 3.6 global disagreement`, `Phase 3.7 hotspot/plotting`, `Phase 4 regional/trends`, and `visualization surfaces`.

Each row should use D002’s exact grade vocabulary — `validated`, `implemented-but-unverified`, `historical/stale path`, `unclear` — and carry separate columns for `Local evidence`, `HPC / external proof`, and `Why this grade`. Following the `doc-coauthoring` skill’s reader-first rule, keep the matrix evidence-forward and easy to scan. Following the S01 decision boundary, do not collapse route judgment into prose or reopen raw exploration. Use an optional short stash note only after the canonical matrix exists.

## Implementation Landscape

### Key Files

- `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` — frozen fact base: file-family counts, representative code anchors, and replayable command appendix. Reuse these counts instead of recomputing ad hoc counts.
- `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` — weighting rules for current vs historical evidence and the authoritative local-vs-HPC proof-boundary language.
- `CHANGELOG.md` — highest-signal chronological source for late route pivots; the `2026-04-05` and `2026-04-06` Phase 4 entries are required evidence for the current/historical split.
- `docs/stashes/2026-03-19-002-fix-phase1-loader-hpc-verified.md` — strongest Phase 1 loader-fix validation anchor, including HPC probe confirmation.
- `docs/stashes/2026-03-22-001-phase2-closeout-rough-review-and-debug-summary.md` — strongest Phase 2 baseline anchor; proves rough comparison, review-manifest outputs, and HPC hardening.
- `docs/stashes/2026-03-22-005-phase3-implementation-summary.md` and `docs/stashes/2026-03-23-003-s2-download-fixes-and-hpc-success.md` — Phase 3 core implementation and sampled HPC proof for S2 downloads.
- `docs/stashes/2026-03-31-015-phase26-wrap-up.md` — Phase 2.6 closeout anchor with local + HPC workflow evidence.
- `docs/stashes/2026-03-31-022-phase36-gwd30-tile-reduce-handoff.md` and `docs/stashes/2026-04-01-011-phase361-gwd30-hotspot-trace-diagnostics.md` — Phase 3.6 / 3.6.1 proof surfaces; local verification is strong, HPC rerun gap is explicit.
- `docs/stashes/2026-04-01-002-phase37-global-500m-handoff.md` and `docs/stashes/2026-04-01-004-phase37-hotspots-implementation.md` — Phase 3.7 plotting / hotspot anchors.
- `docs/stashes/2026-04-05-004-phase4-regional-timeseries-and-figures.md`, `docs/stashes/2026-04-05-008-phase41-session-summary.md`, and `docs/stashes/2026-04-06-003/005/006/007/008-*.md` — the Phase 4 chain; together they show both the old full-tropics route and the newer Stage-1/Stage-2 route.
- `src/WA/standardized_loader.py`, `src/WA/standardize.py`, `src/WA/comparison/rough_binary.py`, `src/WA/comparison/fine_grained.py`, `src/WA/comparison/phase26.py`, `src/WA/comparison/phase36.py`, `src/WA/comparison/trends.py`, `src/WA/comparison/phase4_regional.py`, `src/WA/validation/s2_reference.py`, `src/WA/visualization/phase37.py`, `src/WA/visualization/phase4.py` — code anchors that back the matrix rows; execution should cite them but not modify them.
- `tests/test_standardized_loader.py`, `tests/test_standardize.py`, `tests/test_comparison/test_harmonize.py`, `tests/test_comparison/test_fine_grained.py`, `tests/test_comparison/test_phase4_regional.py`, `tests/test_comparison/test_trends.py`, `tests/test_phase3_6_analysis.py`, `tests/test_phase3_7_hotspots.py`, `tests/test_visualization/test_phase4.py` — verification anchors for module-family rows.
- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` — recommended new canonical deliverable for the slice.
- `.gsd/REQUIREMENTS.md` — update R002 and R007 only after the matrix and proof notes exist.
- `.gsd/DECISIONS.md` — touch only if execution needs to freeze a new matrix schema or evidence-grading pattern.

### Likely First-Pass Grades

These are the most defensible starting grades from the evidence already present:

- **Phase 1 loader fixes** — `validated`
- **Phase 1.1 standardized-source loader refactor** — `implemented-but-unverified`
- **Phase 1.5 chunked standardization / staging** — `implemented-but-unverified`
- **Phase 1.6 coarse-scale visualization** — `implemented-but-unverified`
- **Phase 2 rough comparison + review baseline** — `validated`
- **Phase 2.5 comparison panels** — `implemented-but-unverified`
- **Phase 2.6 regional metrics / imagery workflow** — `validated`
- **Phase 3 fine-grained + entropy + S2 downloads** — `validated`
- **Phase 3.5 classification panels** — `implemented-but-unverified`
- **Phase 3.6 global disagreement** — `implemented-but-unverified`
- **Phase 3.6.1 hotspot trace diagnostics** — `implemented-but-unverified`
- **Phase 3.7 global plots / hotspots** — `implemented-but-unverified`
- **Phase 4 full-tropics shard reducer route** — `historical/stale path`
- **Phase 4 current Stage-1 / Stage-2 regional route** — `implemented-but-unverified`

### Build Order

1. **Freeze the rubric first.** Start the matrix with a short grading-contract section that literally restates D002 and the local-vs-HPC split from R007/S01. This prevents row-by-row drift later.
2. **Populate the high-confidence early anchors next.** Fill Phase 1, Phase 2, Phase 3 core, and Phase 2.6 first because their stash summaries already contain strong verification language, including sampled HPC proof. These rows establish the tone for what counts as `validated`.
3. **Then populate the ambiguous late-phase rows.** Handle Phase 1.5, 1.6, 2.5, 3.5, 3.6, 3.6.1, 3.7, and Phase 4 after the rubric is stable. These rows need careful proof-gap wording more than new exploration.
4. **Split Phase 4 into separate historical/current rows before any summary prose.** Treat the `2026-04-05` full-tropics cache/reducer path and the `2026-04-06` Stage-1/Stage-2 regional path as separate rows. This is the most important downstream unblock for S03.
5. **Derive module-family rows last.** Reuse the already-populated phase evidence rather than researching modules independently. The module matrix should be a cross-cutting synthesis, not a second audit.
6. **Only after the matrix is complete, update requirement status and compact handoff notes.** The requirement validation step should cite the finished matrix file, not intermediate notes.

### Verification Approach

- Structural checks on the final matrix file:
  - contains a grading-contract section that names all four D002 grades;
  - contains separate `Phase Matrix` and `Module Matrix` sections;
  - every row has both `Local evidence` and `HPC / external proof` columns;
  - Phase 4 appears in at least two rows: current Stage-1/Stage-2 route and historical full-tropics reducer route.
- Evidence checks:
  - early validated rows cite the specific stash anchors above;
  - ambiguous rows cite proof gaps instead of silently upgrading to validated;
  - the document cross-links both `S01-INVENTORY.md` and `S01-DRIFT-BOUNDARIES.md`.
- Repository consistency checks:
  - rerun `python -m pytest --collect-only -q` if execution wants a low-cost confirmation that the verification surface still collects cleanly in the current worktree;
  - avoid re-running broad HPC claims locally; the slice should document those as proof gaps, not try to retire them.

## Constraints

- S02 owns R002 and R007. It must grade phases/modules and separate local proof from HPC proof, but it should not turn into the canonical continuation recommendation; S03 owns R003/R005 route judgment.
- Use the S01 frozen counts and proof-boundary wording as source of truth. Do not replace them with fresh ad hoc repo counts unless the slice explicitly needs a delta.
- The `doc-coauthoring` skill’s reader-testing bias applies here: the matrix should be scanner-friendly and evidence-forward, not a long narrative history.
- Per `.gsd/KNOWLEDGE.md`, when plans disagree with newer changelog/stash evidence, weight the newer changelog/stash material higher.
- Treat `results/`, `temp/`, `/lustre/...`, and the old `.claude` memory path as absent-local or external-proof surfaces unless direct evidence is present in the worktree.

## Common Pitfalls

- **Flattening Phase 4 into one `implemented` row** — this loses the exact historical/current split that S03 needs. Keep the old full-tropics reducer/cache route separate from the Stage-1/Stage-2 regional route.
- **Promoting local tests to remote proof** — many rows have strong `pytest` / `ruff` evidence but still lack fresh HPC reruns. Use `implemented-but-unverified` when the missing proof is external rather than silently upgrading to `validated`.
- **Treating old active plans as current state** — several older plans still say Phases 3/4/5 were not started. Use them as design history only when newer stash/changelog evidence contradicts them.
- **Re-auditing the repo instead of synthesizing** — S01 already froze counts, representative anchors, and the command appendix. S02 should spend its effort on evidence grading, not repeating enumeration.

## Open Risks

- Same-day Phase 4 notes already drift: `2026-04-06-003` still says Stage 2 is not implemented, while `2026-04-06-005/007/008` show the regional Stage-2 entrypoint became the active local route later that day. Execution needs careful chronology when filling those rows.
- Some module families span multiple phases — for example `trends.py` now contains both general trend logic and Phase 4 Stage-1 pixel-statistics logic. The matrix should grade the workflow surface, not pretend each file maps 1:1 to one phase.
- Early-phase validated rows rely on stash-recorded HPC outcomes rather than fresh reruns from this worktree. That is acceptable for S02 if the row makes the boundary explicit.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| xarray | `tondevrel/scientific-agent-skills@xarray` | available |
| SLURM / HPC batch workflows | `serendipityoneinc/srp-claude-code-marketplace@slurm` | available |
| Google Earth Engine | none directly relevant found via `npx skills find` | none found |
