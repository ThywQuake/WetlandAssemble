---
estimated_steps: 13
estimated_files: 8
skills_used: []
---

# T04: Reopen readiness and unified ledgers only after the authenticated outputs exist

Why: readiness and ledger are still the S07 acceptance gate, but they must now run only after the authenticated HPC rerun has produced real percentage/classification/trend outputs. This task turns the old downstream proof into an explicit fail-closed post-materialization gate.

## Execution Override
- Override `2026-04-09T03:32:26.852Z` has been applied and resolved in `.gsd/OVERRIDES.md`.
- Per D053 (superseding D052's temporary active-override note), this task is still driven in auto-mode for proof interpretation and any local repair loop, but the actual readiness/ledger rerun remains tied to the authenticated HPC repo once T03 has materialized the upstream families.
- Any `missing` / `partial` readiness result routes back to the T03 authenticated rerun path; do not hand-edit downstream artifacts or treat this container as a substitute execution environment.

Steps
1. In the authenticated HPC repo that now contains all three upstream families, run `scripts/run_phase4_scaleout_readiness.py` with `--subset ten`, canonical percentage/classification keys, and the same five trend dataset ids from T03.
2. Assert from the readiness JSON that `ready_region_ids` exactly equals `amazon, orinoco, pantanal, indogangetic, mekong, sudd, congo, okavango, borneo, northernaus`, `incomplete_region_ids` is empty, and every row status is `ready`; if not, stop and use the diagnostics to rerun only the missing upstream family/region via T03.
3. Run `scripts/run_phase4_hotspot_ledger.py --subset ten --no-skip` with the same keys/participant ids, verify representative first/last region ledgers on HPC, and then copy the readiness reports plus representative ledgers back into the repo.
4. Write `results/phase4/proof/phase4-readiness-ledger-proof.md` in bilingual form, recording the readiness report paths, representative ledger paths, any targeted reruns, and the exact S08 handoff after the authenticated sync-back.
5. If readiness or ledger exposes a real code bug, patch only the touched readiness/ledger files locally, rerun focused checks, resync, rerun readiness, then rerun ledger; do not hand-edit downstream artifacts.

Must-Haves
- [ ] The readiness CSV/JSON exists and every region/family row is `ready` on real ten-region outputs.
- [ ] `ready_region_ids` matches the ordered ten-region contract list exactly, with no `missing` or `partial` rows hidden by manual edits.
- [ ] Ten unified ledgers reopen from disk under `results/phase4/unified_hotspot_ledgers/`, and the copied proof note records the exact S08 handoff.

Done when
The authenticated rerun produces an all-green readiness report and reopened ten-region unified ledgers, and the repo proof bundle contains the copied readiness artifacts plus the bilingual ledger proof note.

## Inputs

- `results/phase4/proof/phase4-producer-materialization.md`
- `results/phase4/proof/phase4-trend-contract-submit.tsv`
- `results/phase4/proof/phase4-trend-fanout.md`
- `scripts/run_phase4_scaleout_readiness.py`
- `scripts/run_phase4_hotspot_ledger.py`
- `src/WA/comparison/scaleout_readiness.py`
- `src/WA/comparison/hotspot_ledger.py`

## Expected Output

- `results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.csv`
- `results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json`
- `results/phase4/unified_hotspot_ledgers/amazon/canonical__amazon__unified_hotspot_ledger.csv`
- `results/phase4/unified_hotspot_ledgers/northernaus/canonical__northernaus__unified_hotspot_ledger.csv`
- `results/phase4/proof/phase4-readiness-ledger-proof.md`

## Verification

# Run from an authenticated workstation / 需在已认证工作站执行
ssh 2200013429@wm2-data.pku.edu.cn <<'SH'
set -euo pipefail
cd /lustre/home/2200013429/repos/WA2
python scripts/run_phase4_scaleout_readiness.py \
  --subset ten \
  --output-root results/phase4 \
  --percentage-key canonical \
  --classification-key canonical \
  --trend-dataset-id gwd30 \
  --trend-dataset-id giems_mc \
  --trend-dataset-id topmodel \
  --trend-dataset-id swamps \
  --trend-dataset-id wad2m
python - <<'PY'
import json
from pathlib import Path
path = Path('results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json')
payload = json.loads(path.read_text())
expected = ['amazon', 'orinoco', 'pantanal', 'indogangetic', 'mekong', 'sudd', 'congo', 'okavango', 'borneo', 'northernaus']
assert payload['ready_region_ids'] == expected, payload['ready_region_ids']
assert payload['incomplete_region_ids'] == [], payload['incomplete_region_ids']
assert all(row['status'] == 'ready' for row in payload['rows']), 'non-ready row present'
PY
python scripts/run_phase4_hotspot_ledger.py \
  --subset ten \
  --output-root results/phase4 \
  --ledger-key canonical \
  --percentage-key canonical \
  --classification-key canonical \
  --trend-dataset-id gwd30 \
  --trend-dataset-id giems_mc \
  --trend-dataset-id topmodel \
  --trend-dataset-id swamps \
  --trend-dataset-id wad2m \
  --no-skip
test -f results/phase4/unified_hotspot_ledgers/amazon/canonical__amazon__unified_hotspot_ledger.csv
test -f results/phase4/unified_hotspot_ledgers/northernaus/canonical__northernaus__unified_hotspot_ledger.csv
SH
rsync -avz \
  2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/results/phase4/scaleout_readiness/ \
  results/phase4/scaleout_readiness/
rsync -avz \
  2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/results/phase4/unified_hotspot_ledgers/ \
  results/phase4/unified_hotspot_ledgers/
test -f results/phase4/unified_hotspot_ledgers/amazon/canonical__amazon__unified_hotspot_ledger.csv
test -f results/phase4/unified_hotspot_ledgers/northernaus/canonical__northernaus__unified_hotspot_ledger.csv

## Observability Impact

- Signals added/changed: readiness `ready/missing/partial` rows, `stage=scaleout-readiness` logs, and ledger `family-context` errors remain the main proof/debug surface.
- How a future agent inspects this: start from the readiness JSON/CSV under `results/phase4/scaleout_readiness/`, then the representative unified ledgers and `results/phase4/proof/phase4-readiness-ledger-proof.md`.
- Failure state exposed: incomplete regions stay visible by family, path, and reason; ledger failure should point back to the auto-written readiness diagnostics instead of requiring hand-reconstruction.

## Failure Modes

- **Dependencies**: `scripts/run_phase4_scaleout_readiness.py`, `scripts/run_phase4_hotspot_ledger.py`, `src/WA/comparison/scaleout_readiness.py`, `src/WA/comparison/hotspot_ledger.py`, and all upstream producer outputs from T02/T03.
- **On error**: rerun the missing upstream family first, then rerun readiness, then rerun ledger; if a code bug exists, patch only readiness/ledger surfaces and focused tests.
- **On timeout**: readiness should stay cheap; if ledger stalls, inspect family-context logs and representative region inputs rather than editing downstream CSVs.
- **On malformed response**: treat any `missing` / `partial` row, participant mismatch, or malformed contract metadata as a hard stop.

## Load Profile

- **Shared resources**: readiness CSV/JSON report, unified ledger CSVs, and the upstream hotspot family artifacts they reopen.
- **Per-operation cost**: one semantic reload per family × region plus one unified-ledger build per ready region.
- **10x breakpoint**: diagnostic clarity and artifact integrity fail before compute cost, so the proof note must preserve exact report paths and representative ledger outputs.

## Negative Tests

- **Malformed inputs**: missing or partial hotspot families, wrong participant-set key, malformed readiness JSON, or missing representative ledgers.
- **Error paths**: ledger must fail closed and point back to readiness diagnostics; the proof note must not claim success while any region remains incomplete.
- **Boundary conditions**: `ready_region_ids` must equal the ordered ten-region contract list exactly, and representative `amazon` / `northernaus` ledgers must exist after the all-green report.
