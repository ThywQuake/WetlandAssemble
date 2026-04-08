# 2026-04-09 M002/S05/T01 十区 selector 速记

## 本次完成 / What shipped

- 在 `src/WA/comparison/evidence_contract.py` 冻结了共享 contract selector：
  - `canonical` 继续返回固定 4 区顺序：`amazon -> pantanal -> sudd -> borneo`
  - `ten` 新增为固定 10 区顺序：`amazon -> orinoco -> pantanal -> indogangetic -> mekong -> sudd -> congo -> okavango -> borneo -> northernaus`
  - 显式拒绝 `--subset` + `--region` 混用
  - 显式拒绝 duplicate region ids
- `scripts/run_phase4_regional.py` 现在支持 `--subset {canonical,ten}`，并在启动前输出 `stage=region-selector ... region_ids=[...]`。
- `scripts/run_phase4_regional.py` **没有** 被静默改成 ten-region default；无参数时仍保留旧的 macro+priority 全区运行，只是现在会把这一路径作为 `legacy-all-regions` 明确写进日志。
- `scripts/run_phase4_trend_contract.py` 和 `scripts/run_phase4_hotspot_ledger.py` 也统一到了同一套 `--subset {canonical,ten}` + ambiguity rejection + resolved-region logging。
- 增补 focused tests：
  - `tests/test_comparison/test_evidence_contract.py`
  - `tests/test_comparison/test_phase4_regional.py`

## 修改文件

- `src/WA/comparison/evidence_contract.py`
- `scripts/run_phase4_regional.py`
- `scripts/run_phase4_trend_contract.py`
- `scripts/run_phase4_hotspot_ledger.py`
- `tests/test_comparison/test_evidence_contract.py`
- `tests/test_comparison/test_phase4_regional.py`
- `CHANGELOG.md`
- `.gsd/KNOWLEDGE.md`

## 验证状态

### 已通过

- `ruff check src/WA/comparison/evidence_contract.py scripts/run_phase4_regional.py scripts/run_phase4_trend_contract.py scripts/run_phase4_hotspot_ledger.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_phase4_regional.py`
- `python scripts/run_phase4_regional.py --help`
- `python scripts/run_phase4_trend_contract.py --help`
- `python scripts/run_phase4_hotspot_ledger.py --help`
- `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_phase4_regional.py -q` → `36 passed`
- `bash -n scripts/submit_phase4_gwd30_pixel_stats.sh scripts/submit_phase4_gwd30_regional_year_split.sh scripts/submit_phase4_gwd30_tropical_shards.sh scripts/submit_phase4_trend_contract.sh`
- `python scripts/run_related_tests.py ...`（selector 命令能正常给出推荐 pytest 子集）

### 预期中的 partial / fail（因为 T02–T05 还没恢复）

- Slice-level long pytest 仍会在缺失文件处失败：
  - `tests/test_comparison/test_percentage_backbone.py`
  - `tests/test_comparison/test_percentage_hotspots.py`
  - `tests/test_comparison/test_classification_contract.py`
  - `tests/test_comparison/test_trend_contract.py`
  - `tests/test_comparison/test_scaleout_readiness.py`
  - `tests/test_submit_phase4_trend_contract.py`
- Slice-level long ruff 仍会在同类缺失 producer / readiness 文件处失败。
- Slice-level help chain 仍会在缺失脚本处失败：
  - `scripts/run_phase4_percentage_contract.py`
  - `scripts/run_phase4_classification_contract.py`
  - `scripts/run_phase4_scaleout_readiness.py`

## 当前风险 / TODO

- S05 还没有恢复 percentage / classification / trend-contract / readiness 的缺失 producer surfaces；T01 只是先把十区 selector 合同冻结。
- `run_phase4_hotspot_ledger.py --subset ten` 现在 selector 是正确且可见的，但在 T02/T03/T05 完成前，wide ledger 仍可能因 family 缺失而 fail-closed。
- 未来如果别的 CLI 也要支持十区 contract，应该复用 `EvidenceContract.resolve_regions(subset="ten")`，不要再写手工十区列表。

## 回滚提示

- 如果后续需要回退，本次变更的低风险点是：regional runner 的旧 no-arg 行为仍保留，所以撤销 subset plumbing 不会破坏现有 macro+priority 默认路线。
- 但不要回退 `EvidenceContract` 的 `ten` selector，否则后续 T02–T05 会重新散落出多份十区列表。

## HPC 命令（本次代码变更后可直接复制）

> 这些命令都用显式 subset；`--no-skip` 已按项目规则写出。

### 1) Regional 百分比主干：十区显式 selector

```bash
python scripts/run_phase4_regional.py \
  --subset ten \
  --dataset-id gwd30 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2016 \
  --end-year 2016 \
  --no-skip
```

### 2) Trend contract：十区显式 selector

```bash
python scripts/run_phase4_trend_contract.py \
  --subset ten \
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

### 3) Unified ledger：十区显式 selector（当前预期仍可能 fail-closed）

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

> 注意：第 3 条在 T02/T03/T05 之前仍可能因为 percentage/classification/readiness 相关 family 未补齐而失败；这是当前 slice reality，不是 selector regression。
