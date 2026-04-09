---
id: T04
parent: S07
milestone: M002
key_files:
  - tests/test_comparison/test_scaleout_readiness.py
  - tests/test_comparison/test_hotspot_ledger.py
  - results/phase4/proof/phase4-readiness-ledger-proof.md
  - .gsd/KNOWLEDGE.md
  - docs/stashes/2026-04-09-026-m002-s07-t04-readiness-ledger-gate.md
  - results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json
key_decisions:
  - Preserved T04 as a fail-closed gate: the local all-missing subset-ten readiness report and the single-region ledger diagnostic are proof of blockage, not substitutes for authenticated S07 completion proof.
  - Used `uv run --with pytest --python .venv/bin/python python -m pytest ...` for verification because the repo venv has the scientific stack but not `pytest`, while the standalone `pytest` tool runs under Python 3.14 and cannot import the repo's Python 3.13 wheels.
duration: 
verification_result: mixed
completed_at: 2026-04-09T04:26:54.959Z
blocker_discovered: false
---

# T04: Pinned the T04 fail-closed gate with exact ten-region readiness/ledger regressions and a stop-state proof note showing authenticated outputs are still missing.

**Pinned the T04 fail-closed gate with exact ten-region readiness/ledger regressions and a stop-state proof note showing authenticated outputs are still missing.**

## What Happened

Reloaded the T04 contract, the resolved S07 override, the earlier T02/T03 proof notes, and the current `results/phase4` tree before changing anything. The live repo state still lacks synced-back ten-region percentage/classification/trend outputs, `phase4-trend-contract-submit.tsv`, and reopened unified ledgers. I kept the task fail-closed and improved only the local T04 guardrails: `tests/test_comparison/test_scaleout_readiness.py` now proves an all-green synthetic subset-ten report preserves the exact ordered ten-region list under the real five-dataset participant-set key, and `tests/test_comparison/test_hotspot_ledger.py` now proves representative `amazon` / `northernaus` ledgers reopen under a synthetic subset-ten all-ready input set. I also recorded the split pytest/dependency verification recipe plus the “local readiness diagnostics are not synced-back proof” rule in `.gsd/KNOWLEDGE.md`.

After that hardening, I ran the exact T04 local boundary checks against the real repo state. Direct SSH still failed on OTP / keyboard-interactive auth. The exact subset-ten readiness command wrote `results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.{csv,json}`, but the report remained all-`missing` with `ready_region_ids=[]` and all ten contract regions still incomplete. The exact ordered all-green assertion failed with `AssertionError: []`. The exact ledger command failed closed immediately at `amazon`, emitted `stage=ledger action=family-context` diagnostics for missing percentage/classification/trend families, and pointed back to the auto-written single-region readiness diagnostic `regions-amazon__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.{csv,json}`.

Finally, I wrote `results/phase4/proof/phase4-readiness-ledger-proof.md` in bilingual form as the T04 stop-state proof note, including the current readiness JSON state, the fail-closed ledger diagnostics, the representative absent ledger paths, the exact authenticated rerun commands, and the explicit S08 handoff gate. I also wrote the compact stash handoff at `docs/stashes/2026-04-09-026-m002-s07-t04-readiness-ledger-gate.md`.

## Verification

Focused local verification passed on the touched readiness/ledger test surface with ruff plus pytest under `uv run --with pytest --python .venv/bin/python`. The exact local subset-ten readiness command succeeded in writing the deterministic report but showed every region/family still `missing`. The exact ordered all-green assertion failed, the exact subset-ten ledger command failed closed on the missing `amazon` percentage manifest while logging `stage=ledger action=family-context`, and representative `amazon` / `northernaus` ledgers remained absent. A repo-wide pytest attempt was also launched under the same temporary 3.13 runner, but it exited 137 after progressing through the collected suite, so the passing focused related subset remains the completed verification surface for this task snapshot.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --with ruff ruff check tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py` | 0 | ✅ pass | 152ms |
| 2 | `uv run --with pytest --python .venv/bin/python python -m pytest tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py -q` | 0 | ✅ pass | 9422ms |
| 3 | `ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts_wa_t04 -o ConnectTimeout=10 2200013429@wm2-data.pku.edu.cn 'hostname'` | 255 | ❌ fail | 6620ms |
| 4 | `python scripts/run_phase4_scaleout_readiness.py --subset ten --output-root results/phase4 --percentage-key canonical --classification-key canonical --trend-dataset-id gwd30 --trend-dataset-id giems_mc --trend-dataset-id topmodel --trend-dataset-id swamps --trend-dataset-id wad2m` | 0 | ✅ pass | 1355ms |
| 5 | `python -c "import json; from pathlib import Path; path = Path('results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json'); payload = json.loads(path.read_text()); expected = ['amazon', 'orinoco', 'pantanal', 'indogangetic', 'mekong', 'sudd', 'congo', 'okavango', 'borneo', 'northernaus']; assert payload['ready_region_ids'] == expected, payload['ready_region_ids']; assert payload['incomplete_region_ids'] == [], payload['incomplete_region_ids']; assert all(row['status'] == 'ready' for row in payload['rows']), 'non-ready row present'"` | 1 | ❌ fail | 25ms |
| 6 | `python scripts/run_phase4_hotspot_ledger.py --subset ten --output-root results/phase4 --ledger-key canonical --percentage-key canonical --classification-key canonical --trend-dataset-id gwd30 --trend-dataset-id giems_mc --trend-dataset-id topmodel --trend-dataset-id swamps --trend-dataset-id wad2m --no-skip` | 1 | ❌ fail | 1231ms |
| 7 | `test -f results/phase4/unified_hotspot_ledgers/amazon/canonical__amazon__unified_hotspot_ledger.csv` | 1 | ❌ fail | 1ms |
| 8 | `test -f results/phase4/unified_hotspot_ledgers/northernaus/canonical__northernaus__unified_hotspot_ledger.csv` | 1 | ❌ fail | 1ms |
| 9 | `uv run --with pytest --python .venv/bin/python python -m pytest tests/` | 137 | ❌ fail | 111200ms |

## Deviations

Added local regression hardening in the touched readiness/ledger test files before writing the stop-state proof note; otherwise stayed within the planned fail-closed authenticated-HPC boundary.

## Known Issues

Real authenticated percentage/classification/trend outputs are still absent locally, so T04 cannot satisfy the slice acceptance gate from this container alone. The repo-wide pytest attempt under the temporary 3.13 runner also exited 137 after progressing through the collected suite, so only the focused related subset is a completed passing verification surface in this task snapshot.

## Files Created/Modified

- `tests/test_comparison/test_scaleout_readiness.py`
- `tests/test_comparison/test_hotspot_ledger.py`
- `results/phase4/proof/phase4-readiness-ledger-proof.md`
- `.gsd/KNOWLEDGE.md`
- `docs/stashes/2026-04-09-026-m002-s07-t04-readiness-ledger-gate.md`
- `results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json`
