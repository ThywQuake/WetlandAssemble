# 2026-04-09 M002/S05 Ten-region Scale-out Research Quick Reference

## 最重要结论

S05 不是“直接加十区调度”这么简单。当前 repo 真正可执行的宽范围骨干只有：

- **percentage regional backbone**：`src/WA/comparison/phase4_regional.py`
- **GWD30 Stage-1/Stage-2 submit**：
  - `scripts/submit_phase4_gwd30_pixel_stats.sh`
  - `scripts/submit_phase4_gwd30_regional_year_split.sh`
  - `scripts/submit_phase4_gwd30_tropical_shards.sh`
- **trend contract runner**：`scripts/run_phase4_trend_contract.py`
- **unified ledger runner**：`scripts/run_phase4_hotspot_ledger.py`

但很多前序 slice 文档里写的 producer 在当前 snapshot **并不存在**：

- `src/WA/comparison/percentage_hotspots.py`
- `scripts/run_phase4_percentage_contract.py`
- `src/WA/comparison/classification_contract.py`
- `scripts/run_phase4_classification_contract.py`
- `src/WA/comparison/trend_contract.py`

所以 S05 的第一风险不是“十区并行怎么做”，而是：**三条线里 percentage/classification 的 contract producer 现实上并没有落在当前 repo 里**。ledger 只能重开已有 family，不能替你生成 missing families。

## 规划建议顺序

1. **先退休 producer-reality gap**
   - 要么恢复缺失的 percentage / classification contract producer
   - 要么明确 replan，因为否则 S05 无法真实完成三线十区 proof

2. **再加一个共享 ten-region selector**
   - `EvidenceContract` 现在只有 `canonical` 或显式 `--region`
   - `run_phase4_regional.py` 默认会跑 **16 个 region**（6 macro + 10 priority），不能直接拿来当 S05 ten-region default

3. **percentage 继续走现有 split/cache/merge**
   - Stage 1: pixel stats 按年 fanout
   - Stage 2: regional year split + merge
   - 太重时再上 tropical shard/reduce

4. **trend 再补 operational proof**
   - 当前 trend runner 每个 region 仍直接从 source/staged tiles 重新算
   - 只有 agreement/hotspot 成品 cache，没有更深一层 split/cache/merge

5. **最后才跑 unified ledger**
   - 它应当是 final gate，不是上游生成器

## 当前最值得改的文件边界

- `src/WA/comparison/evidence_contract.py`
  - 加 ten-region alias / ordered helper 的最佳位置
- `src/WA/comparison/phase4_regional.py`
  - 现有 percentage + GWD30 year-cache 真正骨干
- `scripts/run_phase4_regional.py`
  - 需要避免默认 macro-region 泄漏到 S05
- `src/WA/comparison/trends.py`
  - 当前 trend 对 GWD30 仍按 region/year 直接 merge staged tiles
- `scripts/run_phase4_trend_contract.py`
  - 现有 trend 宽范围 proof 入口
- `src/WA/comparison/hotspot_ledger.py` / `scripts/run_phase4_hotspot_ledger.py`
  - final integration gate
- `src/WA/comparison/phase36.py` + `src/WA/phase37_hotspots.py`
  - 如果要恢复 classification contract producer，这两处是上游 science source
- `scripts/plot_tropical_wetland_025deg.py`
  - 如果要恢复 percentage contract producer，这是非 GWD30 的 surface source

## 额外坑点

- submit 脚本默认 `REPO=$HOME/repos/WA2`，S05 文档/脚本必须显式传 `--repo`
- trend 默认 participant set 现在包含 `topmodel`，和部分旧文档不一致
- ledger / phase4 tests 里 percentage/classification source 主要是 synthetic fixture，不是 end-to-end 真实 producer
- `config/` 不能动；ten-region alias 应放代码里，不要改 `config/priority_regions.yaml`
- HPC 仍按项目规则用 `rsync`，不是 git push/pull

## 当前可执行的 HPC ladder（真实存在）

### GWD30 Stage-1

```bash
bash scripts/submit_phase4_gwd30_pixel_stats.sh \
  --repo "$HOME/repos/WA" \
  --python-bin "$HOME/repos/WA/.venv/bin/python" \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --years 2013,2014,2015,2016,2017,2018,2019,2020,2021,2022 \
  --aggregation monthly \
  --worker-count 4 \
  --cpus 4 \
  --no-skip
```

### GWD30 Stage-2（先 amazon）

```bash
bash scripts/submit_phase4_gwd30_regional_year_split.sh \
  --repo "$HOME/repos/WA" \
  --python-bin "$HOME/repos/WA/.venv/bin/python" \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --region amazon \
  --years 2013,2014,2015,2016,2017,2018,2019,2020,2021,2022 \
  --no-skip
```

### trend（先 amazon，再 canonical，再十区显式 region 列表）

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

### ledger（注意：只有 percentage/classification/trend families 都齐了才会成功）

```bash
python scripts/run_phase4_hotspot_ledger.py \
  --region amazon \
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
