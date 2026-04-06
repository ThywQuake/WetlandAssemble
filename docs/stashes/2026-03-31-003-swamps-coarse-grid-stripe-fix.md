# SWAMPS Coarse Grid Stripe Fix

## Symptom

- `04_clipped_surface.nc` 正常。
- 只有 `05_coarse_surface.nc` 出现明显经向空白条纹。

## Root Cause

- `area_weighted_mean_to_regular_grid()` 原先按源像元中心把数据直接分箱到规则 `0.25°` 目标网格。
- 对于 `SWAMPS` 这类原始列数少于目标列数的粗分辨率/不规则经纬坐标数据，这会留下没有任何源像元中心落入的目标列，表现为经向空白条纹。

## Fix

- 当源网格在任一轴上比目标网格更粗时，不再使用中心分箱的面积加权聚合。
- 改为先按坐标插值到规则目标网格，避免空列/空行。
- 保留原有的面积加权聚合路径给真正的细到粗降采样场景。
- `05_coarse_surface` cache 新增版本号；旧的无版本 coarse cache 会自动视为 stale 并重算。

## Files

- `src/WA/visualization/coarse_scale.py`
- `scripts/plot_tropical_wetland_025deg.py`
- `tests/test_visualization/test_coarse_scale.py`
- `tests/test_plot_tropical_wetland_025deg.py`

## Verification

- `python -m pytest tests/test_visualization/test_coarse_scale.py tests/test_plot_tropical_wetland_025deg.py -q`
- `python -m pytest tests/`

## Result

- 全量测试通过：`314 passed`
