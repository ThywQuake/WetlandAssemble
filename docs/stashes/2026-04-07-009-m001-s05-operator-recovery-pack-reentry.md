# 2026-04-07 M001 S05 Operator Recovery Pack Reentry

## Summary / 摘要

- 先读 `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`。这是当前 recovery stack 的 **canonical first-stop recovery index**。
- 这份 note 只是一个 subordinate **breadcrumb**，不是新的 recovery pack，也不是新的 execution map。
- 如果问题是“当前哪条路线算真”，回到 `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`。
- 如果问题是“下一步具体复制什么执行步骤 / proof target / avoid-list”，回到 `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`。
- `R008` 现在闭合的是 compact recovery packaging，不是 fresh HPC rerun；HPC-only proof gap 仍然保持 open。

## Canonical Recovery Order / 规范恢复顺序

1. **S05 first** — `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`
   - 用它快速恢复方向、问题归属、source precedence。
2. **S03 route truth** — `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
   - 用它判断 current vs stale route。
3. **S02 proof boundary** — `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
   - 用它确认哪些只是 local evidence，哪些仍然需要 HPC proof。
4. **S04 execution truth** — `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
   - 真正开始执行时，只从这里复制 ordered continuation path。

## Do Not Promote This Note / 不要抬高这份 note 的权重

- 不要把这份 breadcrumb 变成第二份 operator pack。
- 不要把这份 breadcrumb 变成第二份 execution map。
- 不要从这里复制命令；真正执行时只回到 `S04-NEXT-STEP-EXECUTION-MAP.md`。
- 不要让后续 stash notes 与 S05 / S03 / S04 重新变成“平级 source of truth”。

## Fast Handoff / 快速交接

- 想快速恢复：先读 S05 pack。
- 想确认路线：跳到 S03。
- 想确认 proof boundary：跳到 S02。
- 想实际继续跑：跳到 S04，并以 `Ordered Continuation Path` 与 `Proof Targets / Exit Criteria` 为准。
