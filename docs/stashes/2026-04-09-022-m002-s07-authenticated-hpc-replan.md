# 2026-04-09 M002/S07 authenticated-HPC replan quick reference

## What changed
- Replanned S07 after T02 proved the remaining work cannot run from the auto-mode container because the HPC sync/ssh path requires OTP-authenticated access.
- Preserved completed tasks `T01` and `T02` unchanged.
- Rewrote `T03` so it now starts with an authenticated `rsync`/HPC session, reruns the missing ten-region percentage + classification producers, then submits and monitors the ten-region trend wrapper before copying proof artifacts back.
- Rewrote `T04` so readiness + unified ledger now run only after those authenticated outputs exist, fail closed on any `missing`/`partial` row, and copy the final proof artifacts back into the repo.

## Files touched
- `.gsd/milestones/M002/slices/S07/S07-PLAN.md`
- `.gsd/milestones/M002/slices/S07/S07-REPLAN.md`
- `.gsd/milestones/M002/slices/S07/tasks/T03-PLAN.md`
- `.gsd/milestones/M002/slices/S07/tasks/T04-PLAN.md`
- `docs/stashes/2026-04-09-022-m002-s07-authenticated-hpc-replan.md`

## Verification status
- `gsd_replan_slice` for `M002 / S07 / blocker T02` ✅
- Task plan files now match the replanned authenticated-HPC execution boundary ✅
- No code tests were rerun because this unit only changed planning artifacts; real verification still requires the authenticated HPC commands embedded in `T03` and `T04`.

## Open risks / TODOs
1. A real OTP-authenticated workstation session is still required; the auto-mode container cannot satisfy that boundary.
2. Do not resume S07 from readiness/ledger directly; T03 must first materialize percentage/classification outputs and finish the trend fanout.
3. Keep the frozen ten-region order, canonical keys, and trend dataset ids including `topmodel`.
4. Sync proof artifacts back into the repo after each remote leg so S08 has local evidence to consume.

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
- 这次不是修代码，而是把 S07 的剩余步骤改成**必须在已认证 HPC 会话里执行**的真实物化路径。
- `T03` 现在先做已认证同步，再补跑 percentage/classification，随后提交并盯完 ten-region trend fanout。
- `T04` 现在只在上述真实输出存在后才允许跑 readiness 和 unified ledger，并且任何 `missing` / `partial` 都必须 fail closed。
- 下一步不是继续本地 auto-mode 容器验证，而是按上面的 HPC 命令在已认证终端里执行并把 proof artifacts 同步回 repo。
