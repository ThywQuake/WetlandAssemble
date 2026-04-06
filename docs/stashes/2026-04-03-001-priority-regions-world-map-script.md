# Priority Regions World Map Script

**Date:** 2026-04-03
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 已新增一个小脚本，用世界海岸线底图展示 `config/priority_regions.yaml` 中的所有 bbox，并已把标注逻辑改为统一从各 bbox 右上角引出，再用纵向堆叠偏移减少重叠。

## Key Changes

| File | Change |
|------|--------|
| `scripts/plot_priority_regions_world.py` | 新增 CLI：读取 `priority_regions.yaml`，绘制 world coastline map、bbox rectangle、中心点和 callout 文本；当前标注统一从 bbox 右上角引出，并按近邻冲突做简单向上堆叠 |
| `tests/test_plot_priority_regions_world.py` | 新增轻量测试，覆盖 region 读取排序、bbox 右上角锚点、近邻标签堆叠偏移和标签文本格式 |
| `CHANGELOG.md` | 记录新增 priority-regions 世界地图脚本 |

## Verification

- `ruff check scripts/plot_priority_regions_world.py tests/test_plot_priority_regions_world.py` → passed
- `python -m pytest tests/test_plot_priority_regions_world.py -q` → `4 passed`
- `python scripts/plot_priority_regions_world.py --output-path results/figures/priority_regions/priority_regions_world.png --dpi 200` → passed

## Output

- PNG: `results/figures/priority_regions/priority_regions_world.png`

## Next Step

如需在 HPC 或本地重画，只需运行：

```bash
python scripts/plot_priority_regions_world.py \
  --regions-file config/priority_regions.yaml \
  --output-path results/figures/priority_regions/priority_regions_world.png \
  --dpi 300
```
