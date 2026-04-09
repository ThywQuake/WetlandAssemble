# S07 Replan

**Milestone:** M002
**Slice:** S07
**Blocker Task:** T02
**Created:** 2026-04-08T23:19:52.388Z

## Blocker Description

The auto-mode container cannot complete the OTP-protected sync-hpc/ssh flow to wm2-data, so real ten-region percentage/classification outputs were never materialized and downstream trend/readiness/ledger work cannot proceed against missing inputs.

## What Changed

Replaced the old trend-only downstream path with an explicit authenticated-HPC execution boundary. T03 now starts by resyncing from an authenticated workstation, reruns the missing ten-region percentage/classification producers, submits and monitors the ten-region trend wrapper, and copies proof artifacts back instead of assuming T02 already materialized the upstream families. T04 now runs readiness and unified ledger only after those real outputs exist, fails closed on any non-ready row, and records the exact sync-back/handoff proof for S08. Security posture and requirement coverage are unchanged; the plan change is an operational resequencing around OTP-gated HPC access.
