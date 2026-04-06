# 2026-03-31 Phase 2.6 switch from entropy to std

## Summary

- Phase 2.6 不再把 `shannon_entropy` 作为主分歧指标。
- 现在改为直接基于连续湿地百分比计算 `std_wetland_fraction`。
- 同时移除了 `wetland_vote_fraction`，避免继续保留二值投票变量。
- 现在只保留：
  - `mean_wetland_fraction`
  - `std_wetland_fraction`
  - `participant_count`
- 这样避免先做 `0.5` 阈值二值化造成的信息损失。

## Files

- `src/WA/comparison/phase26.py`
- `scripts/run_phase2_6_analysis.py`
- `tests/test_phase2_6_analysis.py`
- `docs/phase2_6_metrics_explained.md`

## Verification

- `python -m pytest tests/test_phase2_6_analysis.py -q`
- `ruff check src/WA/comparison/phase26.py scripts/run_phase2_6_analysis.py tests/test_phase2_6_analysis.py`
- `python -m pytest tests/`
