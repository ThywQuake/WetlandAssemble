# 2026-04-09 M002/S07 override document rewrite quick reference

## What changed
- Applied and resolved override `2026-04-09T03:32:26.852Z` (`Change: auto`) across the active M002/S07 planning surface.
- Added decision `D053` in `.gsd/DECISIONS.md` to supersede D052's temporary active-override wording with a standing rule:
  - auto-mode still owns local verification, proof bookkeeping, and focused fix/resync loops
  - OTP-authenticated HPC materialization / readiness / ledger work remains a fail-closed external boundary
- Updated `.gsd/milestones/M002/slices/S07/S07-PLAN.md` so Goal/Demo explicitly require authenticated HPC execution plus synced-back proof artifacts.
- Updated incomplete task plans:
  - `.gsd/milestones/M002/slices/S07/tasks/T03-PLAN.md`
  - `.gsd/milestones/M002/slices/S07/tasks/T04-PLAN.md`
  Both now reference the resolved override state and D053 rather than an active override flag.
- Updated `.gsd/REQUIREMENTS.md` so:
  - `R107` now makes sync-back/authenticated-HPC proof part of what counts as done
  - `R113` now makes synced-back readiness/ledger evidence part of valid paper-pack completion
- Updated `.gsd/PROJECT.md` and `.gsd/milestones/M002/M002-ROADMAP.md` so project-level route truth includes S07/S08 and the authenticated-HPC boundary.
- Marked `.gsd/OVERRIDES.md` scope as `resolved`.

## Verification status
- Read back all targeted docs after edit ✅
- `git diff` checked for the targeted document set ✅
- No code tests rerun; this unit only rewrote planning/decision/requirement/project artifacts ✅

## Open risks / next step
1. The OTP-protected workstation/HPC boundary is still real; this rewrite does **not** make T03/T04 runnable from the container alone.
2. S07 still requires the authenticated command ladder from the frozen proof bundle.
3. S08 should only run after real S07 artifacts are synced back.

## Exact next HPC reminder
```bash
rsync -avz --delete --exclude-from=.gitignore ./ \
  2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/
ssh 2200013429@wm2-data.pku.edu.cn
cd /lustre/home/2200013429/repos/WA2
python scripts/run_phase4_percentage_contract.py --subset ten --output-root results/phase4 --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --dataset-key canonical --surface-year 2016 --start-year 1990 --end-year 2020 --no-skip
python scripts/run_phase4_classification_contract.py --subset ten --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --classification-key canonical --year 2016 --phase36-output-dir results/phase3.6 --phase36-cache-dir results/cache/phase3_6 --phase37-output-dir results/phase3.7_hotspots --phase37-cache-dir results/cache/phase3_7 --no-skip
bash scripts/submit_phase4_trend_contract.sh --repo "$PWD" --python-bin "$PWD/.venv/bin/python" --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --subset ten --dataset-id gwd30 --dataset-id giems_mc --dataset-id topmodel --dataset-id swamps --dataset-id wad2m --aggregation annual --start-year 1990 --end-year 2020 --min-observations 5 --min-overlap-years 5 --top-hotspots 10 --cpus 2 --time 480 --partition C064M0256G --jobs-base temp/slurm-jobs-s07 --tmp-root temp/slurm-tmp-s07 --no-progress
```

## 中文摘要
- 已把 `auto` override 正式传播到 S07 的 slice/task 计划、决策、需求、项目总览和 roadmap 文档里，并把 `.gsd/OVERRIDES.md` 从 `active` 改成了 `resolved`。
- 新决策 `D053` 明确：自动模式仍负责本地校验、proof 记录、以及有问题时的定点修复/重同步循环；但 OTP 认证的 HPC 物化、readiness、ledger 仍然是硬边界，不能被假装成容器内可直接完成。
- `R107` / `R113` 也同步更新了“done”的定义：只有真实 HPC 产物已经生成并 sync back 后，十区 proof 和 strict paper-pack 才能算真正闭环。
- 下一步仍然是到已认证终端执行上面的 HPC 命令，然后把 S07 真实 artifacts 同步回 repo 再进入 S08。
