# 2026-03-28 006 GWD30 Size Manifest Check Script

## Context

远端 `gwd30_remote_sizes.csv` 已经抓取完成。下一步需要一个适合在 HPC 上运行的本地脚本，只通过文件 `stat().st_size` 与 manifest 逐条比对，快速找出所有体积不匹配或缺失的 TIFF。

## What Changed

- Added `scripts/check_gwd30_sizes_from_manifest.py`
  - 输入远端 size manifest CSV
  - 默认 `--root` 走 `datasets.gwd30.path`
  - 默认 manifest 路径是 `temp/check_gwd30/remote_sizes/gwd30_remote_sizes.csv`
  - 用 `tqdm` 逐条检查本地 `st_size`
  - 记录三类异常:
    - `missing_file`
    - `size_mismatch`
    - `stat_failed`
  - 输出:
    - `mismatches.csv`
    - `mismatches.json`
    - `mismatch_paths.txt`
    - `summary.json`
  - 当存在异常时返回退出码 `2`
- Added `tests/test_check_gwd30_sizes_from_manifest.py`
  - 覆盖 manifest 读取与 year/filter/limit
  - 覆盖缺失文件与 size mismatch
  - 覆盖报告文件落盘
  - 覆盖 `_run()` 的退出码和阶段输出

## Validation

- `python -m py_compile scripts/check_gwd30_sizes_from_manifest.py tests/test_check_gwd30_sizes_from_manifest.py`
- `ruff check scripts/check_gwd30_sizes_from_manifest.py tests/test_check_gwd30_sizes_from_manifest.py`
- `python -m pytest tests/test_check_gwd30_sizes_from_manifest.py -q`
- `python -m pytest tests/ -q`

## HPC Command

如果远端 manifest 已经和代码一起同步到 HPC，可直接运行:

```bash
python scripts/check_gwd30_sizes_from_manifest.py \
  --root /lustre/home/2200013429/Wetland_Assemble/data/GWD30 \
  --manifest-csv temp/check_gwd30/remote_sizes/gwd30_remote_sizes.csv \
  --output-dir results/maintenance/gwd30_size_check
```

如果 manifest 放在别的地方，把 `--manifest-csv` 改成对应绝对路径即可。
