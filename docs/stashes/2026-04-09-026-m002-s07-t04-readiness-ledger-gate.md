# 2026-04-09 M002/S07/T04 readiness + ledger gate quick reference

## What changed
- Added `tests/test_comparison/test_scaleout_readiness.py` coverage that proves an all-green synthetic `--subset ten` report preserves the exact ordered ten-region contract list under the real five-dataset trend participant-set key.
- Added `tests/test_comparison/test_hotspot_ledger.py` coverage that proves `scripts/run_phase4_hotspot_ledger.py --subset ten --no-skip` reopens representative `amazon` / `northernaus` ledgers when all upstream families are actually present.
- Wrote `results/phase4/proof/phase4-readiness-ledger-proof.md` as the bilingual T04 stop-state proof note.
- Appended `.gsd/KNOWLEDGE.md` entries for the split pytest/dependency env recipe and the rule that local T04 readiness diagnostics do **not** count as synced-back ten-region proof.

## What the real repo state still says
- `results/phase4/proof/phase4-trend-contract-submit.tsv` is still absent locally.
- The exact local subset-ten readiness run now writes `results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.{csv,json}`, but that report is all-`missing` with `ready_region_ids=[]` and all ten regions still incomplete.
- The exact local ledger rerun still fails closed at `amazon` and points back to `regions-amazon__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.{csv,json}`.
- Representative ledgers are still absent locally:
  - `results/phase4/unified_hotspot_ledgers/amazon/canonical__amazon__unified_hotspot_ledger.csv`
  - `results/phase4/unified_hotspot_ledgers/northernaus/canonical__northernaus__unified_hotspot_ledger.csv`

## Verification status
- `uv run --with ruff ruff check tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py` ✅
- `uv run --with pytest --python .venv/bin/python python -m pytest tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py -q` ✅ (14 passed)
- `ssh ... 2200013429@wm2-data.pku.edu.cn 'hostname'` ❌ still blocked by OTP / keyboard-interactive auth
- `python scripts/run_phase4_scaleout_readiness.py --subset ten ...` ✅ writes the deterministic subset-ten report, but the report is still all-`missing`
- `python -c '...assert payload["ready_region_ids"] == expected...'` ❌ fails with `AssertionError: []`
- `python scripts/run_phase4_hotspot_ledger.py --subset ten ... --no-skip` ❌ fails closed on the missing `amazon` percentage manifest and logs `stage=ledger action=family-context`
- `uv run --with pytest --python .venv/bin/python python -m pytest tests/` ❌ attempted for repo-wide verification but exited 137 after progressing through 520 collected tests; treat the focused related subset above as the passing verification surface for this task

## Open risks / TODOs
1. A real authenticated workstation/HPC session still must run the frozen readiness + ledger ladder after T03 materializes and syncs back all upstream families.
2. Do **not** treat the local all-`missing` subset-ten readiness JSON or the single-region `regions-amazon__...` diagnostic as S07 acceptance proof.
3. S08 strict paper-pack proof remains blocked until synced-back readiness is all-green and representative `amazon` / `northernaus` ledgers exist on disk.

## Exact next HPC commands
```bash
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
```

## Chinese recap / 中文回顾
- 本地已经把 T04 的合同护栏补强：新增了十区 readiness 顺序测试与 representative ledger 复开测试。
- 但真实仓库状态仍然没有通过 T04：subset-ten readiness 报告是全 `missing`，ledger 在 `amazon` 就 fail-closed，OTP 边界也仍然阻止容器直接登录 HPC。
- 因此 `results/phase4/proof/phase4-readiness-ledger-proof.md` 现在是一份**停机状态证明**，不是成功证明；S08 也还不能启动。
