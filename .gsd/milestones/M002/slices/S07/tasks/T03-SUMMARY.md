---
id: T03
parent: S07
milestone: M002
key_files:
  - tests/test_submit_phase4_trend_contract.py
  - results/phase4/proof/phase4-trend-fanout.md
  - .gsd/KNOWLEDGE.md
  - docs/stashes/2026-04-09-025-m002-s07-t03-trend-fanout-boundary.md
key_decisions:
  - Kept T03 fail-closed by documenting the authenticated fanout boundary and sync-back requirements locally without fabricating the missing submit TSV or SLURM job ids.
duration: 
verification_result: mixed
completed_at: 2026-04-09T04:06:57.484Z
blocker_discovered: false
---

# T03: Pinned the trend-wrapper boundary checks and wrote the authenticated fanout sync-back proof note.

**Pinned the trend-wrapper boundary checks and wrote the authenticated fanout sync-back proof note.**

## What Happened

Reloaded the replanned T03 contract, the resolved S07 override, and the existing S07 proof bundle, then confirmed the repo still lacks synced-back ten-region percentage/classification/trend artifacts. A focused local test failure showed harness drift rather than a wrapper defect: the fake-repo wrapper tests were delegating to `sys.executable`, which in the standalone pytest toolchain lacked `yaml`, while the real trend-wrapper dry-run still succeeded with `$PWD/.venv/bin/python`. I fixed that harness narrowly in `tests/test_submit_phase4_trend_contract.py`, expanded the regression surface to pin default `topmodel`, ten-row submit accounting, one-region debug reruns, and fail-closed bad `--repo` / bad `--python-bin` / duplicate dataset ids, then wrote `results/phase4/proof/phase4-trend-fanout.md` as the bilingual authenticated-boundary and sync-back note. I also appended a `.gsd/KNOWLEDGE.md` entry for the repo-python test requirement and wrote a compact stash handoff in `docs/stashes/2026-04-09-025-m002-s07-t03-trend-fanout-boundary.md`.

## Verification

Verified wrapper shell syntax, the live Phase 4 percentage/classification/trend CLI help surfaces, the focused wrapper pytest subset under `uv run`, the real ten-region/five-dataset dry-run wrapper invocation, and the presence of the dry-run TSV plus new T03 proof/stash artifacts. Rechecked that raw SSH remains blocked by OTP keyboard-interactive auth from this container and that the real copied submit TSV is still absent locally, so the task result remains intentionally mixed rather than falsely green.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/submit_phase4_trend_contract.sh` | 0 | ✅ pass | 1ms |
| 2 | `python scripts/run_phase4_percentage_contract.py --help >/tmp/wa_t03_pct_help.txt` | 0 | ✅ pass | 1233ms |
| 3 | `python scripts/run_phase4_classification_contract.py --help >/tmp/wa_t03_cls_help.txt` | 0 | ✅ pass | 1235ms |
| 4 | `python scripts/run_phase4_trend_contract.py --help >/tmp/wa_t03_trend_help.txt` | 0 | ✅ pass | 1041ms |
| 5 | `uv run pytest tests/test_submit_phase4_trend_contract.py -q` | 0 | ✅ pass | 9482ms |
| 6 | `bash scripts/submit_phase4_trend_contract.sh --dry-run --repo "$PWD" --python-bin "$PWD/.venv/bin/python" --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --subset ten --dataset-id gwd30 --dataset-id giems_mc --dataset-id topmodel --dataset-id swamps --dataset-id wad2m --aggregation annual --start-year 1990 --end-year 2020 --min-observations 5 --min-overlap-years 5 --top-hotspots 10 --cpus 2 --time 480 --partition C064M0256G --jobs-base temp/slurm-jobs-s07 --tmp-root temp/slurm-tmp-s07 --no-progress >/tmp/wa_t03_dry_run.txt` | 0 | ✅ pass | 2069ms |
| 7 | `test -s results/phase4/proof/phase4-trend-contract-dry-run.tsv && test -f results/phase4/proof/phase4-trend-fanout.md && test -f docs/stashes/2026-04-09-025-m002-s07-t03-trend-fanout-boundary.md` | 0 | ✅ pass | 0ms |
| 8 | `ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts_wa_t03 -o ConnectTimeout=10 2200013429@wm2-data.pku.edu.cn 'hostname'` | 255 | ❌ fail | 6777ms |
| 9 | `test -s results/phase4/proof/phase4-trend-contract-submit.tsv` | 1 | ❌ fail | 0ms |

## Deviations

The written task plan expects a real authenticated workstation/HPC rsync, producer rerun, trend submit, and sync-back. Per the resolved override and the still-failing OTP boundary, I stopped at local proof bookkeeping plus focused wrapper-test hardening instead of pretending the remote run was container-executable or fabricating a copied submit TSV.

## Known Issues

The real authenticated HPC run is still outstanding, so T04 remains blocked on genuine synced-back percentage/classification/trend artifacts. Also, `.venv/bin/python` still lacks a local `pytest` module in this snapshot, so the focused related-test verification ran through `uv run pytest` while the runtime CLIs continued to use the repo venv interpreter.

## Files Created/Modified

- `tests/test_submit_phase4_trend_contract.py`
- `results/phase4/proof/phase4-trend-fanout.md`
- `.gsd/KNOWLEDGE.md`
- `docs/stashes/2026-04-09-025-m002-s07-t03-trend-fanout-boundary.md`
