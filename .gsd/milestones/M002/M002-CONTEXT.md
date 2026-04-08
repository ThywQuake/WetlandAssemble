---
depends_on: [M001]
---

# M002: 论文主线统一分析合同与核心证据主干

**Gathered:** 2026-04-08
**Status:** Ready for planning

## Project Description

本 milestone 的目标不是再单独推进某一个旧的 Phase，而是把论文主线明确收束成一套统一、可复现、可扩展的分析合同。当前论文主线包含三条核心证据线：

1. **湿地百分比**：把多套数据集统一到 `0-1` 湿地百分比和 `0.25°` 网格上，比较十个大区内的空间差异与热点。
2. **分类准确度 / 分类分歧**：把 `G2017 / GLWD / GWD30` 统一到 8 个主要湿地大类与 `500m` 网格上，用 entropy / majority / agreement 识别热点。
3. **时间趋势正确性**：基于统一 wetland-fraction surface 的趋势指标比较时间变化差异，并为后续外部驱动解释铺好输入合同。

M002 的任务是先把这三条线从“各自有代码、有局部产物”推进到“共享 region / grid / hotspot / summary / figure 语义”的同一套论文级证据主干，再在 canonical hydro-diverse subset 上先闭环，然后扩展到全部十个大区。

## Why This Milestone

M001 解决了“当前路线是什么、哪些证据可信、HPC proof gap 在哪里”的控制面问题，但没有解决论文主线的实现问题。仓库里虽然已经有 `rough_binary.py`、`hotspots.py`、`phase36.py`、`trends.py`、`trend_agreement.py`、`phase4_regional.py` 等关键模块，但这些模块还没有被绑定成一条统一的 thesis evidence contract。

如果现在直接跳到热点成因解释或融合方法，最大的风险是：

- 三条分析线各自输出不同对象，后续无法统一解释；
- 十区结果和 canonical case 结果没有同一个 schema；
- 后面的外部辅助证据、land-cover 解释、融合 scorecard 没有稳定输入；
- 工程产物和论文叙事仍然脱节，形成许多 cache / csv / figure，但不能自然支持章节写作。

所以 M002 要先解决“统一合同 + 主产物 + subset-first proof + 十区 scale-out”这层问题，然后 M003 才能做解释，M004 才能做融合。

## User-Visible Outcome

### When this milestone is complete, the user can:

- 在一组 **hydro-diverse canonical regions** 上，稳定地对三条主线同时产出可比较的 surfaces、hotspots、regional summaries、以及论文图表草稿。
- 用同一套合同把结果扩到 **十个大区**，并直接拿到可写入论文主线的 figures / tables / summary packs。

### Entry point / environment

- Entry point: Python scripts under `scripts/` plus reusable modules under `src/WA/comparison/` and `src/WA/visualization/`
- Environment: local orchestration + HPC batch execution + file-based result artifacts
- Live dependencies involved: standardized dataset files, HPC filesystem, canonical Phase 4 split/cache/merge path; GEE is not the primary proof leg for M002 but remains an existing supporting subsystem

## Completion Class

- Contract complete means: the three analysis lines share one explicit contract for region set, target grids, hotspot schema, summary schema, and paper-artifact naming/layout
- Integration complete means: percentage / class / trend outputs can be produced side-by-side for the same canonical subset and then expanded to ten regions without ad hoc rewiring
- Operational complete means: the ten-region output path is reproducible through HPC-safe split/cache/merge execution rather than fragile one-shot wide runs

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- one hydro-diverse canonical subset can produce **all three** primary evidence lines under one shared output contract;
- the same contract can be scaled to all ten regions without redefining hotspot or summary semantics;
- at least one paper-ready figure/table pack exists that shows the three-line outputs in a form directly usable by the thesis structure;
- the milestone's proof does not depend on hand-curated one-off runs that cannot be replayed from scripts and cached artifacts.

## Risks and Unknowns

- Existing comparison modules have **uneven proof levels** — some are well-tested locally, while wide HPC execution is still only partially proven.
- The current repository has **real analysis primitives but no single hotspot ledger** across the three lines.
- The current canonical Phase 4 route is known, but broad reruns still carry **HPC-only proof risk** unless subset-first proof and split/cache/merge discipline are preserved.
- A paper-aligned figure/table contract does not yet exist; without it, the project may continue generating engineering outputs that are awkward to write from.

## Existing Codebase / Prior Art

- `src/WA/comparison/rough_binary.py` — coarse wetland-fraction disagreement surfaces and pairwise metrics
- `src/WA/comparison/hotspots.py` — Shannon entropy hotspot extraction and representative-site logic
- `src/WA/comparison/phase36.py` — 500m unified-8-class disagreement products for `G2017 / GLWD / GWD30`
- `src/WA/comparison/trends.py` — trend metrics on wetland-fraction-like inputs
- `src/WA/comparison/trend_agreement.py` — cross-dataset trend consistency surfaces and regional summaries
- `src/WA/comparison/phase4_regional.py` — current canonical Stage-1 / Stage-2 regional execution path
- `src/WA/visualization/phase37.py` and `src/WA/visualization/phase4.py` — existing plotting surfaces that can be reused but need contract alignment
- `.gsd/milestones/M001/M001-SUMMARY.md` — current route truth, proof-boundary discipline, and narrow-first continuation logic

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- `R101` — unify the three evidence lines under one analysis contract
- `R102` — produce 0.25° wetland-percentage outputs across ten regions
- `R103` — produce 500m unified-8-class classification disagreement outputs
- `R104` — produce comparable trend-correctness outputs
- `R105` — represent hotspots as one shared analysis object
- `R106` — prove the pipeline on a hydro-diverse canonical subset before scaling out
- `R107` — keep ten-region execution reproducible and HPC-safe
- `R113` — emit paper-ready figure/table packs aligned to the thesis narrative

## Scope

### In Scope

- defining the shared analysis/output contract for percentage / class / trend lines
- selecting and operationalizing a hydro-diverse canonical subset for first proof
- closing all three lines on that canonical subset
- scaling the same contract to all ten target regions
- producing paper-ready evidence packs for the M002 output layer
- preserving HPC-safe cache / split / merge execution patterns where wide runs are required

### Out of Scope / Non-Goals

- full hotspot-cause interpretation with external quantitative drivers (`M003`)
- land-cover explanation with `MCD12Q1` (`M003`)
- final fraction-first fusion scorecard and fused-product validation (`M004`)
- imagery-heavy case-study proof as the mandatory M002 acceptance surface

## Technical Constraints

- Preserve the M001 route hierarchy and proof-boundary discipline; do not silently treat local artifacts as wide HPC proof.
- Do not collapse the three evidence lines into incompatible schemas that require manual downstream reconciliation.
- Keep the subset-first strategy as a proof-ordering device only; final M002 still needs ten-region scale-out.
- Continue using resumable/cacheable HPC-friendly execution rather than one-shot broad runs wherever the data volume demands it.

## Integration Points

- `Phase 4 Stage-1 / Stage-2 regional route` — percentage/trend-oriented regional outputs must respect the current canonical execution path
- `Phase 3.6 classification disagreement outputs` — classification line should reuse and formalize the existing 500m disagreement backbone
- `existing visualization modules` — current plotting helpers should be adapted into paper-artifact producers rather than left as disconnected figure scripts
- `HPC result roots and cached manifests` — must remain replayable and explicitly observable

## Open Questions

- Which exact hydro-diverse canonical regions best retire the contract risk first? — current direction is “mechanism coverage first,” not even regional spread.
- What is the minimal hotspot schema that all three lines can share without losing scientific specificity? — needs to be decided during M002 planning/execution.
- How far should M002 normalize figure/table semantics now versus leaving some narrative polish to M003? — current leaning is to make M002 paper-ready enough that later milestones consume, not reinvent, these artifacts.
