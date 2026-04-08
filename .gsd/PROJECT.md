# Project

## What This Is

WA (Wetland Assemble) is a research-engineering workspace for comparing and ultimately fusing multiple wetland datasets around one thesis-sized logic chain. The project now centers on three coordinated evidence lines:

1. **湿地百分比** — normalize multiple datasets to `0-1` wetland fraction on a shared `0.25°` grid and compare their regional and pixel-scale behavior.
2. **分类准确度 / 分类分歧** — compare `G2017 / GLWD / GWD30` after remapping to a shared 8-class wetland vocabulary on a `500m` grid.
3. **时间趋势正确性** — compare trend behavior derived from wetland-fraction surfaces on a shared `0.25°` grid.

The thesis goal is not only to show where datasets differ, but to identify disagreement hotspots, explain why those hotspots appear, judge dataset quality more rigorously, and eventually build a better fraction-first fused product.

## Core Value

One reproducible, paper-aligned evidence backbone that can show **where wetland datasets disagree, why they disagree, and whether a fraction-first fused product is actually better** under a balanced multi-objective scorecard.

## Current State

M001 is complete and closed the audit / recovery-control problem. The repository now has a canonical control surface for route truth, proof boundaries, and re-entry order, but M001 explicitly did **not** close the scientific implementation gap.

What already exists in code:

- `src/WA/comparison/rough_binary.py` — coarse wetland-fraction disagreement surfaces and pairwise metrics
- `src/WA/comparison/hotspots.py` — entropy hotspot extraction and representative-site logic
- `src/WA/comparison/phase36.py` — 500m unified-8-class disagreement products for `G2017 / GLWD / GWD30`
- `src/WA/comparison/trends.py` and `src/WA/comparison/trend_agreement.py` — trend metrics and cross-dataset trend-agreement surfaces
- `src/WA/comparison/phase4_regional.py` — the current canonical Stage-1 / Stage-2 regional route for GWD30-oriented Phase 4 processing
- `src/WA/validation/gee_client.py`, `modis_reference.py`, and `s2_reference.py` — existing GEE-backed supporting evidence pipelines

What does **not** exist yet as a stable project-level contract:

- one shared schema tying percentage / classification / trend lines together
- one shared hotspot ledger across all three lines
- one paper-ready evidence pack aligned to the thesis structure
- one fraction-first fusion scorecard and baseline comparison framework

External evidence surfaces now explicitly in scope for later milestones:

- Berkeley itself as the CYGNSS-derived auxiliary water product
- GRACE / MSWEP / ERA5 / GLEAM / fcti under `/lustre/home/2200013429/Wetland_LSTM/GIEMS_MC_LSTM/data/clean`
- MODIS `MCD12Q1` through GEE for land-cover context extraction

These remain external/HPC-only or live-GEE proof surfaces unless revalidated in the correct runtime environment.

## Architecture / Key Patterns

- Python package under `src/WA`, mainly split across `loaders`, `comparison`, `validation`, and `visualization`
- Existing comparison modules already produce reusable disagreement, entropy, majority-vote, and trend-agreement primitives
- Validation modules already use a thin GEE wrapper and artifact-return-value pattern for reference imagery workflows
- HPC execution uses split/cache/merge patterns, explicit submit scripts, and rsync-based deployment rather than git-based remote execution
- M001 established the canonical recovery precedence:
  - S05 = first-stop recovery index
  - S03 = route truth
  - S02 = proof-boundary/status matrix
  - S04 = ordered execution truth
- Broad Phase 4 defaults remain dangerous; year/dataset/region filters must stay explicit until proof gaps are retired
- New milestones must treat outputs as **paper evidence objects**, not just intermediate engineering artifacts

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement states, and coverage mapping.

## Milestone Sequence

- [x] M001: Current-State Audit and Recovery Control Plane — re-established authoritative route truth, proof boundaries, and ordered re-entry without claiming fresh HPC execution proof
- [ ] M002: 论文主线统一分析合同与核心证据主干 — unify the three analysis lines under one evidence contract, close the full pipeline on a hydro-diverse canonical subset, then scale that contract to all ten regions
- [ ] M003: 热点成因解释与质量差异分析 — explain hotspot causes with quantitative auxiliary evidence plus land-cover context and turn those explanations into dataset-quality judgments
- [ ] M004: Fraction-First 融合与多目标验证 — build a balanced scorecard and validate a fraction-first fused product against explicit baselines
