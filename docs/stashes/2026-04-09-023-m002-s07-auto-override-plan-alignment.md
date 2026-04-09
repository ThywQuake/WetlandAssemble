# 2026-04-09 M002/S07 auto-override plan alignment quick reference

## What changed
- Read `.gsd/OVERRIDES.md` and aligned the active planning surface to the saved `auto` override at `M002/S07/T03`.
- Recorded decision `D052` in `.gsd/DECISIONS.md` so future agents treat auto-mode as the active posture **without** erasing the real OTP-authenticated HPC boundary.
- Updated the active slice plan at `.gsd/milestones/M002/slices/S07/S07-PLAN.md` with an explicit execution-override note.
- Updated the incomplete task plans:
  - `.gsd/milestones/M002/slices/S07/tasks/T03-PLAN.md`
  - `.gsd/milestones/M002/slices/S07/tasks/T04-PLAN.md`

## Current interpretation
- `auto` is the active execution posture.
- Auto-mode still owns local prep, proof bookkeeping, focused code-fix loops, and resync instructions.
- The OTP-protected HPC sync/submit leg is still a hard external execution boundary.
- Therefore T03/T04 are **not** reinterpreted as runnable from this container alone; they remain fail-closed authenticated-workstation tasks.

## Why this matters
Without this alignment, a later agent could misread the override as permission to keep pushing the container past the known OTP boundary, which would either repeat the blocked ssh/rsync attempts or weaken the proof contract.

## Verification status
- `.gsd/OVERRIDES.md` read ✅
- `D052` recorded in `.gsd/DECISIONS.md` ✅
- S07 plan updated ✅
- T03/T04 plan files updated ✅
- No code tests rerun; this change only updates planning/decision artifacts ✅

## Exact next HPC commands
```bash
rsync -avz --delete --exclude-from=.gitignore ./ \
  2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/
ssh 2200013429@wm2-data.pku.edu.cn
cd /lustre/home/2200013429/repos/WA2
python scripts/run_phase4_percentage_contract.py \
  --subset ten \
  --output-root results/phase4 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --dataset-key canonical \
  --surface-year 2016 \
  --start-year 1990 \
  --end-year 2020 \
  --no-skip
python scripts/run_phase4_classification_contract.py \
  --subset ten \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --classification-key canonical \
  --year 2016 \
  --phase36-output-dir results/phase3.6 \
  --phase36-cache-dir results/cache/phase3_6 \
  --phase37-output-dir results/phase3.7_hotspots \
  --phase37-cache-dir results/cache/phase3_7 \
  --no-skip
bash scripts/submit_phase4_trend_contract.sh \
  --repo "$PWD" \
  --python-bin "$PWD/.venv/bin/python" \
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
  --jobs-base temp/slurm-jobs-s07 \
  --tmp-root temp/slurm-tmp-s07 \
  --no-progress
```

## 中文摘要
- 我已经读取 `.gsd/OVERRIDES.md`，并把当前活动范围的 `auto` override 对齐到 S07/T03-T04 的计划文档里。
- 新决策 `D052` 明确规定：**auto-mode 仍然是当前执行姿态**，但 OTP 认证的 HPC 同步/提交步骤依然是硬边界，不能假装本容器能直接跑完。
- 因此 T03/T04 现在写得更清楚：本地自动模式负责准备、记录、修复与重同步；真正的十区 HPC 物化、trend fanout、readiness、ledger 仍需在已认证工作站/HPC 会话里执行。
- 下一步仍然是按上面的 HPC 命令在已认证终端执行，并把 proof artifacts 同步回 repo。
