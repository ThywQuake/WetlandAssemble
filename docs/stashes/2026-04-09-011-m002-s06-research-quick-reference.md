# 2026-04-09 M002/S06 Research Quick Reference

## 核心结论

S06 不是新 science slice；三条线的 contract producer、readiness、ledger 都已经有了。真正缺的是：

1. **paper-ready pack builder**（figure/table/summary/manifest）
2. **strict integration proof**（基于 readiness + ledger 的十区重新集成证明）
3. **缺失的下游 reload API**（尤其 trend agreement summary/surface 目前还困在 `scripts/run_phase4_trend_contract.py` 的私有 helper 里）

## 当前 repo 里已经能直接复用的文件

- `src/WA/comparison/evidence_contract.py` — ordered `ten` selector + artifact semantics
- `src/WA/comparison/percentage_backbone.py` — percentage surface/summary reload
- `src/WA/comparison/percentage_hotspots.py` — percentage hotspot manifest/table reload
- `src/WA/comparison/classification_contract.py` — classification surface/summary/hotspot reload
- `src/WA/comparison/trend_contract.py` — per-dataset trend surface/summary reload
- `src/WA/comparison/hotspot_ledger.py` — cross-line unified hotspot ledger
- `src/WA/comparison/scaleout_readiness.py` — ready/missing/partial preflight gate
- `src/WA/visualization/phase4.py` — 已有 percentage interannual/climatology plotting helpers，但目前只有测试在用，没有 production CLI

## 关键缺口

- **没有** `phase4_pack.py` / `run_phase4_evidence_pack.py`
- **没有** paper pack manifest
- **没有** milestone integration proof artifact writer
- **没有** trend agreement 的 public semantic reload helper
- `results/phase4/` 本地目前只有 readiness smoke outputs，没有真实十区 science artifacts

## 最推荐的任务顺序

1. **先补 pack-safe reload API**
   - 把 trend agreement reload 从 runner script 提升成 public helper
   - 可顺手把 percentage reload wrapper 也补到 `WA.visualization.phase4`
2. **再做 paper-pack module + CLI**
   - 建议新文件：
     - `src/WA/visualization/phase4_pack.py`
     - `scripts/run_phase4_evidence_pack.py`
     - `tests/test_visualization/test_phase4_pack.py`
3. **最后加 strict integration proof mode**
   - 先查 readiness
   - 不全就 fail closed
   - readiness 通过后逐区重开 ledger
   - 生成 Markdown + CSV/JSON proof artifact

## 不要踩的坑

- 不要手写 ten-region list；用 `contract.resolve_regions(subset="ten")`
- 不要猜文件名；走 semantic reload / contract paths
- 不要再造第二套 hotspot schema；直接复用 unified ledger
- 不要把 pack 输出塞回 `results/phase4` science artifact family 里
- 如果要用现成 `plot_phase4_interannual(...)`，**percentage summary 不能只跑 2016**

## HPC ladder（S06 真正 proof 前置）

### percentage（建议改成 paper-friendly summary window）

```bash
python scripts/run_phase4_percentage_contract.py \
  --subset ten \
  --output-root results/phase4 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --surface-year 2016 \
  --start-year 1990 \
  --end-year 2020 \
  --no-skip
```

### classification

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

### trend

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

### readiness + ledger

```bash
python scripts/run_phase4_scaleout_readiness.py --subset ten --output-root results/phase4 \
  --percentage-key canonical --classification-key canonical \
  --trend-dataset-id gwd30 --trend-dataset-id giems_mc --trend-dataset-id topmodel \
  --trend-dataset-id swamps --trend-dataset-id wad2m
```

```bash
python scripts/run_phase4_hotspot_ledger.py --subset ten --output-root results/phase4 \
  --ledger-key canonical --percentage-key canonical --classification-key canonical \
  --trend-dataset-id gwd30 --trend-dataset-id giems_mc --trend-dataset-id topmodel \
  --trend-dataset-id swamps --trend-dataset-id wad2m --no-skip
```

### future pack CLI shape

```bash
python scripts/run_phase4_evidence_pack.py \
  --subset ten \
  --phase4-output-root results/phase4 \
  --pack-output-root results/figures/phase4_pack \
  --ledger-key canonical \
  --percentage-key canonical \
  --classification-key canonical \
  --trend-dataset-id gwd30 \
  --trend-dataset-id giems_mc \
  --trend-dataset-id topmodel \
  --trend-dataset-id swamps \
  --trend-dataset-id wad2m \
  --strict
```
