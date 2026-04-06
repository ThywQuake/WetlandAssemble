# M001 S02 T04 — validation / analysis / visualization matrix closeout

- Extended `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` with the remaining higher-level module rows:
  - `validation/GEE references`
  - `Phase 2.6 regional metrics`
  - `Phase 3.6 global disagreement`
  - `Phase 3.7 hotspot/plotting`
  - `Phase 4 regional/trends`
  - `visualization surfaces`
- Added concrete `src/WA/...` and test anchors for each row, including local verification surfaces for S2 reference downloads, Phase 2.6 metrics, Phase 3.6 disagreement analysis, Phase 3.7 hotspot plotting, Phase 4 regional/trend helpers, and cross-phase figure writers.
- Added `## Requirement Coverage` to map:
  - `R002` → the now-complete grading contract + phase/module matrix
  - `R007` → the explicit split between `Local evidence` and `HPC / external proof`
- Added `## Open Proof Gaps` to make the remaining boundaries explicit:
  - fresh GEE-backed reference/quicklook runs still require live auth and collections
  - Phase 3.6 still needs a post-fix HPC rerun on real staged GWD30 tiles
  - Phase 3.7 hotspot/global outputs still depend on current Phase 3.6 artifacts and external imagery
  - Phase 4 Stage-1 / Stage-2 remains locally implemented but still needs real HPC confirmation
  - plotting tests prove renderers/layouts, not end-to-end scientific outputs from fresh real products
