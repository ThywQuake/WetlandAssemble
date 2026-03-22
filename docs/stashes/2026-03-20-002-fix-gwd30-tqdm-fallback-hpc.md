# GWD30 tqdm fallback 兼容修复 — 摘要

**日期:** 2026-03-20  
**分支:** `feat/phase2-rough-binary-modis-truth`  
**状态:** 已确认 `results/phase2` 中 `2019-07` 的 GWD30 未参与是由 `tqdm` fallback 不兼容手动进度条调用引起；代码已修复并补充回归测试

## Architecture decisions

- `GWD30` 的 rough 并行归并路径同时使用了两种进度条调用方式：
  - `tqdm(iterable=...)`：包裹 tile 迭代
  - `tqdm(total=...)`：手动 `update()` 的并行进度条
- 之前的 fallback 只兼容第一种形式；当 HPC 环境缺少 `tqdm` 或 `tqdm.auto` 导入失败时，会退回到一个只接受 `iterable` 的函数，导致并行路径在 `progress = tqdm(total=len(paths), ...)` 处报错。
- 本轮将 fallback 明确升级为同时兼容：
  - 直接返回 iterable
  - 返回可 `update()/close()` 的 no-op progress 对象
- 这样即使 HPC 环境没有 `tqdm`，GWD30 也不会因为“仅仅缺少进度条依赖”而中断实际计算流程。

## Findings from `results/phase2`

- `results/phase2/rough/*/201907/run_summary.json` 中，`gwd30` 普遍为 `failed`。
- 典型报错：
  - `TypeError: tqdm() missing 1 required positional argument: 'iterable'`
- `results/phase2/rough/*/200003/run_summary.json` 中，`gwd30` 多为 `skipped_time_window`，这是预期行为，因为 `config/datasets.yaml` 里 `gwd30.years` 只覆盖 `2013-2022`，不覆盖 `2000-03`。

## Modified files and key changes

- `src/WA/loaders/gwd30.py`
  - 新增 `_NoOpProgress`
  - 新增 `_noop_tqdm(iterable=None, ...)`
  - 当 `tqdm.auto` 不可用时，fallback 现在可兼容手动进度条更新
- `tests/test_loaders/test_gwd30.py`
  - 新增 `test_gwd30_noop_tqdm_supports_manual_progress_updates`
  - 覆盖 `tqdm(total=...)` fallback 兼容性

## Verification status

- `uv run ruff check src/WA/loaders/gwd30.py tests/test_loaders/test_gwd30.py`: pass
- `uv run pytest tests/test_loaders/test_gwd30.py -q -k 'parallel_reduce_path or noop_tqdm_supports_manual_progress_updates'`: pass (`2 passed`)

补充说明：
- `uv run pytest tests/test_loaders/test_gwd30.py -q` 在本地 Python 3.13 + `tqdm` 环境下出现 `resource_tracker` / `tqdm` 相关底层噪音，但最终测试结果显示 `8 passed`；本轮未扩大处理该环境层问题，因为它不影响此次 HPC 根因修复结论。

## Open risks, TODOs, rollback notes

- 本轮修复的是 **HPC 缺失 `tqdm` 时的 fallback 崩溃**；修复后仍需要在 HPC 上重跑 `2019-07` 窗口确认 `gwd30` 真正重新参与并写出：
  - `gwd30_load_trace.json`
  - `gwd30_selected_tiles.geojson`
- `2000-03` 窗口没有 `gwd30` 是预期，不属于 bug。
- 如果后续 HPC 环境里 `tqdm` 虽可导入但运行时仍异常，再考虑把 GWD30 进度条统一包进一个更“保守”的安全包装器中，彻底降级为无进度模式。
