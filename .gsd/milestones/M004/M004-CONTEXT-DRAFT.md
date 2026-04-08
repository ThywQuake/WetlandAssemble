---
depends_on: [M003]
---

# M004: Fraction-First 融合与多目标验证 — CONTEXT DRAFT

**Gathered:** 2026-04-08
**Status:** Draft for later discussion

> This is a draft, not a finalized milestone context. It captures the fusion direction already agreed in the M002 discussion so a later focused M004 discussion can begin from this seed.

## Seed Description

M004 is intended to take the unified evidence backbone from M002 and the explanation framework from M003, then design and verify a **fraction-first fused product**. The user has explicitly rejected a single-metric notion of “better.” The milestone must therefore frame fusion as a **balanced multi-objective** problem.

## Locked Decisions Already Made

- the first fusion target is **fraction-first**, not a simultaneous full fused classification product
- fusion quality must be evaluated with a **balanced multi-objective scorecard**
- that scorecard must at least speak to:
  - external consistency
  - disagreement reduction / convergence
  - trend realism
- baselines must be explicit; the fused product cannot be justified by inspection alone

## Why This Milestone Exists

The earlier milestones are expected to establish:

- one shared analysis contract across percentage / classification / trend lines
- one shared hotspot ledger
- one explanation framework linking hotspots to external quantitative evidence and quality judgments

M004 exists to answer the final thesis question: whether a constructed fraction-first fused product can be shown to be better than the existing dataset options under a defensible evaluation protocol.

## Intended User-Visible Outcome

When M004 is complete, the user should be able to point to:

- a stable fraction-first fused product
- a set of explicit fusion baselines
- a scorecard comparing the fused product to those baselines and to key single-dataset references
- a written conclusion about whether the fused product is actually better, and in what sense

## Likely Technical Surfaces

- M002 paper-aligned fraction outputs and hotspot ledger
- M003 explanation outputs and quality-judgment layers
- existing vote / agreement / entropy primitives that may serve as baselines or baseline ingredients:
  - `src/WA/comparison/rough_binary.py`
  - `src/WA/comparison/phase36.py`
  - `src/WA/comparison/trend_agreement.py`

## Major Open Questions For Later Discussion

- What baseline set is mandatory?
  - best single dataset?
  - simple mean / median?
  - vote-based or reliability-weighted baseline?
- What exact scorecard fields define the balanced objective?
- How should scorecard dimensions be weighted or reported when they trade off against each other?
- What counts as a sufficient win for the fused product?
  - dominate all baselines?
  - win on most dimensions?
  - win specifically on the thesis' highest-priority dimensions?
- Should classification fusion remain explicitly deferred, or should M004 leave behind a concrete path for a later classification-fusion extension?

## Current Recommendation

When auto-mode reaches M004, pause and run a dedicated M004 discussion. Start from this draft, then lock:

1. the baseline roster
2. the scorecard dimensions and reporting style
3. the pass/fail logic for claiming “better”
4. the exact artifact form of the fused product and its comparison pack
