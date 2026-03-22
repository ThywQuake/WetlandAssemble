# MODIS 融合窗口扩到前后两个月并收紧 QA — 摘要

**日期:** 2026-03-21  
**分支:** `feat/phase2-rough-binary-modis-truth`  
**状态:** MODIS 粗尺度参考影像改为“目标月份前后两个月融合 + 更严格 QA 去云”

## Architecture decisions

- 用户要求：
  - 融合窗口改为 **目标月份前后两个月**
  - QA 过滤更严格，尽量不保留任何云
- 因此本轮在已有“QA 去云 + 多时段融合”的基础上进一步收紧：
  - 融合窗口：
    - 从“目标月前后 8 天”升级为“目标月前后 2 个月”
    - 例如 `2019-07` 会变成 `2019-05-01` 到 `2019-10-01` 的融合窗口
  - QA：
    - `QA` MODLAND 必须为最高质量（`bits[0:1] == 0`）
    - `StateQA` cloud state 必须 clear（不再接受 mixed）
    - aerosol 只接受 low / climatology (`<= 1`)
    - cirrus 必须为 none (`== 0`)
    - 继续屏蔽 cloud shadow / internal cloud / snow / adjacent cloud / internal snow

## Modified files and key changes

- `src/WA/validation/modis_reference.py`
  - `MODIS_FUSION_PADDING_MONTHS = 2`
  - `resolve_modis_fusion_window()` 改为按月扩窗
  - `_apply_modis_cloud_mask()` 收紧 QA 阈值
- `tests/test_validation/test_modis_reference.py`
  - 融合窗口预期更新为跨 5 个月窗口
  - 增加 artifact 输出路径与窗口断言

## Verification status

- `uv run ruff check src/WA/validation/modis_reference.py tests/test_validation/test_modis_reference.py`: pass
- `uv run pytest tests/test_validation/test_modis_reference.py -q`: pass (`4 passed`)

## Open risks, TODOs, rollback notes

- 过滤更严格后，个别热带 AOI 可能出现：
  - 可用像元很少
  - 甚至 `empty_collection` 或近似空影像
- 如果后续发现“太干净导致信息太少”，可以回退其中一项，而不是整体回退：
  - 保持前后两个月窗口
  - 仅把 aerosol 或 cirrus 阈值稍微放松
