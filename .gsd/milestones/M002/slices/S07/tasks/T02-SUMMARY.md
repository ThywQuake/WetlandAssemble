---
id: T02
parent: S07
milestone: M002
key_files:
  - results/phase4/proof/phase4-producer-materialization.md
  - .gsd/KNOWLEDGE.md
  - docs/stashes/2026-04-09-021-m002-s07-t02-producer-materialization-blocked.md
  - .gsd/milestones/M002/slices/S07/tasks/T02-SUMMARY.md
key_decisions:
  - Preserved producer code unchanged because the observed failures were external HPC auth/input boundaries, not new semantic contract bugs.
duration: 
verification_result: mixed
completed_at: 2026-04-08T23:15:35.381Z
blocker_discovered: true
---

# T02: Documented the blocked T02 producer-materialization boundary, proved the percentage/classification fail-closed surfaces locally, and captured the exact authenticated HPC rerun commands.

**Documented the blocked T02 producer-materialization boundary, proved the percentage/classification fail-closed surfaces locally, and captured the exact authenticated HPC rerun commands.**

## What Happened

Reloaded the S07 T02 contract, the frozen T01 command ladder, the project `sync-hpc` route, and the live percentage/classification runners before touching anything. The local code surface still matches the plan: `--subset ten` is the wide selector, the percentage family still defaults to `dataset_key=canonical`, and the classification family still stays on `classification_key=canonical` over the fixed `g2017+glwd_v2+gwd30` participant set.

The intended next step was the HPC sync/materialization leg, but the actual `sync-hpc` route is a Mac-local wrapper around `rsync` to `2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/`. From this non-interactive auto-mode container, the host is reachable but both raw `ssh` and `rsync` stop at repeated `OTP Verification Fail!` messages and then `Permission denied (keyboard-interactive)`. Because there is no interactive terminal or `ssh-askpass` bridge here, the repo could not be synced and the real remote producer commands could not be run.

I then checked the exact T02 producer commands locally to distinguish an auth/input boundary from a producer-code bug. The percentage runner failed fail-closed on the missing HPC standardized Berkeley source with `FileNotFoundError: No standardized files were found for berkeley_rwawc` after visible `stage=region-selector` / `stage=dataset-selector` / `stage=percentage-contract` logs. The classification runner failed fail-closed during Phase 3.6 source loading with `FileNotFoundError: File does not exist: /lustre/home/2200013429/Wetland_Assemble/data/standardized/g2017.nc` after visible `stage=region-selector` / `stage=phase36` logs. The representative expected manifest paths for `amazon` and `northernaus` remain absent locally, so T02 did not materially produce the percentage/classification families.

Because the observed stop state was external auth/input availability rather than a new semantic contract bug, I did not patch producer code or hand-edit any outputs. Instead I wrote `results/phase4/proof/phase4-producer-materialization.md` in bilingual form with the exact blocked commands, failure shapes, representative expected outputs, and the authenticated rerun ladder; added a compact stash handoff at `docs/stashes/2026-04-09-021-m002-s07-t02-producer-materialization-blocked.md`; and appended one `.gsd/KNOWLEDGE.md` entry so future agents treat this as an auto-mode/HPC boundary instead of re-debugging the producer logic.

## Verification

Verified the remote execution boundary directly with timed `ssh` and `rsync` attempts against the project HPC target, confirmed the percentage/classification CLI help surfaces still expose the intended `--subset ten` / `--no-skip` contract, rechecked the ordered `ten` selector plus the key fail-closed producer behaviors through a direct Python verification script, and ran the exact T02 producer commands plus representative expected-file checks. The local direct producer/file checks failed as expected because the HPC standardized tree is not available in this container, and those failures are now recorded in the proof note rather than hidden.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts_wa -o ConnectTimeout=10 2200013429@wm2-data.pku.edu.cn 'hostname; pwd; whoami'` | 255 | ❌ fail | 5916ms |
| 2 | `rsync -avzn -e 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts_wa -o ConnectTimeout=10' --delete --exclude-from=.gitignore ./ 2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/` | 255 | ❌ fail | 5990ms |
| 3 | `python scripts/run_phase4_percentage_contract.py --help` | 0 | ✅ pass | 1265ms |
| 4 | `python scripts/run_phase4_classification_contract.py --help` | 0 | ✅ pass | 1236ms |
| 5 | `python - <<'PY'  # verify ordered ten subset + local fail-closed percentage/classification checks` | 0 | ✅ pass | 1465ms |
| 6 | `python scripts/run_phase4_percentage_contract.py --subset ten --output-root results/phase4 --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --surface-year 2016 --start-year 1990 --end-year 2020 --no-skip` | 1 | ❌ fail | 1252ms |
| 7 | `python scripts/run_phase4_classification_contract.py --subset ten --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --year 2016 --phase36-output-dir results/phase3.6 --phase36-cache-dir results/cache/phase3_6 --phase37-output-dir results/phase3.7_hotspots --phase37-cache-dir results/cache/phase3_7 --no-skip` | 1 | ❌ fail | 1208ms |
| 8 | `test -f results/phase4/hotspot_manifests/amazon/canonical__amazon__hotspot_manifest.json` | 1 | ❌ fail | 0ms |
| 9 | `test -f results/phase4/hotspot_manifests/northernaus/canonical__northernaus__hotspot_manifest.json` | 1 | ❌ fail | 0ms |
| 10 | `test -f results/phase4/classification_hotspot_manifests/amazon/canonical__amazon__classification_hotspot_manifest.json` | 1 | ❌ fail | 0ms |
| 11 | `test -f results/phase4/classification_hotspot_manifests/northernaus/canonical__northernaus__classification_hotspot_manifest.json` | 1 | ❌ fail | 0ms |

## Deviations

The task plan expected a real HPC rsync plus two remote materialization runs. In this auto-mode container, the `sync-hpc` route was blocked by OTP-only keyboard-interactive auth, so I could not perform the real remote execution. I therefore documented the stop state and exact rerun path instead of forcing a fake completion or broadening into unrelated code changes.

## Known Issues

Real ten-region percentage/classification outputs are still missing locally; T03 and T04 must not be treated as runnable proof work until the authenticated HPC rerun succeeds. This container also lacks one working pytest path for the scientific test surface (`python -m pytest` lacks `pytest`, while bare `pytest` / `uv run pytest` lack `numpy`), so verification used direct `python`-level checks for the fail-closed producer behaviors instead.

## Files Created/Modified

- `results/phase4/proof/phase4-producer-materialization.md`
- `.gsd/KNOWLEDGE.md`
- `docs/stashes/2026-04-09-021-m002-s07-t02-producer-materialization-blocked.md`
- `.gsd/milestones/M002/slices/S07/tasks/T02-SUMMARY.md`
