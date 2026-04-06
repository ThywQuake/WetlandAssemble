# Phase 3.6.1 GWD30 Stage-to-Cache Conclusion

**Date:** 2026-04-02
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 当前排查结论已收敛到 `stage -> cache` 路径：GWD30 的异常主导类结果不是 raw tiles 本身直接导致，而是在 Phase 3.6 从 staged tiles 生成 cache 的过程中引入。

## Current Conclusion

- 已排除纯粹的 Phase 3.7 绘图 cache 问题
- 已将关注点收缩到 Phase 3.6 GWD30 的 staged tile 到 cache 写出路径
- 下一步应重点检查：
  - staged tile 恢复与命中范围
  - reduced tile 变换后在 stripe 中的累计方式
  - `weighted_sum / coverage_sum` 的 annual unified fraction 重建
  - `01_gwd30_valid_mask.nc` / `01_gwd30_dominant_class.nc` 的写出逻辑

## Next Step

从 `src/WA/comparison/phase36.py` 的 `_write_global_gwd30_phase36_caches(...)` 开始，逐段核查 staged tile 到 final cache 的空间累计与覆盖逻辑，并修正后补测试。
