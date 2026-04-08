---
estimated_steps: 11
estimated_files: 6
skills_used: []
---

# T01: Freeze replayable repository evidence into the canonical inventory

## Description

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

## Inputs

- `.gsd/PROJECT.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/milestones/M001/M001-CONTEXT.md`
- `.gsd/milestones/M001/slices/S01/S01-RESEARCH.md`
- `CHANGELOG.md`
- `config/datasets.yaml`
- `.gitignore`

## Expected Output

- `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md`

## Verification

`test -s .gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
`rg -n "^## (Runtime Code Surface|Operational Script Surface|Verification Surface|Planning and History Surface|Dataset, TODO, and Config Surface|Git and Worktree State|Artifact Presence and Proof Boundaries|Command Appendix)$" .gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
`rg -n "python -m pytest --collect-only -q|git status --short --branch|results/|temp/" .gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
