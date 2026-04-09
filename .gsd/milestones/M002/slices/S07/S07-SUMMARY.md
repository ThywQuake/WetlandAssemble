---
id: S07
parent: M002
milestone: M002
provides:
  - A frozen ten-region command ladder and dry-run proof bundle that preserve the exact selector, keys, participant ids, and `--no-skip` posture for future authenticated reruns.
  - A replayable bilingual proof bundle documenting the producer-materialization, trend-fanout, and readiness/ledger stop states plus the precise sync-back targets expected after HPC execution.
  - Focused wrapper/readiness/ledger regression surfaces that future agents can rerun locally before any authenticated resync.
  - A hard S08 handoff gate: do not attempt strict paper-pack proof until copied submit TSV, all-green readiness, and representative unified ledgers exist locally.
requires:
  - slice: S05
    provides: The ordered ten-region selector, canonical percentage/classification keys, the five-dataset trend participant set including `topmodel`, and the readiness/ledger contract surfaces that S07 verifies and freezes.
affects:
  - S08 strict paper-pack proof
  - M002 milestone validation/completion
  - Authenticated HPC operator workflow for ten-region reruns
key_files:
  - scripts/submit_phase4_trend_contract.sh
  - tests/test_submit_phase4_trend_contract.py
  - tests/test_comparison/test_scaleout_readiness.py
  - tests/test_comparison/test_hotspot_ledger.py
  - results/phase4/proof/phase4-ten-region-command-ladder.md
  - results/phase4/proof/phase4-trend-contract-dry-run.tsv
  - results/phase4/proof/phase4-producer-materialization.md
  - results/phase4/proof/phase4-trend-fanout.md
  - results/phase4/proof/phase4-readiness-ledger-proof.md
  - results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json
key_decisions:
  - D053 — Auto-mode owns local verification, proof bookkeeping, and focused fix/resync loops, but OTP-authenticated HPC materialization/readiness/ledger work remains a fail-closed external boundary until artifacts are synced back.
  - D054 — The trend submit wrapper must resolve regions during preflight with the explicit `--python-bin` / repo interpreter instead of bare `python3`.
  - Keep readiness and unified-ledger reopening fail-closed: local all-missing readiness reports and single-region ledger diagnostics are proof of blockage, not substitutes for synced-back ten-region completion proof.
patterns_established:
  - Freeze one bilingual command ladder and one copied dry-run TSV before any wide HPC rerun so later operators do not re-derive selectors, keys, or participant sets.
  - Treat OTP-authenticated HPC work as an explicit external boundary in auto-mode: record exact rerun commands, sync-back targets, and stop-state proof notes instead of fabricating remote success.
  - Use readiness before wide unified-ledger generation and treat ledger failure as a diagnostic producer that writes region-scoped readiness context.
  - Use `uv run --with pytest --python .venv/bin/python` for focused Phase 4 comparison verification when repo dependencies live in `.venv` but `pytest` does not.
observability_surfaces:
  - `results/phase4/proof/phase4-ten-region-command-ladder.md` plus `results/phase4/proof/phase4-trend-contract-dry-run.tsv` freeze the exact region order, key set, participant ids, skip mode, and submit-script fanout shape.
  - `results/phase4/proof/phase4-producer-materialization.md`, `phase4-trend-fanout.md`, and `phase4-readiness-ledger-proof.md` preserve the exact stop states, required sync-back targets, and authenticated rerun commands in bilingual form.
  - `results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.{csv,json}` deterministically records the current all-missing state rather than hiding incomplete families.
  - `scripts/run_phase4_hotspot_ledger.py` logs `stage=ledger action=family-context` and auto-writes a region-scoped readiness report when the ledger fails, so operators can recover from the exact blocking family/region.
drill_down_paths:
  - .gsd/milestones/M002/slices/S07/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S07/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S07/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S07/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-09T07:29:40.643Z
blocker_discovered: false
---

# S07: Ten-region HPC materialization and readiness/ledger proof

**S07 froze the ten-region Phase 4 execution ladder, hardened wrapper/readiness/ledger guardrails, and compressed the remaining producer/readiness/ledger proof into an explicit OTP-authenticated HPC rerun boundary instead of fabricating missing outputs.**

## What Happened

## Slice Outcome

S07 did **not** complete real ten-region Phase 4 materialization from this auto-mode container. What it actually closed was the full local proof surface around that boundary: it fixed the trend-submit preflight bug, froze the exact ten-region command ladder and participant keys, recorded the producer/trend/readiness/ledger stop states in replayable proof notes, and hardened the local fail-closed regression surface so future operators can resume from an authenticated workstation/HPC session without re-deriving selectors, keys, or proof targets.

### What actually shipped

- **T01 — wrapper preflight fix + frozen command ladder**
  - Narrowly fixed `scripts/submit_phase4_trend_contract.sh` so preflight region resolution uses the explicit `--python-bin` / repo interpreter instead of bare `python3`.
  - Added regression coverage in `tests/test_submit_phase4_trend_contract.py` and copied the real dry-run TSV to `results/phase4/proof/phase4-trend-contract-dry-run.tsv`.
  - Wrote `results/phase4/proof/phase4-ten-region-command-ladder.md` in bilingual form, freezing the ordered ten-region list, `canonical` percentage/classification keys, and the five-dataset trend participant set `giems_mc+gwd30+swamps+topmodel+wad2m`.
- **T02 — producer materialization boundary proof**
  - Confirmed the auto-mode container cannot execute the project `sync-hpc` route because SSH/rsync stop at the OTP keyboard-interactive challenge.
  - Re-ran the exact local percentage and classification producer commands and confirmed they fail closed on missing HPC standardized inputs instead of emitting partial artifacts.
  - Wrote `results/phase4/proof/phase4-producer-materialization.md` as the bilingual stop-state and rerun note, including the exact authenticated HPC commands and representative manifest targets.
- **T03 — trend fanout boundary + sync-back proof note**
  - Hardened wrapper regression coverage so the frozen dataset set still includes `topmodel`, `--subset ten` dry-runs account for all ten regions, and bad `--repo` / bad `--python-bin` / duplicate dataset ids fail before fanout.
  - Wrote `results/phase4/proof/phase4-trend-fanout.md` and explicitly refused to fabricate the missing copied submit TSV or any SLURM job ids.
  - Preserved the copied submit TSV and representative first/last manifests as explicit sync-back proof targets for the authenticated rerun.
- **T04 — readiness/ledger fail-closed gate**
  - Added focused readiness and ledger regressions proving that an all-ready synthetic subset-ten state preserves the ordered ten-region contract list and reopens representative `amazon` / `northernaus` ledgers when upstream families really exist.
  - Re-ran the exact local subset-ten readiness and ledger commands against the current repo state, confirmed readiness remains all-`missing`, and confirmed the ledger still fails closed at `amazon` while auto-writing the single-region readiness diagnostic.
  - Wrote `results/phase4/proof/phase4-readiness-ledger-proof.md` as the bilingual S07 stop-state note and explicit S08 handoff gate.

### What S07 now proves

- The live repo still resolves the same ordered ten-region selector and the same frozen contract keys/dataset set that downstream operators must reuse.
- The trend submit wrapper preflight now runs under the selected repo interpreter, so local dry-run and real submit no longer drift on dependency availability.
- The local repo can deterministically diagnose the blocked wide-run state: `results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json` currently shows `ready_region_ids=[]` and all ten regions incomplete, and `scripts/run_phase4_hotspot_ledger.py --subset ten --no-skip` fails closed with family-specific context instead of pretending to reopen partial ledgers.
- The repo still lacks real synced-back ten-region percentage/classification/trend artifacts, the copied `phase4-trend-contract-submit.tsv`, and any `results/phase4/unified_hotspot_ledgers/<region>/...` outputs. S07 therefore closes as an honest proof-boundary compression, **not** as a successful scientific acceptance of the original slice demo text.

## Operational Readiness (Q8)

- **Health signal:** after the authenticated rerun, health means the copied `phase4-trend-contract-submit.tsv` exists, the subset-ten readiness JSON reports `ready_region_ids == [amazon, orinoco, pantanal, indogangetic, mekong, sudd, congo, okavango, borneo, northernaus]`, `incomplete_region_ids == []`, every readiness row is `ready`, and representative `amazon` / `northernaus` unified ledgers reopen from disk.
- **Failure signal:** `ssh` / `rsync` stop at `OTP Verification Fail!`, readiness reports `ready_region_ids=[]` or any `missing` / `partial` row, the ledger logs `stage=ledger action=family-context`, or representative manifests / ledgers remain absent.
- **Recovery procedure:** from an authenticated workstation, `rsync` the repo to `/lustre/home/2200013429/repos/WA2/`, rerun the frozen percentage -> classification -> trend wrapper ladder with `--no-skip`, rerun subset-ten readiness, rerun the unified ledger, then sync back `results/phase4/proof/phase4-trend-contract-submit.tsv`, `results/phase4/scaleout_readiness/`, and `results/phase4/unified_hotspot_ledgers/`; do not hand-edit downstream artifacts.
- **Monitoring gaps:** there is still no automated signal for OTP/auth availability or sync-back completeness; operators must inspect the proof bundle, readiness JSON/CSV, wrapper summary TSV, and per-region job logs manually.

## Handoff to S08

S08 remains blocked until the authenticated HPC rerun produces and syncs back real ten-region outputs. The next slice must treat the following as its hard prerequisite, not as an optional nice-to-have:

1. copied `results/phase4/proof/phase4-trend-contract-submit.tsv` exists and accounts for all ten regions;
2. subset-ten readiness JSON is all-green in the exact contract order;
3. representative `amazon` / `northernaus` unified ledgers exist under `results/phase4/unified_hotspot_ledgers/`;
4. only then may `python scripts/run_phase4_evidence_pack.py --subset ten --strict ...` be used as a real complete-pack claim surface.


## Verification

Re-ran the local S07 closeout surface. Passing checks: `bash -n scripts/submit_phase4_trend_contract.sh`; all five Phase 4 CLI `--help` surfaces (`run_phase4_percentage_contract.py`, `run_phase4_classification_contract.py`, `run_phase4_trend_contract.py`, `run_phase4_scaleout_readiness.py`, `run_phase4_hotspot_ledger.py`); `uv run --with pytest --python .venv/bin/python python -m pytest tests/test_submit_phase4_trend_contract.py -q` (`7 passed`); `uv run --with ruff ruff check tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py`; `uv run --with pytest --python .venv/bin/python python -m pytest tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py -q` (`14 passed`); the real ten-region dry-run wrapper invocation, which resolved the exact ordered ten regions, preserved `topmodel`, showed `Skip mode: --no-skip`, and generated one submit script per region; and `test -s results/phase4/proof/phase4-trend-contract-dry-run.tsv`.

The live acceptance gate still fails on the current local artifact tree, and those failures were kept visible instead of hidden: `python scripts/run_phase4_scaleout_readiness.py --subset ten ...` writes a deterministic subset-ten readiness report but it remains all-`missing` with `ready_region_ids=[]`; the ordered all-green assertion fails with `AssertionError: []`; `python scripts/run_phase4_hotspot_ledger.py --subset ten ... --no-skip` fails closed at `amazon` with `stage=ledger action=family-context` diagnostics and writes the single-region readiness report; and representative `results/phase4/unified_hotspot_ledgers/amazon/...csv` and `.../northernaus/...csv` files are still absent. Those failing checks are the honest proof that the authenticated HPC rerun/sync-back boundary is still open.

## Requirements Advanced

- R107 — S07 reinforced the reproducible HPC-safe execution contract by freezing the exact rsync/producer/submit/readiness/ledger ladder, preserving fail-closed stop-state diagnostics, and refusing to claim container-only success when the authenticated external leg could not run.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The original slice demo promised real ten-region percentage/classification/trend materialization plus all-green readiness and reopened unified ledgers. In this auto-mode environment, the OTP-authenticated HPC leg could not be executed from the container, so S07 closes as a fail-closed boundary-compression and exact rerun handoff slice rather than as a true scientific completion of the original demo text.

## Known Limitations

Real ten-region percentage/classification/trend outputs are still absent locally; `results/phase4/proof/phase4-trend-contract-submit.tsv` is still missing; subset-ten readiness currently reports every region incomplete; and `results/phase4/unified_hotspot_ledgers/` does not yet exist locally. S08 strict paper-pack proof and M002 validation/completion remain blocked until an authenticated workstation/HPC session materializes and syncs back those artifacts.

## Follow-ups

1. From an authenticated workstation, rsync the repo to `/lustre/home/2200013429/repos/WA2/` and run the frozen percentage -> classification -> trend wrapper ladder with `--no-skip`.
2. Rerun subset-ten readiness and the unified ledger on HPC, confirm the exact ordered all-green readiness JSON plus representative `amazon` / `northernaus` ledgers, and sync back `results/phase4/proof/phase4-trend-contract-submit.tsv`, `results/phase4/scaleout_readiness/`, and `results/phase4/unified_hotspot_ledgers/`.
3. Only after those synced-back artifacts exist should S08 run `python scripts/run_phase4_evidence_pack.py --subset ten --strict ...`, repair the remaining evidence-audit gap, and rerun M002 validation.

## Files Created/Modified

- `scripts/submit_phase4_trend_contract.sh` — Preflight region resolution now uses the explicit repo interpreter during dry-run and real submit preparation.
- `tests/test_submit_phase4_trend_contract.py` — Added/fixed wrapper regressions covering repo-python delegation, ten-region accounting, default `topmodel`, and fail-closed bad-argument cases.
- `tests/test_comparison/test_scaleout_readiness.py` — Added subset-ten readiness regression coverage for the exact ordered ten-region list under the real five-dataset participant set.
- `tests/test_comparison/test_hotspot_ledger.py` — Added representative ten-region ledger reopen coverage for the all-ready synthetic upstream state.
- `results/phase4/proof/phase4-ten-region-command-ladder.md` — Frozen bilingual command ladder with exact region order, keys, participant ids, dry-run excerpt, and HPC rerun commands.
- `results/phase4/proof/phase4-producer-materialization.md` — Bilingual proof note capturing the blocked producer-materialization boundary and the exact authenticated rerun commands.
- `results/phase4/proof/phase4-trend-fanout.md` — Bilingual proof note capturing the authenticated trend-fanout boundary, sync-back targets, and retry/job-id bookkeeping rules.
- `results/phase4/proof/phase4-readiness-ledger-proof.md` — Bilingual stop-state proof note for the readiness/ledger acceptance gate and the explicit S08 handoff conditions.
- `results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json` — Deterministic subset-ten readiness diagnostic showing the current all-missing state on the local artifact tree.
