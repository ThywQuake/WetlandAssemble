# 2026-03-31 Phase 2.6 区域底图 400 自动降尺寸回退

## Summary

- 修复了 Phase 2.6 区域卫星底图下载时，部分大区域在 `getThumbURL`/JPG 下载阶段返回 `HTTP 400 Bad Request` 的问题。
- 现在当 quicklook 下载遇到 `HTTP 400` 时，会自动按更小尺寸重试，而不是直接失败。
- 当前回退链为：
  - `1536`
  - `1024`
  - `768`
  - `512`
  - `384`

## Files

- `src/WA/phase26_region_imagery.py`
- `tests/test_phase2_6_region_imagery.py`

## Behavior

- 默认仍优先使用用户请求的 `--dimensions`
- 如果该尺寸触发 `HTTP 400`
  - 自动降到更小尺寸继续尝试
  - 一旦成功，日志会记录实际使用的尺寸
- 如果所有候选尺寸都失败，仍返回原有失败状态并保留底层异常信息

## Verification

- `ruff check src/WA/phase26_region_imagery.py tests/test_phase2_6_region_imagery.py`
- `python -m pytest tests/test_phase2_6_region_imagery.py -q`
- `python -m pytest tests/`

结果：`337 passed`

## Notes

- 这次修复针对的典型场景是 `pantanal_upper_paraguay` 这类 bbox 较大的 region。
- 下载仍然保持原子写入；失败不会留下半截正式 JPG。
