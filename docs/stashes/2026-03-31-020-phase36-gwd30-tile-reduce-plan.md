# Phase 3.6 GWD30 tileNC 先缩维再聚合方案

**Date:** 2026-03-31
**Status:** 针对 Phase 3.6 在 `merge_staged_time_fraction_tiles()` 上触发全局 `reindex` OOM，改为对 staged `tile_*.nc` 先做 tile-local 时间压缩与类别映射，再进行全局条带聚合。

## 结论

- 不应再把 10259 个 GWD30 staged tile 直接 reindex 到全球 `(time, class, lat, lon)`。
- 正确方向是：
  1. 在每个 `tile_*.nc` 上先做 **时间维压缩**；
  2. 同时做 **15类→8类 unified 映射**；
  3. 只保留可跨 tile 相加的加和量；
  4. 最后在全局条带上做聚合并计算 dominant class / valid mask。

## 为什么不能直接在 tile 上先算 dominant

tile 之间理论上可能存在 coarse-grid 级别的边缘重叠。  
如果直接在每个 tile 上先算年均比例或 dominant class，再把这些 dominant 拼起来，不能保证与“先合并所有 tile 再求 dominant”完全等价。

因此 tile 级别缓存必须保留**可加和的统计量**：

- `annual_unified_weighted_sum(class_id, y, x)`
- `annual_coverage_sum(y, x)`

这样跨 tile 聚合时仍然可以精确地：

- 先求全局 `weighted_sum`
- 再除以全局 `coverage_sum`
- 再求 dominant class

## 推荐的新 GWD30 流程

### Step 1: Tile-local reduce

输入：现有 staged `tile_*.nc`

- `weighted(time, class_id, y, x)`
- `coverage(time, y, x)`

输出：新的 reduced tile cache

- `annual_unified_weighted_sum(unified_class_id, y, x)`  
  = 对 `time` 求和，且按 unified 8 类分组求和
- `annual_coverage_sum(y, x)`  
  = 对 `time` 求和

可选诊断变量：

- `valid_mask(y, x)` = `annual_coverage_sum > 0`

不建议把 tile-local `dominant_class` 作为最终聚合输入，只可作为调试产物。

### Step 2: Stripe merge

对每个全局纬向条带：

1. 找到与该条带相交的 reduced tile cache；
2. 读取 tile 的重叠子窗口；
3. 直接按全局行列切片把值累加到 stripe buffer；
4. stripe 完成后计算：
   - `annual_unified_fraction = weighted_sum / coverage_sum`
   - `gwd30_valid_mask`
   - `gwd30_dominant_class`

### Step 3: Phase 3.6 metrics

后续 Stage 只需要：

- `g2017` dominant
- `glwd_v2` dominant
- `gwd30` dominant
- `joint_valid_mask`

因此 GWD30 不必再落一个全球 `01_gwd30_unified_fraction.nc` 大文件，除非后续分析确实需要。

## 推荐的 Loader API 改造

新增类似接口：

- `transform_staged_time_fraction_tiles(...)`

设计目标：

1. 输入 `stage_shard_*.json` + `tile_*.nc`
2. 对每个 tile 执行自定义 reducer
3. 输出 deterministic 的 tile-level reduced cache
4. 支持断点续跑
5. 支持多进程/多节点共享文件系统

建议 reducer 约束：

- 必须是 top-level 可 pickle 的函数或 registry 中的命名 reducer
- 输入一个 staged tile dataset
- 输出与原 tile 相同局部网格的 reduced dataset
- 输出应只包含**不依赖跨 tile 信息**、且可安全复用的变量

## 并发与锁设计

### 并发模型

- 外层使用 **多进程**，不要依赖 Python 线程
- 原因：
  - netCDF/xarray/raster IO 混合 CPU 解码，线程收益不稳定
  - 现有 GWD30 stage 路径已经是 ProcessPool 模式
  - 共享文件系统下多进程更接近当前架构

### 锁策略

延续当前 staged tile 的文件锁模式：

- 每个 reduced tile 输出对应一个独立 `.lock`
- `O_CREAT | O_EXCL` 原子抢锁
- stale lock 可回收
- 写临时文件后 `os.replace()` 原子提交

### 输出命名

建议：

- `results/cache/phase3_6/gwd30_2016/tile_reduce/<transform_name>/tile_<stem>.nc`

并在 attrs 中记录：

- `transform_name`
- `transform_version`
- `source_stage_path`
- `source_bbox`
- `year`

## Phase 3.6 代码改造建议

1. `stage[00]` 只从 `g2017` 取 grid template，不加载 GWD30
2. `stage[01]`
   - `g2017` / `glwd_v2` 保持原逻辑
   - `gwd30` 改为：
     - tile reduce
     - stripe merge
     - 输出 `gwd30_valid_mask` + `gwd30_dominant_class`
3. `stage[02]` joint-valid 直接读取 `gwd30_valid_mask`
4. `stage[03]` dominant stage 直接读取 `gwd30_dominant_class`
5. `stage[04]` metrics 不变

## 预期收益

- 避免 `time x class x global_grid` 级别 reindex
- 把最重的 GWD30 维度从 `92 x 15` 压缩到 `8 + 1`
- 保持与当前 staged tile merge 数学等价
- 支持缓存复用、失败重试、多进程并行、原子写入
