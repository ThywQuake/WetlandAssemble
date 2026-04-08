---
depends_on: [M002]
---

# M003: 热点成因解释与质量差异分析 — CONTEXT DRAFT

**Gathered:** 2026-04-08
**Status:** Draft for later discussion

> This is a draft, not a finalized milestone context. It captures seed material from the M002 discussion so a later focused M003 discussion can start from here instead of from scratch.

## Seed Description

M003 is intended to turn M002's unified hotspot ledger into a real explanation framework for dataset-quality differences. The milestone is not only about drawing more overlays. Its real job is to explain why disagreement hotspots appear, what mechanism each hotspot most likely represents, and what that means for judging the strengths and weaknesses of the wetland datasets.

The user has already locked several important directions:

- hotspot-cause explanation must be **quantitative-evidence-first**
- imagery remains supporting evidence rather than the mandatory proof leg
- external land-cover evidence is required, specifically **MODIS MCD12Q1 via GEE**
- Berkeley itself is already the operational CYGNSS-derived auxiliary water product
- the trend-explanation side should eventually integrate external driver evidence including **GRACE**, **MSWEP**, **ERA5**, **GLEAM**, and **fcti** from the user's HPC-side data root

## Why This Milestone Exists

M002 is expected to unify percentage / classification / trend outputs into one evidence contract and one shared hotspot ledger. That still does not answer the core thesis question of **why** hotspots exist. M003 should convert those hotspot objects into explanation packages that separate hypothesis, supporting evidence, counter-evidence, and the resulting dataset-quality judgment.

## Intended User-Visible Outcome

When M003 is complete, the user should be able to take a hotspot or hotspot family from the shared ledger and inspect a reviewable explanation package that answers:

- what kind of disagreement this hotspot represents
- which external quantitative evidence supports that interpretation
- which evidence weakens or complicates the interpretation
- what this implies about dataset quality, not just hotspot appearance

## Locked Decisions Already Made

- Quantitative auxiliary evidence is the mandatory explanation leg.
- MODIS `MCD12Q1` through GEE is the required land-cover / surface-context source.
- Imagery-heavy case studies are supporting evidence, not the first-class proof surface.
- M003 should consume M002's shared hotspot ledger instead of redefining hotspots from raw products.

## Likely Technical Surfaces

- `src/WA/comparison/hotspots.py` — existing hotspot object model and cluster extraction logic
- `src/WA/comparison/trend_agreement.py` — trend-side disagreement surfaces and summaries
- `src/WA/comparison/phase36.py` — classification-side entropy / majority / agreement outputs
- `src/WA/validation/gee_client.py` — GEE access wrapper
- existing MODIS and S2 validation flows under `src/WA/validation/`
- external/HPC-side driver datasets under `/lustre/home/2200013429/Wetland_LSTM/GIEMS_MC_LSTM/data/clean`

## Major Open Questions For Later Discussion

- What is the canonical mechanism taxonomy for hotspot causes?
  - sensor response differences?
  - canopy / forested wetland masking?
  - open-water vs wetland ontology mismatch?
  - hydrologic variability / climate-driver mismatch?
  - land-cover transition / mixed-surface ambiguity?
- What is the explanation artifact format?
  - per-hotspot cards?
  - per-hotspot-family summaries?
  - region-by-region explanation tables?
- Which hotspots get the deepest interpretation first?
  - highest score?
  - most representative by hydro-setting?
  - most thesis-important regions?
- How much of the explanation work should be automated versus analyst-curated?
- What exact role should supporting imagery still play once quantitative evidence is primary?

## Current Recommendation

When auto-mode reaches M003, pause and run a dedicated M003 discussion. Start from this draft, then lock:

1. the hotspot mechanism registry
2. the explanation evidence template
3. the priority ordering for hotspot families / regions
4. the exact output form for quality judgments
