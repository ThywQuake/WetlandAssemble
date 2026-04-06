# Phase 4.1 GWD30 全时段 Stage 优化计划

## 结论

重新核对 stash 与用户反馈后，之前“只有 2016 做过 stage”的判断是错的。真实问题是：

- HPC 上已经有 `standardized/_staging/gwd30_YYYY/tile_partials/tile_*.nc`
- 对应的 `stage_shard_00xx_of_0064.json` 也已经存在
- 但现有 Phase 4 regional / trend 路径根本没去用这套既有 staged cache

现有 Phase 4 regional 路径在跑 `2013` 时出现：

- `stage plan prepared ... pending ... reused 0 staged tile(s)`

这说明当前运行没有复用到 HPC 现有 canonical staged cache，而是在自己的 Phase4 临时目录里重走 `raw -> stage`。

## 已新增计划

- [docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md](/Users/mac/Code/WA/docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md)

## Phase 4.1 核心目标

1. 让 `phase4_regional.py` 和 `trends.py` 直接复用 HPC 已有 `standardized/_staging/gwd30_YYYY`。
2. 把 shard manifest restore 正式接入 Phase 4。
3. 去掉按 `region_id` / `bbox token` 再建一套 Phase4 专用 staged 根目录的逻辑。
4. 给 standardized staging root 补显式校验和更清楚的命中日志。

## 预期收益

- Phase 4 区域图不再按 region 重复 `raw -> stage`
- HPC 日志能明确显示 cache hit / manifest hit
- `gwd30` 从“已有 cache 但没接上”变成“直接复用既有 canonical cache”

## 下一步

直接进入 `Task 4.1.1 + Task 4.1.2`：

- loader standardized-staging restore
- Phase4 regional 接 standardized staging root
