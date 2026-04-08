# 2026-04-09 M002/S07/T02 producer materialization blocked quick reference

## What happened
- T02 did **not** materialize the ten-region percentage/classification families in this auto-mode session.
- The repo-local `sync-hpc` route points at `2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/`, but from this container both `ssh` and `rsync` stop at `OTP Verification Fail!` / `Permission denied (keyboard-interactive)`.
- Local direct producer runs fail exactly where they should when the HPC standardized tree is absent:
  - percentage: `FileNotFoundError: No standardized files were found for berkeley_rwawc`
  - classification: `FileNotFoundError: File does not exist: .../standardized/g2017.nc`

## Why this matters
- No real ten-region percentage/classification outputs exist in the repo yet.
- Readiness and unified ledger must **not** be rerun as if T02 had succeeded.
- No producer code was patched in T02 because the observed stop condition is external auth/input availability, not a new semantic contract bug.

## Verified locally
- `--subset ten` still resolves the frozen ordered list ending in `northernaus`.
- Missing GWD30 inputs still raise `stage=percentage-surface` context.
- Classification contract still rejects missing `gwd30_source_dominant_class` and mixed-region Phase 3.7 hotspot rows.

## Exact next commands after authenticated HPC access
```bash
rsync -avz --delete --exclude-from=.gitignore ./ \
  2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/

ssh 2200013429@wm2-data.pku.edu.cn
cd /lustre/home/2200013429/repos/WA2
python scripts/run_phase4_percentage_contract.py \
  --subset ten \
  --output-root results/phase4 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --surface-year 2016 \
  --start-year 1990 \
  --end-year 2020 \
  --no-skip
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

## Expected representative outputs once rerun succeeds
- `results/phase4/hotspot_manifests/amazon/canonical__amazon__hotspot_manifest.json`
- `results/phase4/hotspot_manifests/northernaus/canonical__northernaus__hotspot_manifest.json`
- `results/phase4/classification_hotspot_manifests/amazon/canonical__amazon__classification_hotspot_manifest.json`
- `results/phase4/classification_hotspot_manifests/northernaus/canonical__northernaus__classification_hotspot_manifest.json`

## Chinese recap / 中文回顾
- 本次阻塞点不是 producer 代码逻辑，而是 auto-mode 容器无法完成 HPC 的 OTP 交互认证。
- 真实十区物化仍需在已认证的 HPC 会话中按冻结命令重跑，并继续保持 `--subset ten` + canonical keys + `--no-skip`。
- 后续 agent 先看 `results/phase4/proof/phase4-producer-materialization.md`，再决定是否继续 T03/T04。
