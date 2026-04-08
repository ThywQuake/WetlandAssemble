# 2026-04-09 M002/S05 计划速记

## 核心判断

S05 不能直接进入“十区并行”。当前 repo 里真正缺的是 **真实可执行的 producer 链**：

- percentage：缺 `src/WA/comparison/percentage_backbone.py`、`src/WA/comparison/percentage_hotspots.py`、`scripts/run_phase4_percentage_contract.py`
- classification：缺 `src/WA/comparison/classification_contract.py`、`scripts/run_phase4_classification_contract.py`
- trend：现有 `scripts/run_phase4_trend_contract.py` 只稳定写 agreement / hotspot，不足以支撑十区可复跑 proof

因此 S05 计划先补 producer reality，再补 scale-out orchestration，最后再用 ledger 做 final gate。

## 新决策

- **D042**：S05 必须先恢复缺失的 percentage / classification producer，并在代码里冻结 ordered ten-region selector；ledger 只做 final readiness gate，不做上游生成器。

## 任务拆分

1. **T01 — 冻结 ten-region selector + subset plumbing**
   - 在 `EvidenceContract` 里加稳定 ten-region alias
   - 让 `run_phase4_regional.py` / `run_phase4_trend_contract.py` / `run_phase4_hotspot_ledger.py` 共享这套解析
   - 明确拒绝 `--subset` + `--region` 混用

2. **T02 — 恢复 percentage contract backbone / hotspots / runner**
   - 恢复 `percentage_backbone.py`
   - 恢复 `percentage_hotspots.py`
   - 新增 `run_phase4_percentage_contract.py`
   - 把 GWD30 接回共享 `0.25°` contract path

3. **T03 — 恢复 classification contract adapter / runner**
   - 恢复 `classification_contract.py`
   - 恢复 `run_phase4_classification_contract.py`
   - 补 phase4 semantic reload

4. **T04 — 恢复 trend surface/summary 写出 + checkpoint + submit wrapper**
   - 恢复 `trend_contract.py`
   - 让 trend wide run 有明确 checkpoint / reload 面
   - 新增 `submit_phase4_trend_contract.sh`

5. **T05 — 加 ten-region readiness report，并保持 ledger fail-closed**
   - 新增 `scaleout_readiness.py`
   - 新增 `run_phase4_scaleout_readiness.py`
   - `run_phase4_hotspot_ledger.py` 继续做 final gate

## 计划验证面

- Focused pytest:
  - `tests/test_comparison/test_evidence_contract.py`
  - `tests/test_comparison/test_phase4_regional.py`
  - `tests/test_comparison/test_percentage_backbone.py`
  - `tests/test_comparison/test_percentage_hotspots.py`
  - `tests/test_comparison/test_classification_contract.py`
  - `tests/test_comparison/test_trend_contract.py`
  - `tests/test_comparison/test_trends.py`
  - `tests/test_comparison/test_hotspot_ledger.py`
  - `tests/test_comparison/test_scaleout_readiness.py`
  - `tests/test_visualization/test_phase4.py`
  - `tests/test_plot_tropical_wetland_025deg.py`
  - `tests/test_submit_phase4_gwd30_pixel_stats.py`
  - `tests/test_submit_phase4_gwd30_regional_year_split.py`
  - `tests/test_submit_phase4_gwd30_tropical_shards.py`
  - `tests/test_submit_phase4_trend_contract.py`
- Shell syntax:
  - `bash -n scripts/submit_phase4_gwd30_pixel_stats.sh scripts/submit_phase4_gwd30_regional_year_split.sh scripts/submit_phase4_gwd30_tropical_shards.sh scripts/submit_phase4_trend_contract.sh`
- CLI help:
  - `run_phase4_percentage_contract.py`
  - `run_phase4_classification_contract.py`
  - `run_phase4_trend_contract.py`
  - `run_phase4_hotspot_ledger.py`
  - `run_phase4_scaleout_readiness.py`

## 关键风险

- 旧 `.gsd` slice summary 与当前 repo reality 继续漂移；执行时必须以当前文件系统为准。
- percentage 与 trend 的宽范围路径都涉及较重 I/O；必须保留显式 cache / checkpoint / `--no-skip` 诊断面。
- submit 脚本默认 `REPO=$HOME/repos/WA2` 的风险仍在；S05 的 submit surface 必须把 `--repo` 作为显式操作习惯。

## 执行顺序理由

先做 T01 固定 region selector，避免后续所有 runner 各自发明十区列表；再恢复 percentage / classification / trend 三条 producer 链；最后做 readiness + ledger gate，这样完成后 slice goal 才是真的。