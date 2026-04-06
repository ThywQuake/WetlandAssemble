# 2026-03-28 007 redownload_obs_api mismatch CSV support

## Context

`results/mismatches.csv` 已经由体积校验流程产出，下一步需要让 `scripts/redownload_obs_api.py` 直接读取这个 CSV 来决定哪些 GWD30 TIFF 需要重下，而不是只支持旧的纯文本路径列表。

## What Changed

- Updated `scripts/redownload_obs_api.py`
  - 继续兼容旧的 `corrupted_files_list.txt`
  - 新增对 `mismatches.csv` 的直接支持
  - CSV 模式下读取:
    - `absolute_path`
    - `relative_path`
    - `expected_size_bytes`
    - `status`
  - 只处理 `missing_file` / `size_mismatch` / `stat_failed`
  - 若本地文件已经恢复，且:
    - `st_size == expected_size_bytes`
    - 且 TIFF 头有效
    则自动跳过，不重复下载
  - 下载 object key 直接由 `relative_path` 还原，避免依赖手工整理 txt
- Added `tests/test_redownload_obs_api.py`
  - 覆盖 mismatch CSV 读取
  - 覆盖“已修复文件自动跳过”
  - 覆盖 `absolute_path` 缺失时退回 `relative_path`
  - 覆盖旧 txt 输入行为不变

## Validation

- `python -m py_compile scripts/redownload_obs_api.py tests/test_redownload_obs_api.py`
- `ruff check scripts/redownload_obs_api.py tests/test_redownload_obs_api.py`
- `python -m pytest tests/test_redownload_obs_api.py -q`
- `python -m pytest tests/ -q`

## Usage

直接用现有的 mismatch CSV：

```bash
python scripts/redownload_obs_api.py results/mismatches.csv --workers 16
```

旧文本格式仍然可用：

```bash
python scripts/redownload_obs_api.py corrupted_files_list.txt --workers 16
```
