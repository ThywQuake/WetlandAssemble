# 2026-04-09 M002/S05/T05 Scale-out Readiness Quick Reference

## 本次交付

- 新增 `src/WA/comparison/scaleout_readiness.py`
  - 用和 ledger 相同的 semantic reload 语义检查 `percentage / classification / trend` 三条 hotspot family
  - 每个 `region_id × metric_family` 都会输出明确的 `ready / missing / partial` 状态
  - readiness 行里固定带出 `reason`、`manifest_path`、`table_path`、`surface_output_path`、`summary_output_path`
  - `missing` 只表示 **manifest 和 CSV 都不存在**；partial pair、坏 metadata、mixed rows、缺 provenance 都归到 `partial`
- 新增 `scripts/run_phase4_scaleout_readiness.py`
  - 支持 `--region`、`--subset canonical`、`--subset ten`
  - 默认把 readiness 报告写到 `results/phase4/scaleout_readiness/`
  - 同时写 CSV + JSON 两份 deterministic report，适合先扫十区 readiness，再决定是否跑 wide ledger
- 更新 `scripts/run_phase4_hotspot_ledger.py`
  - help 现在明确告诉操作者先看 `run_phase4_scaleout_readiness.py`
  - 仍然 fail-closed，不会为不完整 family 写 ledger
  - 一旦某个 region 失败，会自动写一个 **单区 readiness diagnostic report**，并把三条 family 的 `status + path + reason` 打到日志里，而不是只冒出第一个裸异常
- 更新 `src/WA/test_selection.py`
  - Phase 4 相关测试路由现在包含新的 readiness surfaces，以及之前恢复的 classification/trend contract surfaces

## 关键路径

### readiness report 默认目录

- `results/phase4/scaleout_readiness/*.csv`
- `results/phase4/scaleout_readiness/*.json`

文件 stem 会稳定编码：

- selector（`subset-canonical` / `subset-ten` / `regions-...`）
- `percentage_key`
- `classification_key`
- `trend participant_set_key`

### ledger 失败时新增的诊断面

失败 region 会额外写：

- 对应 single-region readiness CSV/JSON
- 日志里三条 family 的：
  - `metric_family`
  - `status`
  - `manifest/table/surface/summary` 路径
  - `reason`

这样可以立刻区分：

1. family 还没生成（missing）
2. manifest / CSV 只写了一半（partial pair）
3. JSON/CSV/provenance 语义坏了（partial semantic failure）

## 已通过验证

- `ruff check src/WA/comparison/scaleout_readiness.py scripts/run_phase4_scaleout_readiness.py scripts/run_phase4_hotspot_ledger.py src/WA/test_selection.py tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py CHANGELOG.md`
- `python scripts/run_phase4_scaleout_readiness.py --help`
- `python scripts/run_phase4_hotspot_ledger.py --help`
- `python -m pytest tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py -q` → `23 passed`
- `python scripts/run_related_tests.py src/WA/comparison/scaleout_readiness.py scripts/run_phase4_scaleout_readiness.py scripts/run_phase4_hotspot_ledger.py src/WA/test_selection.py`
- 额外回归：`python -m pytest tests/test_test_selection.py -q` → `5 passed`

## Repo 级验证现状

- `python -m pytest tests/` 仍复现 repo 既有红条：
  - `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` 仍因浮点尾差失败
  - broader suite 后续仍会被系统杀掉并退出 `137`
- 单独重跑 `python -m pytest tests/test_mgrs_tiling.py -q` 仍是同一条既有失败，不是本次 readiness / ledger 改动引入的 focused regression

## HPC 命令

### 先扫 ten-region readiness

```bash
python scripts/run_phase4_scaleout_readiness.py \
  --subset ten \
  --output-root results/phase4 \
  --percentage-key canonical \
  --classification-key canonical \
  --trend-dataset-id gwd30 \
  --trend-dataset-id giems_mc \
  --trend-dataset-id topmodel \
  --trend-dataset-id swamps \
  --trend-dataset-id wad2m
```

### 如果只想看某个失败区的 readiness

```bash
python scripts/run_phase4_scaleout_readiness.py \
  --region amazon \
  --output-root results/phase4 \
  --percentage-key canonical \
  --classification-key canonical \
  --trend-dataset-id gwd30 \
  --trend-dataset-id giems_mc \
  --trend-dataset-id topmodel \
  --trend-dataset-id swamps \
  --trend-dataset-id wad2m
```

### readiness 通过后再跑 ten-region ledger final gate（显式 `--no-skip`）

```bash
python scripts/run_phase4_hotspot_ledger.py \
  --subset ten \
  --output-root results/phase4 \
  --ledger-key canonical \
  --percentage-key canonical \
  --classification-key canonical \
  --trend-dataset-id gwd30 \
  --trend-dataset-id giems_mc \
  --trend-dataset-id topmodel \
  --trend-dataset-id swamps \
  --trend-dataset-id wad2m \
  --no-skip
```

## 继续排查时先看什么

1. 先开 readiness JSON/CSV，看某个 region 是 `missing` 还是 `partial`
2. 如果是 `partial`：
   - 先看 manifest / table 是否是 partial pair
   - 再看 `error_message` 是否是 malformed metadata、mixed-region rows、或缺 provenance path
3. 如果 ledger 直接失败：
   - 先看它自动写出的 single-region readiness report
   - 再按日志里给出的 `manifest/table/surface/summary` 路径逐个核对
