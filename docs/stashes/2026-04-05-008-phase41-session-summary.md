# Phase4.1 Session Summary

**Date:** 2026-04-05
**Branch:** refactor/loader-reference-grid-alignment
**Commit Range:** unknown
**Status:** Phase4.1 已切到 data-only，`gwd30` 现复用 standardized staging、先构建 full-tropics cache，再支持 manifest-list HPC 并行。

---

## Key Changes

| File | Change |
|------|--------|
| [src/WA/comparison/phase4_regional.py](/Users/mac/Code/WA/src/WA/comparison/phase4_regional.py) | 新增 Phase4 data-only 区域统计主链；`gwd30` 改为复用 `standardized/_staging/gwd30_<year>/stage_shard_*.json`；主缓存层级提升为 `full_tropics tile-month cache`；新增 manifest-list restore 和 staged-tile tropical cache helper |
| [scripts/run_phase4_regional.py](/Users/mac/Code/WA/scripts/run_phase4_regional.py) | 改为 data-only 入口；若请求 `gwd30`，先预构建/加载 `full_tropics tile cache`，再派生 region 表 |
| [src/WA/comparison/trends.py](/Users/mac/Code/WA/src/WA/comparison/trends.py) | `gwd30` trend load 改为从 standardized staging root restore staged tiles；不再走 ad hoc Phase4 cache root |
| [scripts/hpc_probe_trends.py](/Users/mac/Code/WA/scripts/hpc_probe_trends.py) | 改为使用 `--standardized-dir` 驱动 `gwd30` staged-tile trend probing |
| [scripts/build_phase4_gwd30_shard_lists.py](/Users/mac/Code/WA/scripts/build_phase4_gwd30_shard_lists.py) | 从 `stage_shard_*.json` 生成 `manifest_list_*.txt`，用于 HPC 并行任务分发 |
| [scripts/run_phase4_gwd30_tropical_shard.py](/Users/mac/Code/WA/scripts/run_phase4_gwd30_tropical_shard.py) | 单个 manifest-list 任务：恢复 staged tiles，生成一份 `full_tropics` partial CSV |
| [scripts/reduce_phase4_gwd30_tropical_shards.py](/Users/mac/Code/WA/scripts/reduce_phase4_gwd30_tropical_shards.py) | 合并 shard partial CSV，产出年度 `tile_monthly_<year>.csv` |
| [scripts/submit_phase4_gwd30_tropical_shards.sh](/Users/mac/Code/WA/scripts/submit_phase4_gwd30_tropical_shards.sh) | 新增 SLURM 提交脚本：manifest-list array task + dependent reduce job |
| [tests/test_comparison/test_phase4_regional.py](/Users/mac/Code/WA/tests/test_comparison/test_phase4_regional.py) | 补 standardized manifest restore、full-tropics cache、region-from-cache 聚合测试 |
| [tests/test_comparison/test_trends.py](/Users/mac/Code/WA/tests/test_comparison/test_trends.py) | 补 trend path 对 standardized staged tiles 的 targeted test |
| [tests/test_submit_phase4_gwd30_tropical_shards.py](/Users/mac/Code/WA/tests/test_submit_phase4_gwd30_tropical_shards.py) | 覆盖新 submit 脚本 dry-run 输出和作业脚本生成 |
| [CHANGELOG.md](/Users/mac/Code/WA/CHANGELOG.md) | 记录 Phase4 data-only、standardized staging reuse、full-tropics cache、manifest-list HPC sharding |
| [docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md](/Users/mac/Code/WA/docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md) | 更正为“复用已有 standardized staging root”，不再假设需要重做全时段 stage |
| [docs/stashes/2026-04-05-005-phase41-gwd30-full-period-stage-optimization-plan.md](/Users/mac/Code/WA/docs/stashes/2026-04-05-005-phase41-gwd30-full-period-stage-optimization-plan.md) | 记录上述计划修正 |
| [docs/stashes/2026-04-05-006-phase41-gwd30-full-tropics-tile-cache.md](/Users/mac/Code/WA/docs/stashes/2026-04-05-006-phase41-gwd30-full-tropics-tile-cache.md) | 记录 `region-first -> full_tropics cache` 的重构 |
| [docs/stashes/2026-04-05-007-phase41-gwd30-manifest-list-hpc-sharding.md](/Users/mac/Code/WA/docs/stashes/2026-04-05-007-phase41-gwd30-manifest-list-hpc-sharding.md) | 记录 manifest-list HPC 并行方案 |

## Verification

- pytest: `python -m pytest tests/test_comparison/test_phase4_regional.py tests/test_submit_phase4_gwd30_tropical_shards.py -q` -> `11 passed`
- pytest: `python -m pytest tests/test_comparison/test_phase4_regional.py tests/test_comparison/test_trends.py -q` -> `23 passed`
- ruff: targeted checks clean for `phase4_regional.py`、`trends.py`、new scripts、new tests
- compile: targeted `python -m compileall ...` passed
- shell: `bash -n scripts/submit_phase4_gwd30_tropical_shards.sh` passed
- HPC: 本次没有重新跑最新代码；用户先前提供的 HPC 日志显示当时运行的仍是旧路径，表现为 `reused 0 staged tile(s)` 并触发 `raw -> stage`

## Open Risks / TODOs

- `gwd30` 子区域提取当前基于 tile bbox 相交聚合，边界存在可接受但真实存在的近似误差
- `python -m pytest tests/` 未跑；用户明确要求不要跑全量测试
- 新的 manifest-list HPC 并行链尚未在真实 HPC 上完成端到端验证
- `trends.py` 的像素级 merge 路线仍保留；当前只把 Phase4 区域数据链从 merge 思路中剥离出来

## Next Steps

1. 在 HPC 上先运行 `bash scripts/submit_phase4_gwd30_tropical_shards.sh --years ... --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --phase36-cache-dir results/cache/phase3_6 --task-lists 16 --task-cpus 4 --reduce-cpus 4 --no-skip`
2. 确认 `results/phase4/cache/gwd30/full_tropics/tile_monthly_<year>.csv` 都已生成
3. 再运行 `python scripts/run_phase4_regional.py --dataset-id gwd30 --region <region_id> --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --phase36-cache-dir results/cache/phase3_6 --output-root results/phase4`
