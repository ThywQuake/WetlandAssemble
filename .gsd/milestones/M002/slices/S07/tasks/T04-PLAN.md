---
estimated_steps: 12
estimated_files: 7
skills_used:
  - hpc-analyze
  - sync-hpc
---

# T04: Prove all-green readiness and rebuild the ten unified hotspot ledgers

Why: readiness plus unified-ledger reopen is the actual S07 acceptance boundary, not file counting or one-region smoke output.

## Steps
1. Run `scripts/run_phase4_scaleout_readiness.py` with `--subset ten`, canonical percentage/classification keys, and the same five trend dataset ids used in T03; inspect the CSV/JSON first and rerun upstream producer families if any row is `missing` or `partial`.
2. Assert from the JSON payload that `ready_region_ids` exactly equals the ordered ten-region contract list, then capture the report paths and any rerun notes in `results/phase4/proof/phase4-readiness-ledger-proof.md`.
3. Run `scripts/run_phase4_hotspot_ledger.py --subset ten --no-skip` with the same keys/participant ids, then verify representative first/last region ledgers reopen cleanly from disk.
4. If readiness or ledger exposes a real code bug, patch only the touched readiness/ledger files and focused tests locally, resync, rerun readiness, then rerun ledger; do not hand-edit downstream artifacts.

## Must-Haves
- [ ] The readiness CSV/JSON exists and every region/family row is `ready`.
- [ ] Ten `canonical__<region>__unified_hotspot_ledger.csv` files exist under `results/phase4/unified_hotspot_ledgers/`.
- [ ] The proof note records the report paths, representative ledger paths, and the exact remaining handoff to S08 strict pack proof.

## Done when
The ten-region readiness report is all-green and the unified ledgers reopen without family-context errors, making S07's producer -> readiness -> ledger ladder operationally true.

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
