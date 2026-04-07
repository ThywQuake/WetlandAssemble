# 2026-04-07-013 Phase4 Berkeley Mask Pre-Coverage Fallback

## Summary

- 修复了 Phase 4 year-split 运行在 `2017` 这类 **早于 Berkeley 标准化覆盖起点** 的年份上直接报错的问题。
- `build_or_load_phase4_berkeley_valid_mask(...)` 现在在请求时间窗与 Berkeley 文件 **没有年份重叠** 时，不再抛 `FileNotFoundError`，而是回退到 **最早可用** 的 Berkeley 标准化文件，并继续只取该文件的首个真实时间片来构造 valid mask。
- 这次修改只修复 Berkeley valid-mask 的 source-window 选择逻辑；不改变 `gwd30` year cache / merge 的主链语义。

## Why

HPC 报错是：

```text
FileNotFoundError: No standardized files for berkeley_rwawc overlap ('2017-01-01', '2017-12-31')
```

根因不是 Berkeley 数据缺失，而是当前实现把 Berkeley valid mask 当成了“必须与分析年份重叠”的时序数据来解析。实际上这一步只需要一个真实 Berkeley 空间 footprint，用来给后续区域计算提供有效域分母。

所以对于 `2017` 这样的 year-split 任务：

- `gwd30` 分析年份是 2017
- Berkeley 标准化覆盖从 `2018-08` 才开始
- 旧逻辑按 `2017` 去找 Berkeley 重叠文件，直接失败

## Key Changes

- `src/WA/comparison/phase4_regional.py`
  - `_resolve_phase4_berkeley_mask_source_time_range(...)` 现在先尝试按请求时间窗找重叠文件
  - 若无重叠，则 fallback 到最早可用 Berkeley 文件
  - 新增日志模式标记：`mode=overlap` / `mode=earliest-available`
  - fallback 时会显式记录 warning，说明请求年份无重叠、当前改用哪个 Berkeley 文件

- `tests/test_comparison/test_phase4_regional.py`
  - 保留已有的“有重叠窗口时只取首个真实 Berkeley 时间片”的回归测试
  - 新增“请求 `2017` 时回退到 `2018-08-01` 而不是报错”的回归测试

- `CHANGELOG.md`
  - 记录这次 pre-coverage fallback 修复

## Verification

- `ruff check src/WA/comparison/phase4_regional.py tests/test_comparison/test_phase4_regional.py`
- `python -m pytest tests/test_comparison/test_phase4_regional.py -q`

## HPC Retry

针对单年 `2017` 先直接重跑：

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region pan_trop_subtrop \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2017 \
  --end-year 2017 \
  --no-skip
```

如果你走新的 fanout 提交脚本，也可以继续提交：

```bash
bash scripts/submit_phase4_gwd30_regional_year_split.sh \
  --repo "$PWD" \
  --python-bin "$PWD/.venv/bin/python" \
  --region pan_trop_subtrop \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --cpus 1 \
  --time 480 \
  --partition C064M0256G \
  --no-skip
```

## Remaining Risk

- 这个 fallback 依然假设 Berkeley valid footprint 在时间上足够稳定，适合作为 Phase 4 区域分母的空间有效域。
- 如果后续发现必须按“最近可用年份”而不是“最早可用年份”取 footprint，再调整策略；当前目标是先消除 year-split pre-coverage 的硬失败。
