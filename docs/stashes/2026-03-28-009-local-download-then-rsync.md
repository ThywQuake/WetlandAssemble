# 2026-03-28 009 Local Download Then Rsync

## Context

HPC 直连公网下载 GWD30 时，频繁出现截断文件和固定错误体积，说明瓶颈更像远端限流 / 共享出口 / 共享存储写入，而不是本地浏览器那种顺滑下载路径。为提升恢复效率，需要一个“本地下载一批 -> rsync 到 HPC -> 清空本地临时缓存 -> 继续下一批”的调度脚本。

## What Changed

- Added `scripts/download_gwd30_local_then_rsync.py`
  - 读取 `mismatches.csv` 或旧的 txt 输入
  - 本地按 `staging_root/year/file.tif` 下载
  - 支持批次阈值:
    - `--batch-files`
    - `--batch-size-gib`
  - 每个批次下载完成后执行 `rsync --remove-source-files`
  - rsync 后自动清理本地空目录
  - 启动时自动清理遗留 `*.part`
  - 若 staging 目录里已有完成文件，会先 rsync 掉再继续下载
  - 输出 `summary.json` / `failed_downloads.json` / `failed_downloads.txt`
- Added `tests/test_download_gwd30_local_then_rsync.py`
  - 覆盖 staging task 构造
  - 覆盖 batch 切分
  - 覆盖 rsync 命令构造
  - 覆盖 `_run()` 的分批下载与报告输出

## Validation

- `python -m py_compile scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `ruff check scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `python -m pytest tests/test_download_gwd30_local_then_rsync.py -q`
- `python -m pytest tests/ -q`

## Usage

示例:

```bash
python scripts/download_gwd30_local_then_rsync.py \
  results/mismatches.csv \
  --remote-dest 2200013429@wm2-data01:/lustre/home/2200013429/Wetland_Assemble/data/GWD30 \
  --staging-root temp/check_gwd30/local_rsync_buffer \
  --workers 6 \
  --batch-files 100 \
  --batch-size-gib 8 \
  --max-retries 6 \
  --download-timeout 300
```

这个模式是波次式的:

1. 本地先下满一个 batch
2. 把 batch rsync 到 HPC
3. 成功后本地自动清空该 batch
4. 再处理下一批

这样不会让本地下载和 rsync 同时争抢同一批文件，更稳。
