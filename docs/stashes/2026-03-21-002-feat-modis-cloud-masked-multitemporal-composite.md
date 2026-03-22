# MODIS 去云与多时段融合复合影像 — 摘要

**日期:** 2026-03-21  
**分支:** `feat/phase2-rough-binary-modis-truth`  
**状态:** MODIS 粗尺度参考影像已从“单窗口直接 median”升级为“QA 去云 + 多时段融合复合”

## Architecture decisions

- 之前的 `MODIS` 参考影像直接对单个时间窗口的 `MOD09A1` RGB band 做 `median()`，没有显式 QA 去云，因此热带地区云污染明显。
- 本轮改为两层增强：
  1. **像元级 QA 去云**
     - 使用 `QA` 与 `StateQA` 做质量屏蔽
     - 屏蔽云、云影、雪冰、邻近云、内部云，以及过差的 aerosol / cirrus 条件
  2. **多时段融合**
     - 不再只用“包含目标时间的单个 8-day composite”
     - 改为“目标月份 ± 8 天 padding”的融合窗口
     - 对该窗口内多景经过 QA mask 后的影像做 `median()` 合成
- 这样生成的 quicklook / chip 更接近“人工判读参考影像”，而不是单景或单合成时段的偶然观测。

## Modified files and key changes

- `src/WA/validation/modis_reference.py`
  - 新增 `MODIS_QA_BANDS`
  - 新增 `MODIS_FUSION_PADDING_DAYS`
  - 新增 `resolve_modis_fusion_window()`
  - 新增 `_apply_modis_cloud_mask()`
  - `download_modis_reference()` 现在：
    - 读取 `QA` + `StateQA`
    - 先做去云 mask
    - 再做 multi-temporal median composite
- `tests/test_validation/test_modis_reference.py`
  - Fake GEE image / collection 补齐 QA 与 mask 链式调用
  - 新增 `resolve_modis_fusion_window()` 回归测试

## Behavioral impact

- 新生成的 MODIS 输出目录会反映**实际融合窗口**，不再只是单个 8-day bucket。
- 例如先前类似 `20190626_20190704` 的窗口，后续可能变为更长的融合窗口（如目标月前后各扩 8 天）。
- 这意味着即使旧图已缓存，新版本也会落到新的时间窗口目录，不会误复用旧的“未去云”产物。

## Verification status

- `uv run ruff check src/WA/validation/modis_reference.py tests/test_validation/test_modis_reference.py`: pass
- `uv run pytest tests/test_validation/test_modis_reference.py -q`: pass (`4 passed`)

## Open risks, TODOs, rollback notes

- 当前是基于 `MOD09A1` QA bit 的保守去云策略；如果后续发现 tropical 湿地区域仍残留薄云，可再：
  - 收紧 cirrus / aerosol 阈值
  - 或扩大融合窗口
- 当前仍使用同步下载；大 AOI 仍可能碰到 `download_limit_exceeded`。
- 若要做更强的一致性控制，下一步可以把：
  - fusion window
  - QA strategy
  - visualize min/max
 统一写入 artifact manifest 字段中。
