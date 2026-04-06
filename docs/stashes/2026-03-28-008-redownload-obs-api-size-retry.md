# 2026-03-28 008 redownload_obs_api size retry

## Context

在并行下载场景下，用户希望“准备开始下载下一个文件之前，立刻检查刚下载完的文件体积；如果不对就重下”。同时明确要求不要再做 TIFF 头检查，因为体积校验已经足够精确，且更快。

## What Changed

- Updated `scripts/redownload_obs_api.py`
  - 新增 `DownloadTask`，把 `expected_size_bytes` 带进下载阶段
  - worker 在 `download_file()` 里完成单个文件下载后，立刻执行体积校验
  - 若 `actual_size != expected_size_bytes`：
    - 删除刚下载的错误文件
    - 在当前任务内立即重试
    - 只有校验通过，这个 worker 才会回到线程池领取下一个任务
  - 不再做 TIFF 头检查
  - 对于旧 txt 输入，因为没有期望体积，只能退化为“文件存在且非零”
- Updated `tests/test_redownload_obs_api.py`
  - 覆盖 `DownloadTask` 结构
  - 覆盖 mismatch CSV 仍能正确构造任务
  - 覆盖“第一次下载体积错误，第二次重下成功”的重试路径

## Parallel Semantics

严格意义上的“上一个文件”在并行下载中并不存在全局顺序，因此实现采用 **per-worker immediate verification**：

- 某个 worker 下载完自己的当前文件
- 立刻按 manifest 体积校验
- 失败就本 worker 原地重下
- 通过后才会去接下一个任务

这比“全局串行等一个文件校验完再开始下一个”更适合线程池模型，也不会误让坏文件混进成功结果里。

## Validation

- `python -m py_compile scripts/redownload_obs_api.py tests/test_redownload_obs_api.py`
- `ruff check scripts/redownload_obs_api.py tests/test_redownload_obs_api.py`
- `python -m pytest tests/test_redownload_obs_api.py -q`
- `python -m pytest tests/ -q`
