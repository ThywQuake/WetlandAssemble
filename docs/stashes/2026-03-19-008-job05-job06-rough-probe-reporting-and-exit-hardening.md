# Job05/Job06 Rough Probe 报告与退出路径硬化 — 摘要

**日期:** 2026-03-19
**分支:** `feat/phase2-rough-binary-modis-truth`
**状态:** `job05/job06` 的报告与退出层问题已修复；`glwd_v2` 业务失败仍保留为显式 domain failure

## Architecture decisions

- `rough_probe` 里“是否参与 rough comparison”的判定顺序调整为：
  1. 先判断数据集是否有 rough binary comparison 资格；
  2. 再判断动态数据集的 target month 是否落在 temporal coverage 内。
  这样像 `berkeley_rwawc` 这类 out-of-scope 数据不会再被误标成 `skipped_time_window`。
- `loader_probe.make_json_safe()` 现在会把 `NaN` / `Inf` / numpy 非有限浮点统一转换为 `None`，避免生成语义不稳定或无效的 JSON。
- `rough_probe.main()` 的 `--json-out` 路径现在会：
  - 自动创建父目录；
  - 使用 `allow_nan=False` 写出严格 JSON；
  - 在写出失败时打印明确错误并返回非零退出码。
- `rough_probe` 的退出码语义收紧：任何 `status.startswith("failed")` 的数据集结果都会让 CLI 返回非零退出码，而不再只匹配裸 `failed`。
- `scripts/hpc_probe_rough_binary.py` 最外层 wrapper 不再把进程结束交给外部环境的 `sys.excepthook`；现在会自己归一化 `SystemExit` / 其他异常，再通过 `os._exit()` 结束进程，以绕开 HPC 环境里坏掉的异常钩子噪音。
- `failed_empty_harmonized_surface` 被明确视为**已处理的领域失败**，不是未捕获崩溃：
  - 这类结果保留 `error` 文本；
  - 但不再保存或渲染 traceback。
- 只有真正未预期的失败（`failed` / `failed_prepare`）才会在报告中打印 `traceback:` 段。

## Modified files and key changes

- `src/WA/rough_probe.py`
  - 修正 `skipped_not_eligible` 与 `skipped_time_window` 的判定顺序
  - 加强 `--json-out` 的写出与错误处理
  - 退出码判断改为覆盖所有 `failed_*`
  - `EmptyBinarySurfaceError` 不再保留 traceback
  - 报告渲染只为 `failed` / `failed_prepare` 打印 traceback
- `src/WA/loader_probe.py`
  - `make_json_safe()` 新增对非有限浮点值的清洗
- `scripts/hpc_probe_rough_binary.py`
  - 新增 `_coerce_exit_code()` 与 `_main()`
  - `__main__` 使用 `os._exit()` 直接退出，绕开环境 `sys.excepthook`
- `tests/test_loader_probe.py`
  - 新增 `make_json_safe()` 对 `NaN/Inf` 的回归测试
- `tests/test_rough_probe.py`
  - 新增 `berkeley_rwawc` 保持 `skipped_not_eligible` 的回归测试
  - 新增 `failed_empty_harmonized_surface` 不保留 traceback 的回归测试
  - 新增报告不渲染 expected domain failure traceback 的回归测试
- `tests/test_hpc_probe_rough_binary_script.py`
  - 新增 wrapper 对 `SystemExit` / 未预期异常的退出码回归测试

## job05 findings

来自 `temp/job05/job.10173298.out` 与 `temp/job05/job.10173298.err`：

- 主 rough probe 逻辑已经完整跑到 `overall_status: completed_with_failures`。
- `berkeley_rwawc` 被错误标成了 `skipped_time_window`，这暴露了 not-eligible 与 time-window 判定顺序的回归。
- stdout 中 metrics 区块仍包含大量 `NaN` 字样，这会污染 JSON-safe 导出语义。
- stderr 中持续出现 `Error in sys.excepthook:`，说明 HPC 外层环境的异常展示钩子不可靠。

## job06 findings

来自 `temp/job06/job.10173357.out` 与 `temp/job06/job.10173357.err`：

- `berkeley_rwawc` 状态已恢复为 `skipped_not_eligible`。
- stdout 中的 `NaN` 已被清洗成 `null`，JSON-safe 路径修复生效。
- `overall_status: completed_with_failures` 仍正确。
- 但 `job06` 的 stdout 中仍出现了一段 `traceback:`：
  - 位置：`temp/job06/job.10173357.out:698`
  - 内容是 `glwd_v2 produced an empty binary surface from combined_classes`
- 这段 traceback 不是主流程崩溃，而是一个**已处理的 domain failure** 被错误地当成调试栈打印进报告。
- stderr 中 `sys.excepthook` 噪音仍存在，因此本轮继续对最外层 wrapper 做了退出路径硬化。

## Business interpretation

- 这轮真正的业务失败仍是：`glwd_v2` 在当前 Amazon 小 bbox `(-61.0, -5.0, -60.0, -4.0)` 上没有形成可用的 binary comparison surface。
- 现在该失败会继续保留为：
  - `status=failed_empty_harmonized_surface`
  - `error=glwd_v2 produced an empty binary surface from combined_classes`
- 但不会再在最终报告中显示 traceback，避免把预期内失败伪装成未捕获崩溃。

## Verification status

- `uv run pytest tests/test_hpc_probe_rough_binary_script.py tests/test_rough_probe.py tests/test_loader_probe.py -q`: pass (`16 passed`)
- `uv run ruff check scripts/hpc_probe_rough_binary.py tests/test_hpc_probe_rough_binary_script.py src/WA/rough_probe.py src/WA/loader_probe.py tests/test_rough_probe.py tests/test_loader_probe.py`: pass

## Open risks, TODOs, rollback notes

- `glwd_v2` 的根因仍未完全查清：当前只知道在目标 bbox 上 binary surface 对齐后为空，但还没有完成“选中的 combined raster / bbox 内原始值分布 / nodata 占比 / 重投影前后 non-null count”的逐层诊断。
- HPC 环境的 `sys.excepthook` 噪音很可能来自 WA 之外的作业模板或 Python 启动环境；本轮 wrapper 已尽量规避，但如果 stderr 仍持续刷噪音，需要在更外层 job wrapper 中继续排查。
- 当前 rough probe 仍会因为 `failed_empty_harmonized_surface` 返回非零退出码；这符合“有失败就 fail job”的保守策略，但如果后续想把这类失败视作“允许的 partial completion”，需要重新定义退出码策略。

## Recommended next step

- 进入下一轮 `glwd_v2` 专项诊断：
  1. 记录当前 bbox 实际选中的 `combined_classes` 文件；
  2. 统计 bbox 内原始 class 值分布；
  3. 统计 `255` nodata 占比；
  4. 比较 binary 映射前后、重投影前后 `non_null_count`。
- 只有完成这条链路，才能判断 `glwd_v2` 到底是“这个 bbox 下确实无有效值”，还是“文件选择 / 映射 / 重投影逻辑仍有 bug”。
