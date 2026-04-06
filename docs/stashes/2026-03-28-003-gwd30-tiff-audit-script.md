# 2026-03-28 003 GWD30 TIFF Audit Script

## Context

`GWD30` 原始年瓦片中存在“下载中断但文件仍可被识别为 TIFF”的坏文件。此类文件可能在 stage/merge 时才暴露为 `RasterioIOError: Read failed`，因此需要一轮直接针对原始 TIFF 的全量体检。

## What Changed

- Added `scripts/check_gwd30_tiffs.py`
  - 直接扫描 `GWD30` 目录下的 `*_wetland_YYYY.tif`
  - 默认自动并行：优先读取 `WA_GWD30_AUDIT_WORKERS` / `SLURM_CPUS_PER_TASK` 等环境变量，未设置时回退本机 CPU，并做保守 cap
  - 在 root 解析 / 文件发现 / 开始扫描 / 写报告 / quarantine / 完成等阶段显式输出带 flush 的提示，避免 HPC 日志里“无输出像卡住”
  - 默认检查 canonical GWD30 profile：`GTiff` / `uint8` / `92` bands / `3661x3661` / `nodata=255`
  - 逐 block 读取整幅 TIFF，强制触发截断/损坏数据块的读错误
  - 输出 `summary.json` / `bad_files.csv` / `redownload_targets.txt`
  - 可选 `--quarantine-dir`，把坏文件移走，便于后续重下
- Added `tests/test_check_gwd30_tiffs.py`
  - 覆盖 metadata mismatch
  - 覆盖截断 TIFF read failure
  - 覆盖报告输出与 quarantine
  - 覆盖坏文件存在时返回非零退出码

## Validation

- `python -m pytest tests/test_check_gwd30_tiffs.py -q`
- `ruff check scripts/check_gwd30_tiffs.py tests/test_check_gwd30_tiffs.py`
- `python -m py_compile scripts/check_gwd30_tiffs.py tests/test_check_gwd30_tiffs.py`

## Next Step

在 HPC 或数据所在机器上运行：

```bash
python scripts/check_gwd30_tiffs.py --root /lustre/home/2200013429/Wetland_Assemble/data/GWD30 --quarantine-dir /lustre/home/2200013429/Wetland_Assemble/data/GWD30_corrupt
```

如需显式控制并发，可再加 `--workers N`。

然后按 `results/maintenance/gwd30_tiff_audit/redownload_targets.txt` 重下坏文件。
