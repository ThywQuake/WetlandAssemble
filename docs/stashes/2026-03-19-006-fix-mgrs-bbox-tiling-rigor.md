# MGRS bbox tiling hardening — 摘要

**日期:** 2026-03-19
**分支:** `feat/phase2-rough-binary-modis-truth`
**状态:** `bbox_to_tiles()` 已改为严格候选枚举 + 判交，验证通过

## Architecture decisions

- `bbox_to_tiles()` 不再使用固定 `0.5°` 经/纬度采样。
- 新实现按 UTM zone 与 hemisphere 枚举 100 km MGRS 候选网格，并在投影后做 polygon-rectangle 判交。
- tile footprint 按 GWD30 的 shifted tile 语义处理：
  - 西/南仅偏移 `15 m`
  - 东/北允许 `109830 m` footprint 带来的重叠
- bbox 现在显式校验经纬度范围与上下界顺序；超出 MGRS 纬度有效范围的部分会被裁掉。

## Modified files and key changes

- `src/WA/utils/mgrs_tiling.py`
  - 重写 `bbox_to_tiles()`
  - 新增 bbox 校验、UTM zone helper、bbox 边界致密化、polygon/segment/rectangle 判交、UTM origin 到 tile code 的候选生成
  - 去掉原先基于 `np.arange(..., 0.5)` 的粗采样逻辑
- `tests/test_mgrs_tiling.py`
  - 更新 reference case，反映 shifted tile overlap 的真实结果
  - 新增 eastward overlap 回归测试，覆盖旧实现漏 tile 的情况
- `tests/test_loaders/test_gwd30.py`
  - 去掉“bbox 只会命中一个 tile”的隐含假设
  - 预过滤相关测试改为显式使用 `31NEA`

## Verification status

- `uv run pytest tests/test_mgrs_tiling.py tests/test_loaders/test_gwd30.py -q`: pass (`8 passed`)
- `uv run ruff check src/WA/utils/mgrs_tiling.py tests/test_mgrs_tiling.py tests/test_loaders/test_gwd30.py`: pass
- `uv run mypy src/WA/utils/mgrs_tiling.py tests/test_mgrs_tiling.py tests/test_loaders/test_gwd30.py`: pass

## Open risks, TODOs, rollback notes

- 当前实现针对本项目热带/亚热带使用场景是严谨的，但未专门处理 Norway/Svalbard 的特殊 UTM zone 规则。
- loader 端 tile-code prefilter 现在可能命中更多真实重叠 tile；如果后续发现某些年份文件命名并不完整，需要在 HPC 上复验实际 GWD30 文件覆盖情况。
- 如果要回滚，本次变更仅涉及 `mgrs_tiling` 与相关测试，可直接回退上述 3 个文件。
