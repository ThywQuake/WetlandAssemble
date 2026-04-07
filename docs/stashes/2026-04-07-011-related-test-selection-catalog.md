# 2026-04-07-011 Related Test Selection Catalog

## Summary

- 把现有测试按功能面整理成可复用的分类清单，不再把 `python -m pytest tests/` 当成每次改动的默认动作。
- 新增一个轻量工具：`python scripts/run_related_tests.py <changed-paths...>`，它会根据改动文件推导相关 pytest 子集。
- 这次整理不移动现有测试文件，只增加分类索引、路径映射和最小回归测试。

## Added

- `docs/testing/test-categories.md`
  - 记录测试家族、覆盖面、推荐命令和何时需要扩大测试范围。
- `src/WA/test_selection.py`
  - 保存测试分类目录和“改动路径 -> 相关测试”的映射规则。
- `scripts/run_related_tests.py`
  - 列出测试分类，或根据改动路径打印 / 直接运行相关测试。
- `tests/test_test_selection.py`
  - 覆盖 Phase 4、loaders、standardization、direct test path 等关键映射行为。

## Default Usage

列出分类：

```bash
python scripts/run_related_tests.py --list-categories
```

推导相关测试：

```bash
python scripts/run_related_tests.py src/WA/comparison/phase4_regional.py
```

直接运行相关测试：

```bash
python scripts/run_related_tests.py --run src/WA/comparison/phase4_regional.py
```

## Rule

- 默认只跑相关测试。
- 只有在以下情况才扩大：
  - 同时改了多个测试家族
  - 改到了共享基础设施（如 loaders/config/runtime）
  - 相关测试失败且看起来像跨模块回归
  - 用户明确要求更大范围

## Verification

- `ruff check src/WA/test_selection.py scripts/run_related_tests.py tests/test_test_selection.py`
- `python -m pytest tests/test_test_selection.py -q`

## Note

- 这是“测试选择规则”的整理，不是目录重构；现有测试文件路径保持不变。
- `.gsd/KNOWLEDGE.md` 已追加用户偏好：以后默认只跑相关测试，不再默认全量回归。
