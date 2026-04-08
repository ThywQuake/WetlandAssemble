# 2026-04-09 M002/S05/T04 Trend Contract Checkpoints Quick Reference

## 本次交付

- 新增 `src/WA/comparison/trend_contract.py`
  - 恢复了每个 `dataset_id + region_id` 的 `trend_surface` NetCDF
  - 恢复了每个 `dataset_id + region_id` 的 `trend_regional_summary` CSV
  - surface / summary 都支持 semantic reload，metadata 不匹配会 fail-closed
- 扩展 `src/WA/comparison/trends.py`
  - 新增显式 trend checkpoint surface：`results/phase4/trend_checkpoints/<region>/...trend_checkpoint.nc`
  - checkpoint key 现在显式绑定 `region + dataset + aggregation + requested window`
  - metadata 同时保留 **requested window** 与 **actual result coverage**，避免月初时间戳被误判为 stale/mixed
- 更新 `scripts/run_phase4_trend_contract.py`
  - runner 现在先走 `stage=trend-load action=compute|reload` checkpoint，再写/重开 `stage=trend-write` dataset-scoped contract outputs，然后才进入 `stage=agreement` / `stage=trend-hotspots`
  - `--subset ten` 继续复用 T01 的 shared selector
  - partial surface/summary pair 或 mixed checkpoint metadata 都会显式报错，而不是静默复用
- 新增 `scripts/submit_phase4_trend_contract.sh`
  - 一次 fan out 一个 region 一个 job
  - **强制要求 `--repo`**，不再允许脚本静默回退到 `$HOME/repos/WA2`
  - 生成的每个 job command 都显式写出 participant dataset list 和 `--no-skip`
  - 每次 fanout 都会写一个 summary TSV，便于不打开所有 `.slurm` 脚本也能检查提交面

## 关键语义

1. **contract outputs 和 checkpoints 是分开的两层 surface**
   - contract outputs：稳定给 downstream 用，key 是 `dataset_id + region_id`
   - checkpoints：给 rerun/resume 用，key 是 `region + dataset + aggregation + requested window`
2. **checkpoint metadata 必须同时保存 requested window 和 actual result time range**
   - 例：请求到 `2004-12-31`，但月序列最后一个真实时间戳可能是 `2004-12-01`
   - 如果只存一个 time range，semantic reload 会把合法 checkpoint 误判成 mixed/stale
3. **agreement / hotspot family 继续只用 participant-set 语义**
   - dataset-scoped trend contract outputs 不挤占 participant-set key
   - agreement / hotspot 仍然是 sorted participant ids 驱动的 family
4. **skip 是 fail-closed 的**
   - checkpoint metadata 不匹配 → 直接失败
   - contract surface/summary pair 只要出现 partial pair → 直接失败
   - hotspot manifest/CSV pair 继续只接受完整且语义可重开的产物

## 主要产物路径

- checkpoint
  - `results/phase4/trend_checkpoints/<region>/<dataset>__<region>__<aggregation>__<start>_<end>__trend_checkpoint.nc`
- contract surface
  - `results/phase4/trend_surfaces/<region>/<dataset>__<region>__trend_surface.nc`
- contract summary
  - `results/phase4/trend_regional_summaries/<region>/<dataset>__<region>__trend_regional_summary.csv`
- agreement surface / summary
  - `results/phase4/trend_agreement_surfaces/<region>/<participant_set>__<region>__trend_agreement_surface.nc`
  - `results/phase4/trend_agreement_summaries/<region>/<participant_set>__<region>__trend_agreement_summary.csv`
- hotspot pair
  - `results/phase4/trend_hotspot_manifests/<region>/<participant_set>__<region>__trend_hotspot_manifest.json`
  - `results/phase4/trend_hotspot_manifests/<region>/<participant_set>__<region>__trend_hotspot_manifest.csv`
- submit summary TSV
  - `${JOBS_BASE}/phase4-trend-contract-<timestamp>.tsv`

## 已通过验证

- `ruff check src/WA/comparison/trend_contract.py src/WA/comparison/trends.py scripts/run_phase4_trend_contract.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_submit_phase4_trend_contract.py`
- `bash -n scripts/submit_phase4_trend_contract.sh`
- `python scripts/run_phase4_trend_contract.py --help`
- `python -m pytest tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_submit_phase4_trend_contract.py -q` → `34 passed`

## Repo 级验证现状

- `python -m pytest tests/` 仍会复现 repo 既有红条：
  - `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` 仍 fail（浮点尾差）
  - broader suite 后段仍会被系统杀掉并退出 `137`
- 单独重跑 `python -m pytest tests/test_mgrs_tiling.py -q` 仍是同一个既有失败，不是本次 trend contract/checkpoint 改动引入的 focused regression

## HPC 命令

### 单区 amazon，直接重建（显式 `--no-skip`）

```bash
python scripts/run_phase4_trend_contract.py \
  --region amazon \
  --dataset-id gwd30 \
  --dataset-id giems_mc \
  --dataset-id topmodel \
  --dataset-id swamps \
  --dataset-id wad2m \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --aggregation annual \
  --start-year 1990 \
  --end-year 2020 \
  --top-hotspots 10 \
  --no-skip
```

### canonical subset，逐区写 checkpoint + surface/summary + agreement/hotspots

```bash
python scripts/run_phase4_trend_contract.py \
  --subset canonical \
  --dataset-id gwd30 \
  --dataset-id giems_mc \
  --dataset-id topmodel \
  --dataset-id swamps \
  --dataset-id wad2m \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --aggregation annual \
  --start-year 1990 \
  --end-year 2020 \
  --top-hotspots 10 \
  --no-skip
```

### ten-region fanout submit（推荐 wide rerun）

```bash
bash scripts/submit_phase4_trend_contract.sh \
  --repo "$HOME/repos/WA" \
  --python-bin "$HOME/repos/WA/.venv/bin/python" \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --subset ten \
  --dataset-id gwd30 \
  --dataset-id giems_mc \
  --dataset-id topmodel \
  --dataset-id swamps \
  --dataset-id wad2m \
  --aggregation annual \
  --start-year 1990 \
  --end-year 2020 \
  --min-observations 5 \
  --min-overlap-years 5 \
  --top-hotspots 10 \
  --cpus 2 \
  --time 480 \
  --partition C064M0256G \
  --no-progress
```

> 注意：submit wrapper 现在**必须**显式传 `--repo`；脚本会拒绝静默回退到 `$HOME/repos/WA2`。

## 继续排查时先看什么

- CLI logs：
  - `stage=trend-load action=compute|reload`
  - `stage=trend-write action=write|rebuild|reload|ready`
  - `stage=agreement`
  - `stage=trend-hotspots`
- 如果 checkpoint reload 报 mixed metadata：
  1. 先看 requested window 是否和 rerun 命令一致
  2. 再看 checkpoint attrs 里的 `requested_time_range_*` / `result_time_range_*`
  3. 最后确认是否误复用了不同 aggregation 或不同 dataset 的 checkpoint
- 如果 submit wrapper 输出不对：
  1. 先看 summary TSV
  2. 再看每个 `submit.slurm` 里是否显式带了 `--region ... --dataset-id ... --no-skip`
  3. 最后确认 `--repo` 指向的 HPC worktree 里确实存在 `scripts/run_phase4_trend_contract.py`
