# 2026-04-07-010 Phase4 Berkeley Mask Single-File Window

## Summary

- 针对你提供的 Phase 4 `amazon` 长时间窗 (`2013-2022`) 运行在 `berkeley_valid_mask` 冷启动阶段再次 OOM 的日志，继续收窄 Berkeley mask 冷路径。
- 现在 cache miss 时不再把整个请求时间窗对应的 Berkeley 年文件全部拼起来再取一个时间片，而是先定位 **请求时间窗内第一个真实可用时间片**，只用这个时间片来生成空间 valid footprint。
- 这次修改只影响 Berkeley valid-mask 冷启动；不改 `gwd30` Stage 1 / Stage 2 主链。

## Why

你提供的日志表明进程在这里被杀：

- `Phase4 cache miss: berkeley_valid_mask`
- 还没有进入 `gwd30` Stage 2 tile 处理

前一轮修复已经把 mask 构建从多时相规约改成了单时间切片，但冷启动仍然可能先按请求时间窗（例如 `2013-2022`）打开多个 Berkeley 年文件。对 Amazon 这种较大 bbox，这一步仍然可能造成不必要的峰值内存。

这次修复把冷启动再往前收紧一层：

1. 先从 standardized Berkeley 文件列表中找出请求时间窗内第一个实际可用文件
2. 读取该文件的第一个真实时间戳（例如 `2018-08-01`）
3. 仅用这个单时间片构建 valid mask

## Key Changes

- `src/WA/comparison/phase4_regional.py`
  - 新增 `_resolve_phase4_berkeley_mask_source_time_range(...)`
  - `build_or_load_phase4_berkeley_valid_mask(...)` 在 cache miss 时先把 Berkeley source window 收窄到首个真实可用时间片，再调用 `_open_phase4_dataset(...)`
  - 新增日志：
    - `Phase4 Berkeley mask source window: requested=... selected=... file=...`

- `tests/test_comparison/test_phase4_regional.py`
  - 新增回归测试，确认长时间窗请求时只会把首个真实可用 Berkeley 时间片传入冷启动 open path，而不是整窗 `2013-2022`

- `CHANGELOG.md`
  - 记录这次 Berkeley mask single-file/single-timestamp 冷启动收窄修复

## Verification

- `ruff check src/WA/comparison/phase4_regional.py tests/test_comparison/test_phase4_regional.py`
- `python -m pytest tests/test_comparison/test_phase4_regional.py -q`
- `python -m pytest tests/`

## HPC Retry

先重跑你这条失败命令：

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2013 \
  --end-year 2022 \
  --no-skip
```

如果你想先做最窄确认，再扩大范围，建议先跑：

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2016 \
  --end-year 2016 \
  --no-skip
```

## Remaining Risk

- 这个修复假设 Berkeley valid spatial footprint 对 Phase 4 区域分母而言，用“首个真实可用时间片”已经足够稳定。
- 如果后续发现 Berkeley 空间覆盖在时间上变化明显，需要回到 **按文件流式 OR** 的实现，而不是重新回到整窗多文件 / 多时相一起拼接。
