# S01: Canonical Surface Inventory

**Goal:** Inventory every major project surface across the whole repository and establish the evidence sources later slices will rely on.
**Demo:** After this: After this: there is one evidence-backed inventory of code, scripts, tests, docs, stash history, results, temp surfaces, TODOs, and branch state, so re-entry no longer starts from blind exploration.

## Tasks
- [x] **T01: Created S01-INVENTORY.md with replayable surface counts, branch/worktree state, and explicit local proof boundaries.** — ## Description

Build the main inventory artifact that directly advances R001 and freezes the evidence base before any route-judgment work starts.

## Steps

1. Run the agreed filesystem, git, and `python -m pytest --collect-only -q` commands and capture the current counts, branch state, and local presence/absence facts that the research identified.
2. Summarize `src/WA`, `scripts/`, `tests/`, `docs/`, `config/datasets.yaml`, and `todos/` as inventory surfaces with representative anchor files and explicit tags such as `present-local`, `historical`, `superseded`, `absent-local`, and `external/HPC-only` where applicable.
3. Write `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` with one section per surface plus a replayable command appendix that later slices can cite instead of re-exploring.

## Must-Haves

- [ ] Cover every R001 surface named by the roadmap/research, including results/temp absence checks and branch/worktree state.
- [ ] Cite the exact commands used so S02/S03 can refresh evidence without redoing blind exploration.

## Done when

- `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` exists, is non-empty, and contains the planned surface sections plus the command appendix.
  - Estimate: 45m
  - Files: .gsd/milestones/M001/slices/S01/S01-INVENTORY.md, .gsd/milestones/M001/slices/S01/S01-RESEARCH.md, .gsd/PROJECT.md, .gsd/REQUIREMENTS.md, CHANGELOG.md, .gitignore
  - Verify: `test -s .gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
`rg -n "^## (Runtime Code Surface|Operational Script Surface|Verification Surface|Planning and History Surface|Dataset, TODO, and Config Surface|Git and Worktree State|Artifact Presence and Proof Boundaries|Command Appendix)$" .gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
`rg -n "python -m pytest --collect-only -q|git status --short --branch|results/|temp/" .gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
- [x] **T02: Added the drift-boundary appendix and Chinese-friendly re-entry note, and cross-linked them from the frozen S01 inventory.** — ## Description

Finish the slice by turning the raw inventory into an appendix that later slices can reason from and by leaving a compact operator-facing recovery note in `docs/stashes/`.

## Steps

1. Review the high-signal plans, changelog entries, and stash summaries already identified by research and group them into `current-signal`, `historical`, and `superseded` sets without yet deciding the final canonical route.
2. Write `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` so S02/S03 can see which evidence is current, which is stale, and which claims remain `external/HPC-only` or `absent-local` in this worktree.
3. Cross-link the appendix from `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` and write `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md` as a concise Chinese-friendly recovery note covering outputs, verification commands, and open risks.

## Must-Haves

- [ ] The appendix explicitly separates current-route signals from stale/superseded references and from proof-boundary gaps.
- [ ] The recovery note points future re-entry to the canonical inventory, the appendix, the replayable commands, and the unresolved local-vs-HPC caveats.

## Done when

- `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` and `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md` both exist, and the main inventory cross-links the appendix.
  - Estimate: 35m
  - Files: .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md, .gsd/milestones/M001/slices/S01/S01-INVENTORY.md, docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md, docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md, docs/stashes/2026-04-06-003-phase4-conversation-summary.md, .gitignore
  - Verify: `test -s .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md && test -s docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md`
`rg -n "^## (Current Signals|Historical / Superseded Signals|Proof Boundaries|Handoff to S02 and S03)$" .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`
`rg -n "S01-DRIFT-BOUNDARIES.md" .gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
`rg -n "S01-INVENTORY.md|S01-DRIFT-BOUNDARIES.md|Open Risks|Verification Snapshot" docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md`
