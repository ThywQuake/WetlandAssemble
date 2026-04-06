# 2026-04-07 M001 S04 Next-Step Execution Map Reentry

## Summary / 摘要

- 本轮 S04 的 canonical artifact 是 `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`。
- 这份 note 只是 compact re-entry breadcrumb：先把你带回 canonical S04 map，再提醒你当前最小 continuation ladder 是 **2016 -> amazon -> widen later**。
- 不要把这份 note 当成第二份 execution map；真正要复制命令、核对 proof targets、确认 avoid-list 时，先回到 `S04-NEXT-STEP-EXECUTION-MAP.md`。
- `R006` 现在应理解为“下一步怎么继续做”的文档化验证，而不是“fresh HPC rerun 已经完成”的证明。

## Canonical Map / 规范入口

- 主入口：`.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
- 快速恢复时优先重读：
  1. `## Canonical Read Order`
  2. `## Ordered Continuation Path`
  3. `## Proof Targets / Exit Criteria`
  4. `## Do Not Touch First`
  5. `## Requirement Coverage`
- 如果后续 stash、plan 或 changelog 片段和这里冲突，先回到 canonical S04 map，不要让本 note 演变成新的 source of truth。

## 当前最小执行阶梯 / Current Narrow-First Ladder

1. **先读，不先跑**：先读 S03 route truth，再读 S02 proof boundary，然后才进入 live scripts。
2. **Stage 1 先窄跑**：先用 `scripts/build_phase4_gwd30_pixel_stats.py` 跑 `--year 2016 --no-skip`。
3. **Stage 2 再窄跑**：再用 `scripts/run_phase4_regional.py` 跑 `--dataset-id gwd30 --region amazon --start-year 2016 --end-year 2016 --no-skip`。
4. **确认 proof targets 后再放宽**：只有当 Stage-1 manifest / log marker 与 Stage-2 regional outputs 都齐了，才考虑 widening year range 或 wrapper。
5. **放宽顺序固定**：先 widen 时间范围，再考虑更宽的 dataset / region / workflow surface；不要反过来。

## Avoid / 避免先碰的路线与标志

- 避免把 old full-tropics shard/reduce family 当成当前入口：
  - `scripts/submit_phase4_gwd30_tropical_shards.sh`
  - `scripts/run_phase4_gwd30_tropical_shard.py`
  - `scripts/reduce_phase4_gwd30_tropical_shards.py`
- 避免假设 repo 里已经有 broad runner `scripts/run_phase4_trend_analysis.py`；当前 worktree 没有这份脚本。
- 避免一上来就跑 broad defaults；尤其不要先用没有显式 year / region 收窄的默认调用。
- 避免从旧 stash 里抄 stale flags：`--berkeley-raw-path`、`--phase36-cache-dir`、`--gwd30-cache-dir`、`--gwd30-worker-count`。

## Proof Boundary Reminder / 证明边界提醒

- 当前 S04 map 做到的是把“先读什么、先跑什么、什么算成功、什么先别碰”收敛成一个 ordered continuation path。
- 当前并没有声称 fresh HPC rerun 已完成；S03 继承下来的 HPC-only proof gap 仍然存在。
- 如果下一步真的要执行，请直接回到 `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` 复制 `--no-skip` 命令和 artifact expectations，不要只靠这份摘要继续。

## Handoff / 交接

- 想快速恢复：先读本 note，再回到 canonical S04 map。
- 想真正继续执行：直接从 `S04-NEXT-STEP-EXECUTION-MAP.md` 的 `Ordered Continuation Path` 和 `Proof Targets / Exit Criteria` 开始。
- 后续 slice 若引用 S04，请优先引用 canonical map；这份 note 只负责 re-entry，不负责替代执行证据本体。
