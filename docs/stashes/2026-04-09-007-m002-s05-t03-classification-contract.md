# 2026-04-09 M002/S05/T03 Classification Contract Quick Reference

## 本次交付

- 新增 `src/WA/comparison/classification_contract.py`
  - 从 **真实** Phase 3.6 全局输出重写 region-scoped classification contract surface
  - 从 **真实** Phase 3.7 source trio（manifest + hotspot CSV + region CSV）重写 region-scoped classification hotspot family
  - 提供 classification surface / summary / hotspot 的 semantic reload helpers
- 新增 `scripts/run_phase4_classification_contract.py`
  - 支持 `--region`、`--subset canonical`、`--subset ten`
  - 默认年份固定为项目约定的 `2016`
  - `--skip/--no-skip` 明确控制是否复用现有 Phase 3.6 / Phase 3.7 / contract outputs
- 扩展 `src/WA/visualization/phase4.py`
  - 新增 `load_phase4_contract_classification_summary(...)`
  - 新增 `load_phase4_contract_classification_hotspot_table(...)`

## 关键语义

1. **classification contract family key 继续是 `canonical`**
   - 这是为了兼容现有 ledger / downstream 语义
   - 但 provenance 在 metadata 里明确固定为 `g2017+glwd_v2+gwd30`
2. **不在 Phase 4 adapter 里重算 disagreement / hotspot science**
   - disagreement surface 仍来自 `src/WA/comparison/phase36.py`
   - hotspot selection 仍来自 `src/WA/phase37_hotspots.py`
   - adapter 只负责 subset / rewrite / reload / fail-closed validation
3. **Phase 3.7 source trio 必须三件套完整且互相一致**
   - 不能只按 `region_id` 过滤 hotspot CSV 就信任它
   - 必须先从 Phase 3.7 manifest 取该 region 的 hotspot ids，再要求 CSV 恰好有这些 ids
4. **classification surface 保留完整诊断 payload**
   - `entropy`
   - `majority_class`
   - `agreement_count`
   - `joint_valid_mask`
   - `g2017/glwd_v2/gwd30` 的 unified dominant class
   - `g2017/glwd_v2/gwd30` 的 source dominant class

## 主要产物路径

- surface
  - `results/phase4/classification_surfaces/<region>/canonical__<region>__classification_surface.nc`
- summary
  - `results/phase4/classification_regional_summaries/<region>/canonical__<region>__classification_regional_summary.csv`
- hotspot pair
  - `results/phase4/classification_hotspot_manifests/<region>/canonical__<region>__classification_hotspot_manifest.json`
  - `results/phase4/classification_hotspot_manifests/<region>/canonical__<region>__classification_hotspot_manifest.csv`

## 已通过验证

- `ruff check src/WA/comparison/classification_contract.py scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py`
- `python scripts/run_phase4_classification_contract.py --help`
- `python -m pytest tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py -q` → `15 passed`

## Repo 级验证现状

- `python -m pytest tests/` 仍在 repo 既有边界处复现：
  - `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` 仍 fail
  - full suite 后段仍会被系统杀掉并退出 `137`
- 这不是本次 classification contract 变更新引入的 focused regression；本次新增 focused tests 全部通过

## HPC 命令

### 先跑单区 amazon（显式 `--no-skip`）

```bash
python scripts/run_phase4_classification_contract.py \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --year 2016 \
  --phase36-output-dir results/phase3.6 \
  --phase36-cache-dir results/cache/phase3_6 \
  --phase37-output-dir results/phase3.7_hotspots \
  --phase37-cache-dir results/cache/phase3_7 \
  --no-skip
```

### canonical subset

```bash
python scripts/run_phase4_classification_contract.py \
  --subset canonical \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --year 2016 \
  --phase36-output-dir results/phase3.6 \
  --phase36-cache-dir results/cache/phase3_6 \
  --phase37-output-dir results/phase3.7_hotspots \
  --phase37-cache-dir results/cache/phase3_7 \
  --no-skip
```

### ten-region widen

```bash
python scripts/run_phase4_classification_contract.py \
  --subset ten \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --year 2016 \
  --phase36-output-dir results/phase3.6 \
  --phase36-cache-dir results/cache/phase3_6 \
  --phase37-output-dir results/phase3.7_hotspots \
  --phase37-cache-dir results/cache/phase3_7 \
  --no-skip
```

## 继续排查时先看什么

- CLI logs：
  - `stage=phase36`
  - `stage=phase37`
  - `stage=classification_contract_write`
  - `stage=classification_reload`
- 如果 hotspot rewrite 异常：
  1. 先看 Phase 3.7 manifest 里的该 region hotspot ids
  2. 再看 CSV 是否正好有这些 ids
  3. 最后看 region CSV 的 `selected_count / quota / shortfall`
