---
estimated_steps: 10
estimated_files: 5
skills_used:
  - doc-coauthoring
  - document-review
---

# T02: Publish the compact S04 re-entry breadcrumb and wire R006 validation back to the canonical map

Close S04 by keeping the execution map canonical while still leaving the operator a compact Chinese-friendly re-entry breadcrumb and the formal requirement/changelog links that point back to it.

## Steps

1. Finish the `Requirement Coverage` section in `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`, making `R006` explicit and keeping the inherited `R003`/`R005` route-truth and proof-gap boundaries visible without re-arguing S03.
2. Write `docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md` as a compact Chinese-friendly pointer note that tells operators to read the canonical S04 map first, restates the 2016/amazon narrow-first ladder in condensed form, and preserves `--no-skip` wording plus the routes/flags to avoid.
3. Update `CHANGELOG.md` and `.gsd/REQUIREMENTS.md` so later slices can recover the new continuation map quickly and `R006` validates directly against `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`.

## Must-Haves

- [ ] The stash note and changelog both point back to the canonical S04 map instead of becoming a second source of truth.
- [ ] `.gsd/REQUIREMENTS.md` validates `R006` against the finished S04 map and does not imply the fresh HPC rerun already happened.

## Done when

- The canonical S04 map contains requirement coverage, the compact Chinese-friendly stash note exists, `CHANGELOG.md` records the breadcrumb, and `.gsd/REQUIREMENTS.md` maps `R006` to the canonical S04 artifact.

## Inputs

- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
- `CHANGELOG.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`

## Expected Output

- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
- `docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md`
- `CHANGELOG.md`
- `.gsd/REQUIREMENTS.md`

## Verification

`rg -n '^## Requirement Coverage$|R006|R003|R005' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
`test -s docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md`
`rg -n 'S04-NEXT-STEP-EXECUTION-MAP.md|2016|amazon|当前|避免|--no-skip' docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md`
`rg -n 'R006' .gsd/REQUIREMENTS.md`
`rg -n 'S04-NEXT-STEP-EXECUTION-MAP.md|next-step execution map|docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md' CHANGELOG.md`
