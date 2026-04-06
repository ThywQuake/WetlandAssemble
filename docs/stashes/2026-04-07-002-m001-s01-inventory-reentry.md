# 2026-04-07-002 M001 S01 Inventory Reentry

## Summary

- 本轮 S01 的 canonical 本地证据入口是 `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md`。
- drift / stale / proof-boundary 的解释层单独放在 `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`。
- 如果只是快速恢复上下文，不要重新盲目扫仓库；先读这两个文件，再回到最新 Phase 4 stash 与 `CHANGELOG.md`。

## Read Order / 建议阅读顺序

1. `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
2. `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`
3. `docs/stashes/2026-04-06-008-phase4-recall-entry.md`
4. `docs/stashes/2026-04-06-003-phase4-conversation-summary.md`
5. `CHANGELOG.md`（重点看 `2026-04-05` 与 `2026-04-06`）

## Outputs / 产物位置

- Inventory freeze: `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
- Drift appendix: `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`
- T01 freeze note: `docs/stashes/2026-04-07-001-m001-s01-t01-inventory-freeze.md`
- T02 re-entry note: `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md`

## Verification Snapshot

| Check | Command | Result |
|---|---|---|
| T01 inventory exists | `test -s .gsd/milestones/M001/slices/S01/S01-INVENTORY.md` | ✅ pass |
| T01 headings intact | `rg -n "^## (Runtime Code Surface|Operational Script Surface|Verification Surface|Planning and History Surface|Dataset, TODO, and Config Surface|Git and Worktree State|Artifact Presence and Proof Boundaries|Command Appendix)$" .gsd/milestones/M001/slices/S01/S01-INVENTORY.md` | ✅ pass |
| T01 command anchors intact | `rg -n "python -m pytest --collect-only -q|git status --short --branch|results/|temp/" .gsd/milestones/M001/slices/S01/S01-INVENTORY.md` | ✅ pass |
| T02 files exist | `test -s .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md && test -s docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md` | ✅ pass |
| T02 headings intact | `rg -n "^## (Current Signals|Historical / Superseded Signals|Proof Boundaries|Handoff to S02 and S03)$" .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` | ✅ pass |
| Inventory cross-link present | `rg -n "S01-DRIFT-BOUNDARIES.md" .gsd/milestones/M001/slices/S01/S01-INVENTORY.md` | ✅ pass |
| Re-entry note anchors present | `rg -n "S01-INVENTORY.md|S01-DRIFT-BOUNDARIES.md|Open Risks|Verification Snapshot" docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md` | ✅ pass |

## Open Risks

- `results/`、`temp/`、以及 `../../.claude/projects/-Users-mac-Code-WA/memory` 在当前 GSD worktree 都是 `absent-local`；这里能记录的是 proof boundary，不是“这些东西从未存在”。
- `config/datasets.yaml` 指向的 `/lustre/...` 路径属于 `external/HPC-only`；任何关于 staged cache、pixel stats、regional outputs 的存在性都需要在 HPC 上单独核实。
- `docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md` 仍然是高信号计划文件，但 2026-04-06 的 changelog + stash 已经把其中一部分“如何走”更新成了更近的实现事实；做 route judgment 时要优先后者。

## Replay / 继续工作时先做什么

- 本地证据刷新：直接复用 `S01-INVENTORY.md` 里的 `Command Appendix`，不要重新发明盘点命令。
- 当前路线判断：先用 `S01-DRIFT-BOUNDARIES.md` 过滤 `current-signal`、`historical`、`superseded`。
- 如果进入 HPC 执行，优先参考 `docs/stashes/2026-04-06-008-phase4-recall-entry.md` 里的 Stage 1 / Stage 2 命令，而不是回到旧的 full-tropics reducer 路线。

## Current HPC Commands (from latest recall note)

Stage 1 builder:

```bash
python scripts/build_phase4_gwd30_pixel_stats.py --year 2020 --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --aggregation monthly --worker-count 1 --no-skip
```

Stage 2 regional run:

```bash
python scripts/run_phase4_regional.py --dataset-id gwd30 --region amazon --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --start-year 2013 --end-year 2022 --no-skip
```
