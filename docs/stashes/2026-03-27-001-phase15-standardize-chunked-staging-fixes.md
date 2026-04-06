# Phase 1.5 标准化内存修复总结

**Date:** 2026-03-27  
**Branch:** `refactor/loader-reference-grid-alignment`  
**Status:** 已完成第一轮 Phase 1.5 内存/序列化修补

## 本次修改

- `src/WA/standardize.py`
  - 新增 **chunked staging + merge** 流程：先按 reference grid 空间分块输出临时 chunk `.nc`，再合并成最终年度/静态产物
  - 新增 dataset/variable/coord attrs 的递归 netCDF 序列化清洗，避免 `semantic_mapping` dict 写盘报错
  - 将连续数据重投影改为 **slice-wise**，支持 `TOPMODEL` 这类 `(config, forcing, time, lat, lon)` 多非空间维数据
  - `G2017` / `GLWD` / 连续数据集 / `GWD30` 全部接入 chunk 路径，避免直接构造整幅 500m 全球数组
- `src/WA/loaders/berkeley.py`
  - 在逐月文件读取后立刻 `apply_bbox()`，减少 chunk 模式下不必要的数据载入
- `tests/test_standardize.py`
  - 新增 attrs 清洗测试
  - 新增多非空间维重投影测试
  - 新增 chunk staging + merge 端到端测试

## 已验证

- `python -m py_compile src/WA/standardize.py src/WA/loaders/berkeley.py tests/test_standardize.py`
- `python -m pytest tests/test_standardize.py tests/test_loaders/test_berkeley.py -q` → `20 passed`
- `ruff check src/WA/standardize.py src/WA/loaders/berkeley.py tests/test_standardize.py` → passed

## 仍需在 HPC 复核

- `GWD30` chunk 大小 `64`、`Berkeley` chunk 大小 `128`、其余连续数据 `1024` 目前是经验值，需按实际节点内存复核
- chunk 合并现在依赖 `xr.open_mfdataset(...).to_netcdf(...)`；需在 HPC 上确认大规模 chunk 文件合并时间与稳定性
- 如合并阶段仍偏慢，可考虑后续改成更强的 append/region 写法

## 建议下一步

- 先在 HPC 上小范围重跑：`g2017`、`glwd_v2`、`berkeley_rwawc`、`topmodel`
- 若通过，再跑 `swamps` 与 `gwd30`
- 观察 `_staging/` 下 chunk 文件数、单文件大小、最终 merge 阶段耗时
