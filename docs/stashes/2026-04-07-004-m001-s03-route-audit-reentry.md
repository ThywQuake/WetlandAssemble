# 2026-04-07 M001 S03 Route Audit Reentry

## Summary / 摘要

- 本轮 S03 的 canonical artifact 是 `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`。
- 这份 route audit / risk register 现在同时承担三件事：给出当前推荐 continuation path、列出 historical/stale 或 misleading routes、并把 R003 / R004 / R005 需要继承的 proof gaps 明写出来。
- 本 note 只是 compact pointer，不是第二份 route truth；恢复上下文时先看本 note，再回到 canonical S03 文档。
- 当前推荐主链仍然是 **Stage 1 pixel stats -> Stage 2 regional tables**，但真正的端到端 HPC proof 仍然没有在这轮文档工作里被关闭。

## Canonical Audit / 规范入口

- 主入口：`.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
- 快速恢复时，优先重读：
  1. `## Current Recommended Routes`
  2. `## Historical/Stale or Misleading Routes`
  3. `## Risk Register`
  4. `## Requirement Coverage`
- 如果后面有新的 stash、plan 或 changelog 片段跟这里冲突，先回到 canonical S03 文档核对，不要让这份 note 自己演变成新的 competing source of truth。

## 当前推荐路线 / Current Recommended Route

1. **Stage 1** — `scripts/build_phase4_gwd30_pixel_stats.py` 或 `scripts/submit_phase4_gwd30_pixel_stats.sh`
   - 从 `standardized/_staging/gwd30_<year>/stage_shard_*.json` 恢复 staged tiles。
   - 产出 `results/phase4/pixel_stats/gwd30/gwd30_<year>/<aggregation>/tile_manifest.json`。
2. **Stage 2** — `scripts/run_phase4_regional.py`
   - 消费 Stage-1 tile manifests。
   - 在区域级应用 Berkeley valid mask。
   - 生成 `results/phase4/tables/` 下的区域统计表。
3. **Supporting but non-primary** — `scripts/hpc_probe_trends.py`
   - 这条 lane 仍然有用，但当前定位是 diagnostic / spot check。
   - 它仍然走 `_staging`-restore 输入，不是当前推荐主链的 continuation path。

## 避免 / Routes to Avoid

- 不要把 old full-tropics shard/reduce family（如 `scripts/submit_phase4_gwd30_tropical_shards.sh`、`scripts/run_phase4_gwd30_tropical_shard.py`、`scripts/reduce_phase4_gwd30_tropical_shards.py`）当成当前 continuation path；它是 historical/stale lane，并且有明确的 HPC OOM 历史。
- 不要假设 repo 里已经有 broad batch runner `scripts/run_phase4_trend_analysis.py`；旧计划写过这个入口，但当前 worktree 里并没有这份脚本。
- 不要因为旧 plan 仍然标 `active`、旧脚本仍然在树里、或旧 test 仍然 passing，就把这些旧路线误判成 current route proof；当前 route judgment 以 `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` 加 source-code-backed 2026-04-06 evidence 为准。

## Open Proof Gaps

1. **Stage 1 / Stage 2 HPC-only proof gap**：本地代码、stash 和测试已经说明推荐链路是什么，但这并不等于已经在真实 HPC 上完成 fresh rerun。
2. **Input divergence**：regional lane 已经读取 Stage-1 pixel-stats manifests；trend probe 仍直接从 `standardized/_staging` restore。后续 trend work 需要决定是收敛还是继续保留双路线。
3. **Stage numbering drift**：不同 stash / changelog 对 “Stage 2” 的指代并不总一致；续做时必须写清是在说 regional tables，还是 future region-targeted trend expansion。
4. **2026-04-06 changelog self-conflict**：同一天的 changelog 还保留了新旧 route 语言，不能只靠 changelog 判断当前主链。
5. **Old active plans/tests still distort route weight**：旧路线仍有 plan front matter、脚本和测试留下来的“活着的样子”，但这些只能证明它们存在，不能证明它们仍是推荐 continuation。

## Recommended HPC Commands / 建议补证命令

如果下一步要在 HPC 上补 current route proof，优先按当前主链显式用 `--no-skip` 重跑：

```bash
python scripts/build_phase4_gwd30_pixel_stats.py \
  --year 2016 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --aggregation monthly \
  --worker-count 1 \
  --no-skip

bash scripts/submit_phase4_gwd30_pixel_stats.sh \
  --aggregation monthly \
  --worker-count 1 \
  --cpus 1 \
  --time 480 \
  --partition C064M0256G \
  --no-skip

python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2013 \
  --end-year 2022 \
  --no-skip
```

## Handoff / 交接

- 如果你只是要快速恢复 Phase 4 continuation path，先看这份 note，再回到 `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`。
- 如果你准备真正继续实现或补 HPC proof，就不要停在这份 note；直接 drill down 到 canonical S03 文档对应章节，并按上面的 `--no-skip` 命令做 fresh verification。
- 后续 slice 若需要引用 S03，请优先引用 canonical route-audit 文档；这份 note 只负责快速 re-entry，不负责替代证据本体。
