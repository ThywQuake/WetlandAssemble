# 2026-04-07-005 M001 S02 T02 Late-Phase Matrix + Phase 4 Split

## Summary

- 已补完 `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` 的 late-phase rows：`Phase 3.6`、`Phase 3.6.1`、`Phase 3.7`、`Phase 4 current Stage-1 / Stage-2 route`、`Phase 4 historical full-tropics reducer route`。
- Phase 4 现在在 matrix 里明确拆成 **current route** 和 **historical/stale path** 两行，避免后续 slice 把 2026-04-05 的旧 full-tropics reducer 路线误当成当前入口。
- 当前判断规则：优先信任 2026-04-06 的 `CHANGELOG.md` + stash（`2026-04-06-003` / `005` / `008`），因此当前推荐链路是 Stage 1 native pixel-stats → Stage 2 regional integration。

## Key Files

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- `CHANGELOG.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`

## Evidence Anchors

Late Phase 3 anchors:
- `docs/stashes/2026-03-31-022-phase36-gwd30-tile-reduce-handoff.md`
- `docs/stashes/2026-04-01-011-phase361-gwd30-hotspot-trace-diagnostics.md`
- `docs/stashes/2026-04-01-002-phase37-global-500m-handoff.md`
- `docs/stashes/2026-04-01-004-phase37-hotspots-implementation.md`

Phase 4 chronology anchors:
- `CHANGELOG.md` (`2026-04-05`, `2026-04-06`)
- `docs/stashes/2026-04-06-003-phase4-conversation-summary.md`
- `docs/stashes/2026-04-06-005-phase4-stage2-pixel-stats-regional-integration.md`
- `docs/stashes/2026-04-06-008-phase4-recall-entry.md`

## Verification Commands

```bash
rg -n "Phase 3.6|Phase 3.6.1|Phase 3.7|Phase 4 current Stage-1 / Stage-2 route|Phase 4 historical full-tropics reducer route" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n "2026-03-31-022|2026-04-01-011|2026-04-01-002|2026-04-01-004|2026-04-06-003|2026-04-06-005|2026-04-06-008" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n "historical/stale path|implemented-but-unverified|HPC / external proof" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
```

## Open Risks

- `Phase 3.6` / `Phase 3.7` 的主要剩余缺口仍是 HPC-only proof，不是本地代码缺失。
- 当前 Phase 4 Stage 1 / Stage 2 路线已是 canonical continuation path，但仍缺真实 HPC rerun 证明。
- 旧 full-tropics reducer 路线仍在仓库和旧计划里出现；继续判断当前路线时不要把它重新合并回当前 Phase 4 状态。
