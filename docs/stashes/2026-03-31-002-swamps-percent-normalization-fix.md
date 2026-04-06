# SWAMPS Percent Normalization Fix

## Summary

- `SWAMPS` 原始 `fw` 数值是 `0-100` 百分比，不是 `0-1` 分数。
- `SwampsLoader` 现在在屏蔽 `-9999` 填充值之后，统一执行 `/ 100.0` 归一化。
- 同步更新了依赖原始 SWAMPS 测试数据语义的测试样例，避免继续把原始输入误写成 `0-1`。

## Files

- `src/WA/loaders/swamps.py`
- `tests/test_loaders/test_swamps.py`
- `tests/test_visualization/test_comparison_panel.py`

## Verification

- `python -m py_compile src/WA/loaders/swamps.py tests/test_loaders/test_swamps.py tests/test_visualization/test_comparison_panel.py`
- `ruff check src/WA/loaders/swamps.py tests/test_loaders/test_swamps.py tests/test_visualization/test_comparison_panel.py`
- `python -m pytest tests/test_loaders/test_swamps.py tests/test_visualization/test_comparison_panel.py -q`

## Notes

- 针对性回归已通过。
- 全量 `python -m pytest tests/` 在本次会话中启动后被用户新问题打断，没有拿到最终完整结束状态。
