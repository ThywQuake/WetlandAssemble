# 2026-04-08 M002/S04/T01 Trend Hotspot Contract Summary

## Summary

- 补齐了 Phase 4 trend hotspot contract：新增 `src/WA/comparison/trend_hotspots.py`，把 trend hotspot 输出固定成 **JSON manifest + CSV companion**，并且按 **排序后的 participant ids** 生成稳定的 `participant_set_key`。
- 新增 `scripts/run_phase4_trend_contract.py`，现在先写/验 `trend_agreement_surface + trend_agreement_summary`，再跑 `stage=trend-hotspots`；如果 agreement 或 hotspot 只写了一半，runner 会 **fail closed**，不会把半成品当缓存复用。
- `src/WA/visualization/phase4.py` 新增 `load_phase4_contract_trend_hotspot_table(...)`，上层可以按 `region_id + participant_ids` 语义重开热点，不再猜文件名。

## Key Files

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/trend_hotspots.py`
- `scripts/run_phase4_trend_contract.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_evidence_contract.py`
- `tests/test_comparison/test_trend_hotspots.py`
- `tests/test_visualization/test_phase4.py`
- `src/WA/test_selection.py`
- `CHANGELOG.md`

## Verification

Passed:

- `uvx ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_hotspots.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md`
- `uv run python scripts/run_phase4_trend_contract.py --help`
- `uv run --with pytest python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_visualization/test_phase4.py -q`
- `uv run python scripts/run_related_tests.py src/WA/comparison/evidence_contract.py src/WA/comparison/trend_hotspots.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py`
- 额外 smoke：直接验证了 `stage=agreement` / `stage=trend-hotspots` 日志和 `Phase4 semantic reload failed ...` 失败信息。

Not clean yet:

- `uv run --with pytest python -m pytest tests/ -x` 在 **无关本任务** 的 `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` 失败（精确浮点断言差 3e-16 量级）。
- `uv run --with pytest python -m pytest tests/` 也跑过，但继续跑完整套后退出 `137`。

## Important Notes

- 这个 auto-mode 环境没有裸 `python` 命令，验证时实际用了 `uv run python` / `uv run --with pytest python`。
- HPC 侧如果要验证新 runner，按项目约定用 `--no-skip`：

```bash
python scripts/run_phase4_trend_contract.py \
  --region amazon \
  --dataset-id gwd30 \
  --dataset-id giems_mc \
  --dataset-id topmodel \
  --dataset-id swamps \
  --dataset-id wad2m \
  --output-root results/phase4 \
  --standardized-dir output/standardized \
  --aggregation annual \
  --start-year 1990 \
  --end-year 2020 \
  --top-hotspots 10 \
  --no-skip
```
