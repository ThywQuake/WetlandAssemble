# 2026-04-07 M001 S02 Phase Matrix Reentry

## Summary / 摘要

- 本轮 S02 的 canonical artifact 是 `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`。
- 这份 matrix 已经同时完成 R002 与 R007：一方面用 D002 的四级状态（`validated` / `implemented-but-unverified` / `historical/stale path` / `unclear`）覆盖 major phases 和 module families，另一方面把每一行的 `Local evidence` 与 `HPC / external proof` 明确拆开。
- `.gsd/REQUIREMENTS.md` 现在把 R002 与 R007 都回指到这份 matrix 作为验证证据来源；后续不要再用零散 prose 代替它。
- 如果只是快速恢复上下文，先读这份 note，再跳到 matrix 的 `## Grading Contract`、`## Phase Matrix`、`## Module Matrix`、`## Requirement Coverage`、`## Open Proof Gaps`。

## Canonical Matrix / 规范入口

- 主入口：`.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- 快速恢复后建议直接跳转到：
  1. `## Grading Contract` — 先重新建立 grading vocabulary 与 proof-boundary 规则。
  2. `## Phase Matrix` — 看 major phase 的当前状态、证据和 HPC gap。
  3. `## Module Matrix` — 看具体 `src/WA/...` surface 现在算不算真正被证明。
  4. `## Requirement Coverage` + `## Open Proof Gaps` — 看 R002 / R007 已经如何落地，以及哪些 gap 仍然只能去 HPC 上补证。

## Phase 4 Split / Phase 4 现行与历史分流

- **当前推荐主链** 是 matrix 里的 `Phase 4 current Stage-1 / Stage-2 route`。
- **历史/不要误回去的路线** 是 `Phase 4 historical full-tropics reducer route`。
- 解释方式要固定：
  - **Stage 1** = 从 `standardized/_staging/gwd30_<year>/stage_shard_*.json` 恢复 staged tiles，构建 native pixel-statistics tiles。
  - **Stage 2** = `run_phase4_regional.py` 消费这些 Stage-1 tiles，在区域级应用 Berkeley-valid mask，并生成区域统计表。
- 读 matrix 时，不要把这两条路线合并理解：
  - current row = 继续执行时该跟的链路。
  - historical row = 已被后续 changelog / stash 明确降级的旧 full-tropics reducer 路线，保留它是为了防止 future work 被误导回 OOM 历史路径。

## Verification

本 slice 结束后，下面这些命令仍然是“最小必要”检查：

```bash
test -s .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n "^## (Grading Contract|Phase Matrix|Module Matrix|Requirement Coverage|Open Proof Gaps)$" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n "Phase 4 current Stage-1 / Stage-2 route|Phase 4 historical full-tropics reducer route|R002|R007" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
```

如果后续要进入真实 HPC proof，当前仍然重要的命令是：

```bash
python scripts/build_phase4_gwd30_pixel_stats.py --year 2020 --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --aggregation monthly --worker-count 1 --no-skip
bash scripts/submit_phase4_gwd30_pixel_stats.sh --aggregation monthly --worker-count 1 --cpus 1 --time 480 --partition C064M0256G --no-skip
python scripts/run_phase4_regional.py --dataset-id gwd30 --region amazon --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --start-year 2013 --end-year 2022 --no-skip
```

## Open HPC Gaps

以下 gap 仍然不是本地 matrix/测试能直接关掉的，必须当成 HPC-only / external proof：

1. **Phase 3.6 当前修正后的 global route**：需要在真实 staged GWD30 tiles 上重新做 fresh HPC rerun，确认 tile-reduce / source-dominant 修复后的产物稳定。
2. **Phase 3.7 presentation chain**：需要基于当前 Phase 3.6 outputs 重新生成 global disagreement / hotspot outputs，并和 S2 / GEE imagery 一起做端到端确认。
3. **Phase 4 current Stage 1 / Stage 2 chain**：本地代码和测试已经在，但真正的区域链路仍需在 HPC 上执行 Stage 1 + Stage 2，不能因为本地 test pass 就视为完成。
4. **GEE/auth surfaces**：`s2_reference` 与相关 imagery 流程的本地测试只证明控制流，不证明 live Earth Engine auth / collection 状态。

## Handoff / 交接给 S03 与 S05

- **S03**：先从这份 note 恢复，再进入 `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`，重点消费 `Phase 4` current-vs-historical split、`Requirement Coverage`、`Open Proof Gaps`。
- **S05**：这份 note 可以当 compact operator handoff，用来快速恢复“matrix 已经做到了什么”和“哪些 gap 仍然不该在本地假装关闭”。
- 如果后续时间紧，不要重演 S01/S02 的综合判断；先读本 note，再 drill down 到 canonical matrix 即可。
