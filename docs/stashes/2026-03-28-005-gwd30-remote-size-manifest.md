# 2026-03-28 005 GWD30 Remote Size Manifest

## Context

需要直接从 `data-starcloud.pcl.ac.cn` 的 GWD30 文件列表接口拉取官方 `TIFF -> size` 清单，先把远端基准 manifest 固化到当前环境，后续再单独做本地完整性校验。

## What Changed

- Added `scripts/fetch_gwd30_remote_sizes.py`
  - 按年调用 `/aiforearth/api/data/getFileListByPage`
  - 自动分页抓取 `2013-2022`
  - 输出 `gwd30_remote_sizes.csv` / `gwd30_remote_sizes.json` / `summary.json`
  - 请求层优先走 `curl`，因为站点会拦截 `urllib` 直连
- Added `tests/test_fetch_gwd30_remote_sizes.py`
  - 覆盖 curl 请求构造
  - 覆盖分页聚合
  - 覆盖 manifest 落盘
  - 覆盖 `_run()` 端到端输出

## Live Result

- 实际抓取时间: `2026-03-28T10:15:59Z`
- 输出目录: `temp/check_gwd30/remote_sizes`
- 总文件数: `184336`
- 总体积字节数: `7821755777043`

按年条目数:

- `2013`: `18448`
- `2014`: `18449`
- `2015`: `18443`
- `2016`: `18444`
- `2017`: `18441`
- `2018`: `18444`
- `2019`: `18447`
- `2020`: `18449`
- `2021`: `18394`
- `2022`: `18377`

## API Constraint

`2026-03-28` 实测接口对 `count` 的限制是 `1..1000`。当 `count=20000` 或更大时，接口返回:

```json
{"code":403,"error":"count must be between 1 and 1000","success":false}
```

因此脚本默认值已收敛到 `1000`。

## Validation

- `python -m py_compile scripts/fetch_gwd30_remote_sizes.py tests/test_fetch_gwd30_remote_sizes.py`
- `ruff check scripts/fetch_gwd30_remote_sizes.py tests/test_fetch_gwd30_remote_sizes.py`
- `python -m pytest tests/test_fetch_gwd30_remote_sizes.py -q`
- `python scripts/fetch_gwd30_remote_sizes.py --count 1000 --output-dir temp/check_gwd30/remote_sizes`
