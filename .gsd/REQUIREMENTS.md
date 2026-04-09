# Requirements

This file is the explicit capability and coverage contract for the project.

It now spans two layers:

1. **Validated audit/recovery capabilities from M001** — the project can recover route truth, proof boundaries, and re-entry order reliably.
2. **Active scientific execution capabilities for M002+** — the project must now turn the thesis logic chain into one coherent, reproducible evidence pipeline.

## Active

### R101 — Unified analysis contract across the three evidence lines
- Class: core-capability
- Status: active
- Description: The wetland-percentage, classification-accuracy, and trend-correctness lines must share one explicit contract for regions, grids, hotspot objects, summaries, and output semantics.
- Why it matters: Without a shared contract, the three lines drift into separate projects and cannot support one thesis narrative.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S02, M002/S03, M002/S04
- Validation: mapped
- Notes: This is the foundational anti-drift requirement for M002.

### R102 — Wetland-percentage line must produce comparable 0.25° surfaces, hotspot outputs, and regional summaries across the ten major regions
- Class: primary-user-loop
- Status: active
- Description: The wetland-percentage line must generate shared-grid wetland-fraction outputs, hotspot candidates, and regional summaries that can be compared directly across datasets and across all ten target regions.
- Why it matters: This is one of the thesis' three primary evidence legs and the base variable for later trend analysis.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S05, M002/S06
- Validation: mapped
- Notes: Berkeley/CYGNSS is treated as a direct auxiliary evidence surface here, not as a separate parallel product line.

### R103 — Classification-accuracy line must produce 500m unified-8-class disagreement products for G2017 / GLWD / GWD30
- Class: core-capability
- Status: active
- Description: `G2017`, `GLWD`, and `GWD30` must be comparable on a shared 8-class wetland vocabulary and `500m` grid, with disagreement products suitable for hotspot extraction and regional interpretation.
- Why it matters: This is the thesis' second primary evidence leg and the main route for classification-disagreement diagnosis.
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: M002/S04, M002/S06
- Validation: mapped
- Notes: Existing `phase36.py` outputs are a strong starting surface but not yet the whole paper-level contract.

### R104 — Trend-correctness line must produce comparable trend metrics, hotspot outputs, and regional summaries from wetland-fraction surfaces
- Class: core-capability
- Status: active
- Description: The trend line must derive comparable trend metrics from wetland-fraction surfaces, identify trend-disagreement hotspots, and emit regional summaries under the same paper-level contract as the other two lines.
- Why it matters: This is the thesis' third primary evidence leg and will later feed the external-driver explanation framework.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S04, M002/S06
- Validation: mapped
- Notes: The project already has trend-analysis modules, but they are not yet integrated into one paper-aligned output contract.

### R105 — Hotspots must be represented as one shared analysis object across percentage / class / trend lines
- Class: integration
- Status: active
- Description: Hotspots from all three lines must be represented through one shared object model so they can be tracked, compared, and interpreted consistently.
- Why it matters: The thesis depends on moving from “three separate hotspot lists” to one coherent hotspot evidence layer.
- Source: inferred
- Primary owning slice: M002/S04
- Supporting slices: M002/S01, M002/S02, M002/S03
- Validation: mapped
- Notes: This is the bridge from single-line analysis to cross-line synthesis.

### R106 — The first implementation milestone must close the full paper pipeline on a hydro-diverse canonical subset before scaling to all ten regions
- Class: operability
- Status: active
- Description: M002 must first prove the full pipeline on a canonical subset chosen for hydro-setting diversity, then scale the same contract to all ten regions.
- Why it matters: Subset-first proof reduces risk while still preserving the thesis-level ambition.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S05
- Validation: mapped
- Notes: The subset is for proof ordering, not for shrinking final scope.

### R107 — The full ten-region analysis must be reproducible through explicit HPC-safe cache, split, merge, manifest, and sync-back patterns rather than one-shot wide runs or container-only claims.
- Class: operability
- Status: active
- Description: The full ten-region analysis must be reproducible through explicit HPC-safe cache, split, merge, manifest, and sync-back patterns rather than one-shot wide runs or container-only claims.
- Why it matters: Wide geospatial jobs are too fragile to trust without a resumable execution model.
- Source: inferred
- Primary owning slice: M002/S05
- Supporting slices: M002/S06, M002/S07, M002/S08
- Validation: mapped
- Notes: Auto-mode may prepare, diagnose, and document reruns, but completion still requires authenticated HPC execution plus synced-back proof artifacts; OTP-gated remote legs remain explicit external boundaries.

### R108 — Hotspot-cause explanation must be driven primarily by quantitative auxiliary evidence
- Class: core-capability
- Status: active
- Description: Hotspot-cause analysis must be led by quantitative auxiliary evidence rather than relying on imagery-first case studies.
- Why it matters: The thesis needs explainable, defensible reasons for disagreement, not only compelling visuals.
- Source: user
- Primary owning slice: M003 (provisional)
- Supporting slices: none
- Validation: unmapped
- Notes: Imagery remains supporting evidence, not the mandatory proof leg.

### R109 — Hotspot-cause explanation must include external land-cover evidence via MODIS MCD12Q1 through GEE
- Class: integration
- Status: active
- Description: The explanation framework must include MODIS `MCD12Q1` land-cover context acquired through GEE.
- Why it matters: Land-surface context is required evidence for interpreting hotspot causes, especially around forested wetlands and land-cover transitions.
- Source: user
- Primary owning slice: M003 (provisional)
- Supporting slices: none
- Validation: unmapped
- Notes: MCD12Q1 is required evidence, not an optional embellishment.

### R110 — Each hotspot explanation must distinguish hypothesis, supporting evidence, counter-evidence, and quality implications
- Class: quality-attribute
- Status: active
- Description: Every hotspot interpretation package must separate the candidate mechanism, the evidence that supports it, the evidence that weakens it, and what the interpretation implies about dataset quality.
- Why it matters: This stops the explanation layer from collapsing into unstructured correlation stacking.
- Source: inferred
- Primary owning slice: M003 (provisional)
- Supporting slices: none
- Validation: unmapped
- Notes: The explanation output should be reviewable and reusable in writing, not just embedded in ad hoc notes.

### R111 — The fusion milestone must use a balanced multi-objective scorecard
- Class: differentiator
- Status: active
- Description: The fusion milestone must evaluate “better” as a balanced multi-objective problem spanning external consistency, disagreement reduction, and trend realism.
- Why it matters: Fusion quality cannot be reduced to one metric without distorting the thesis goal.
- Source: user
- Primary owning slice: M004 (provisional)
- Supporting slices: none
- Validation: unmapped
- Notes: This scorecard must be defined before claiming any fused product is superior.

### R112 — The first fused product must be fraction-first and benchmarked against explicit baselines
- Class: core-capability
- Status: active
- Description: The first fusion result must be a fraction-first product and must be benchmarked against explicit baseline methods rather than judged by inspection.
- Why it matters: A baseline-backed fraction-first target keeps fusion scoped, comparable, and scientifically interpretable.
- Source: user
- Primary owning slice: M004 (provisional)
- Supporting slices: none
- Validation: unmapped
- Notes: Fraction-first does not rule out later fused classification work; it only sets the first stable target.

### R113 — The project must emit paper-ready figure/table packs aligned to the thesis narrative
- Class: launchability
- Status: active
- Description: The project must produce figure, table, and summary packs that map cleanly onto the thesis narrative rather than only emitting intermediate caches and scripts.
- Why it matters: The engineering work is successful only if it directly supports paper writing and review.
- Source: inferred
- Primary owning slice: M002/S06
- Supporting slices: M002/S07, M002/S08, M003 (provisional), M004 (provisional)
- Validation: mapped
- Notes: Paper-ready packs can claim completion only from regenerated science artifacts plus synced-back readiness/ledger evidence; local smoke outputs or fixture-only packs are insufficient.

## Validated

### R001 — Canonical inventory of repository surfaces
- Class: core-capability
- Status: validated
- Description: The project has one canonical inventory of code surfaces, scripts, plans, stashes, tests, and proof boundaries.
- Why it matters: Re-entry no longer starts from blind exploration.
- Source: user
- Primary owning slice: M001/S01
- Supporting slices: M001/S05
- Validation: validated
- Notes: Validated by `S01-INVENTORY.md` + `S01-DRIFT-BOUNDARIES.md`.

### R002 — Evidence-graded status matrix across major phases and modules
- Class: core-capability
- Status: validated
- Description: Major phases and modules are classified with explicit proof grades such as validated, implemented-but-unverified, historical/stale path, or unclear.
- Why it matters: The project can now distinguish implementation existence from proof strength.
- Source: user
- Primary owning slice: M001/S02
- Supporting slices: M001/S01, M001/S03
- Validation: validated
- Notes: Validated by `S02-PHASE-MODULE-MATRIX.md`.

### R003 — Current recommended continuation route is explicit
- Class: operability
- Status: validated
- Description: The project identifies which workflow is currently recommended for continuation.
- Why it matters: Follow-on milestones can start from the right route instead of stale ones.
- Source: inferred
- Primary owning slice: M001/S03
- Supporting slices: M001/S02, M001/S04
- Validation: validated
- Notes: Validated by the S03 route audit.

### R004 — Stale or misleading routes are explicitly named
- Class: failure-visibility
- Status: validated
- Description: Old, duplicated, or misleading entrypoints are listed explicitly together with the risk of following them.
- Why it matters: This prevents the recovery surface from reintroducing stale execution paths.
- Source: user
- Primary owning slice: M001/S03
- Supporting slices: M001/S05
- Validation: validated
- Notes: Validated by the S03 route audit.

### R005 — Open risks and HPC-only proof gaps are explicit
- Class: failure-visibility
- Status: validated
- Description: The project records unresolved proof gaps and places where claims depend on remote state.
- Why it matters: Later milestones inherit uncertainty honestly instead of assuming closure.
- Source: research
- Primary owning slice: M001/S03
- Supporting slices: M001/S02, M001/S04
- Validation: validated
- Notes: Validated by the S03 risk register.

### R006 — Ordered next-step execution map exists
- Class: primary-user-loop
- Status: validated
- Description: The project ends the audit phase with an ordered route for what to do next.
- Why it matters: The audit becomes useful only if it leads into executable continuation.
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: M001/S02, M001/S03, M001/S05
- Validation: validated
- Notes: Validated by `S04-NEXT-STEP-EXECUTION-MAP.md`.

### R007 — Local proof is separated from HPC/external proof
- Class: integration
- Status: validated
- Description: The audit separates what is proven locally from what still requires real HPC or live-service verification.
- Why it matters: This protects the project from false confidence.
- Source: research
- Primary owning slice: M001/S02
- Supporting slices: M001/S03, M001/S04
- Validation: validated
- Notes: Validated by the S02 matrix and its proof-boundary fields.

### R008 — Compact re-entry artifacts exist for the primary operator
- Class: continuity
- Status: validated
- Description: The project now has compact artifacts that let the operator recover control quickly without replaying long traces.
- Why it matters: The repository is large and operationally complex.
- Source: user
- Primary owning slice: M001/S05
- Supporting slices: M001/S01, M001/S02, M001/S03, M001/S04
- Validation: validated
- Notes: Validated by the S05 operator recovery pack.

## Deferred

### R120 — Fused classification product beyond the fraction-first fused product
- Class: differentiator
- Status: deferred
- Description: A fused classification product may be useful later, but it is not the first stable fusion target.
- Why it matters: It may become valuable once the fraction-first scorecard and evidence chain are stable.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred to avoid overloading the first fusion milestone.

### R121 — Imagery-heavy hotspot case-study workflows as a first-class proof surface
- Class: admin/support
- Status: deferred
- Description: Rich imagery-led hotspot packages may be useful later, but they are not the mandatory explanation leg.
- Why it matters: They can improve communication, but they should not dominate the explanation framework.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Sentinel-2 and other imagery remain supporting evidence for now.

### R122 — Additional auxiliary drivers beyond the current core set
- Class: integration
- Status: deferred
- Description: Additional auxiliary drivers may be added later if the first explanation framework proves insufficient.
- Why it matters: The current driver set may not explain every hotspot class or trend regime.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: The current core set is Berkeley/CYGNSS, GRACE, MSWEP, ERA5, GLEAM, fcti, and MCD12Q1.

## Out of Scope

### R130 — Treat Berkeley/CYGNSS as a separate parallel evidence leg outside the Berkeley product already in use
- Class: anti-feature
- Status: out-of-scope
- Description: The project will not treat CYGNSS as a separate parallel product line when Berkeley already serves as the CYGNSS-derived auxiliary water product.
- Why it matters: This prevents duplicated scope and duplicated interpretation surfaces.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Berkeley is the direct operational entrypoint.

### R131 — Define fusion quality from a single metric only
- Class: anti-feature
- Status: out-of-scope
- Description: The project will not define a fused product as “better” from only one metric.
- Why it matters: A single-metric definition would distort the thesis objective.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Fusion is explicitly multi-objective.

### R132 — Let hotspot explanation collapse into qualitative image inspection without quantitative auxiliary evidence
- Class: anti-feature
- Status: out-of-scope
- Description: The project will not accept imagery-only hotspot interpretation as the primary explanation route.
- Why it matters: This would weaken the scientific argument and make explanations less reproducible.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Imagery is supporting evidence only.

### R133 — Use raw global 30m trend analysis as the default scientific path instead of normalized fraction surfaces
- Class: constraint
- Status: out-of-scope
- Description: The project will not default to raw global 30m trend analysis when the agreed trend line is built from normalized wetland-fraction surfaces.
- Why it matters: The raw-30m route is computationally fragile and mismatched to the thesis' comparable trend contract.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Fraction-first trend analysis is the stable thesis path.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R101 | core-capability | active | M002/S01 | M002/S02, M002/S03, M002/S04 | mapped |
| R102 | primary-user-loop | active | M002/S01 | M002/S05, M002/S06 | mapped |
| R103 | core-capability | active | M002/S03 | M002/S04, M002/S06 | mapped |
| R104 | core-capability | active | M002/S02 | M002/S04, M002/S06 | mapped |
| R105 | integration | active | M002/S04 | M002/S01, M002/S02, M002/S03 | mapped |
| R106 | operability | active | M002/S01 | M002/S05 | mapped |
| R107 | operability | active | M002/S05 | M002/S06, M002/S07, M002/S08 | mapped |
| R108 | core-capability | active | M003 (provisional) | none | unmapped |
| R109 | integration | active | M003 (provisional) | none | unmapped |
| R110 | quality-attribute | active | M003 (provisional) | none | unmapped |
| R111 | differentiator | active | M004 (provisional) | none | unmapped |
| R112 | core-capability | active | M004 (provisional) | none | unmapped |
| R113 | launchability | active | M002/S06 | M002/S07, M002/S08, M003 (provisional), M004 (provisional) | mapped |
| R001 | core-capability | validated | M001/S01 | M001/S05 | validated |
| R002 | core-capability | validated | M001/S02 | M001/S01, M001/S03 | validated |
| R003 | operability | validated | M001/S03 | M001/S02, M001/S04 | validated |
| R004 | failure-visibility | validated | M001/S03 | M001/S05 | validated |
| R005 | failure-visibility | validated | M001/S03 | M001/S02, M001/S04 | validated |
| R006 | primary-user-loop | validated | M001/S04 | M001/S02, M001/S03, M001/S05 | validated |
| R007 | integration | validated | M001/S02 | M001/S03, M001/S04 | validated |
| R008 | continuity | validated | M001/S05 | M001/S01, M001/S02, M001/S03, M001/S04 | validated |
| R120 | differentiator | deferred | none | none | unmapped |
| R121 | admin/support | deferred | none | none | unmapped |
| R122 | integration | deferred | none | none | unmapped |
| R130 | anti-feature | out-of-scope | none | none | n/a |
| R131 | anti-feature | out-of-scope | none | none | n/a |
| R132 | anti-feature | out-of-scope | none | none | n/a |
| R133 | constraint | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 13
- Mapped to slices: 13
- Validated: 8
- Unmapped active requirements: 0
