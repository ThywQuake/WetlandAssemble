# 2026-03-28 004 GWD30 Manifest Audit Optimization

## Context

`GWD30` 根目录下本来就有逐年的 `GWD30_file_list_YYYY.json`，内容是超长文件名数组。此前 TIFF 体检脚本错误地默认扫盘，并且默认逐 block 解码整幅 TIFF，在 Lustre/HPC 上过慢。

## What Changed

- Updated `scripts/check_gwd30_tiffs.py`
  - 默认 discovery 改为读取 `GWD30_file_list_YYYY.json`，把 bare filename 解析为 `root/YYYY/filename`
  - 仅当显式传 `--allow-disk-scan` 时才退回扫描目录树
  - 新增 `--read-mode {footprint,sampled,full}`
  - 默认 `footprint`：用 `tifffile` 检查 TIFF segment offset/bytecount 是否越过文件尾，专门针对“下载被截断但头部仍像 TIFF”的坏文件
  - `sampled`：在 footprint 基础上再读少量代表性 block
  - `full`：保留原来的全 block 解码
  - summary / 终端输出里会记录实际 `read_mode`
- Updated `tests/test_check_gwd30_tiffs.py`
  - discovery 改为按 yearly manifest 覆盖
  - 截断文件检测改为覆盖 `footprint` 快检路径

## Validation

- `python -m py_compile scripts/check_gwd30_tiffs.py tests/test_check_gwd30_tiffs.py`
- `ruff check scripts/check_gwd30_tiffs.py tests/test_check_gwd30_tiffs.py`
- `python -m pytest tests/`

## Next Step

默认快检：

```bash
python scripts/check_gwd30_tiffs.py --root /lustre/home/2200013429/Wetland_Assemble/data/GWD30 --quarantine-dir /lustre/home/2200013429/Wetland_Assemble/data/GWD30_corrupt
```

如需更强校验，可改成：

```bash
python scripts/check_gwd30_tiffs.py --root /lustre/home/2200013429/Wetland_Assemble/data/GWD30 --read-mode sampled
python scripts/check_gwd30_tiffs.py --root /lustre/home/2200013429/Wetland_Assemble/data/GWD30 --read-mode full
```
