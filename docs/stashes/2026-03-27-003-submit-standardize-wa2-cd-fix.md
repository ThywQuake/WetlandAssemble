# submit_standardize WA2 切目录修正

**Date:** 2026-03-27  
**Branch:** `refactor/loader-reference-grid-alignment`

## 修改

- `scripts/submit_standardize.sh`
  - 默认 `REPO` 直接改成 `~/repos/WA2`
  - 生成的子脚本现在显式执行 `cd ${REPO} || exit 1`
  - `cd` 后打印实际工作目录，便于看日志确认是否进入了正确的 `WA2`

## Why

用户在 HPC 上的实际问题是子脚本没有进入正确的 `WA2` 仓库，导致：

- `.venv/bin/activate` 找不到
- `python` 不在 PATH 里

先 `cd ~/repos/WA2` 再运行，问题最直接。
