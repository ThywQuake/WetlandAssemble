# Phase 1 Loader 修复 HPC 验证完成 — 摘要

**日期:** 2026-03-19
**分支:** `feat/phase1-loader-foundation`
**状态:** 三个修复已通过 HPC 验证 (job.02 vs job.01)

## 修改文件

| 文件 | 变更 |
|------|------|
| `src/WA/loaders/swamps.py` | 添加 `-9999` → NaN 显式掩膜 |
| `src/WA/loaders/glwd.py` | 新增 `_parse_glwd_class_id()` 替代 `parse_first_integer` |
| `src/WA/loaders/g2017.py` | `reproject_match` 对齐到 wetland 参考网格 + `join="inner"` |
| `tests/test_loaders/test_swamps.py` | 新增 fill value 掩膜测试 |
| `tests/test_loaders/test_glwd.py` | 新增 class ID 解析测试，fixture 改为真实 GLWD 文件名 |
| `tests/test_loaders/test_g2017.py` | 新增坐标对齐测试 |

## HPC 验证结果 (diff job.01 → job.02)

- **SWAMPS:** `-9999` 值全部掩膜为 NaN（probe 区域无有效数据，non_null_count 8→0）
- **GLWD:** glwd_class 从 `[2,2,2,2]` → `[0,1,...,3,4]` 正确递增
- **G2017:** lat/lon shape 1798→898，wetland_nolake 从全 NaN → 有效值 0.1906
- **其他数据集:** 无实质变化，仅时间戳和微小耗时波动
- **GWD30:** tile discovery 日志从两次扫描减为一次，缓存正常工作

## 验证状态

- `pytest`: 28 passed
- `ruff`: all checks passed
- HPC probe: 三个修复全部确认

## 下一步

- Phase 1 验证完成，可进入 Phase 2（Rough Binary Comparison + MODIS Truth）
- probe 脚本改进（datetime 序列化等）优先级低，可后续处理
