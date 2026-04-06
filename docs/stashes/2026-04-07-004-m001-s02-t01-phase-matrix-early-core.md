# 2026-04-07-004 M001 S02 T01 Early/Core Phase Matrix

**Status:** 已创建规范化矩阵文件 `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`，并完成早期/核心 phase 行。

## 本次完成

- 新增 `Grading Contract`，明确四个 D002 等级：`validated`、`implemented-but-unverified`、`historical/stale path`、`unclear`
- 明确引用 `S01-INVENTORY.md` 与 `S01-DRIFT-BOUNDARIES.md` 作为冻结证据基线
- 明确规则：**更新的 changelog / terminal stash 证据优先于陈旧的 active plan 文本**
- 已填写以下 `Phase Matrix` 行：
  - `Phase 1`
  - `Phase 1.1`
  - `Phase 1.5`
  - `Phase 1.6`
  - `Phase 2`
  - `Phase 2.5`
  - `Phase 2.6`
  - `Phase 3`
  - `Phase 3.5`

## 当前等级快照

- `validated`：`Phase 1`、`Phase 2`、`Phase 2.6`、`Phase 3`
- `implemented-but-unverified`：`Phase 1.1`、`Phase 1.5`、`Phase 1.6`、`Phase 2.5`、`Phase 3.5`

## 解释口径

- `Local evidence` 只写当前 worktree 内可直接读取的代码 / 测试 / changelog / stash 证据
- `HPC / external proof` 单列写远端运行、Earth Engine、`results/`、`/lustre/...` 等外部证明面
- 缺少 fresh runtime/HPC 复核时，不上调到 `validated`

## 本次验证

```bash
test -s .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n "^## (Grading Contract|Phase Matrix)$" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n "Phase 1|Phase 1.1|Phase 1.5|Phase 1.6|Phase 2|Phase 2.5|Phase 2.6|Phase 3|Phase 3.5" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n "validated|implemented-but-unverified|historical/stale path|unclear|Local evidence|HPC / external proof|Why this grade" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
```

## 下一步

- T02 继续补齐 `Phase 3.6` 以后各行
- 特别要把 **Phase 4 current Stage-1 / Stage-2 route** 与 **historical full-tropics reducer route** 分开，不要合并成一个状态
- 如果要快速恢复上下文，优先读本 stash，然后跳回 canonical matrix
