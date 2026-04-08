---
id: T01
parent: S05
milestone: M002
key_files:
  - src/WA/comparison/evidence_contract.py
  - scripts/run_phase4_regional.py
  - scripts/run_phase4_trend_contract.py
  - scripts/run_phase4_hotspot_ledger.py
  - tests/test_comparison/test_evidence_contract.py
  - tests/test_comparison/test_phase4_regional.py
  - CHANGELOG.md
  - .gsd/KNOWLEDGE.md
  - docs/stashes/2026-04-09-005-m002-s05-t01-ten-region-selector.md
key_decisions:
  - D043 — make EvidenceContract the single owner of the ordered `ten` subset, require explicit `--subset` vs `--region` selection on contract-aware CLIs, and keep `run_phase4_regional.py`'s no-arg macro+priority route as an explicit legacy path instead of silently redefining it.
duration: 
verification_result: mixed
completed_at: 2026-04-08T17:57:57.855Z
blocker_discovered: false
---

# T01: Added a shared ordered ten-region selector and explicit subset/logging plumbing across the Phase 4 regional, trend, and ledger CLIs.

**Added a shared ordered ten-region selector and explicit subset/logging plumbing across the Phase 4 regional, trend, and ledger CLIs.**

## What Happened

Added the shared ten-region selector at the evidence-contract layer, extending the contract to support `subset="ten"` in stable priority order while keeping `canonical` unchanged and rejecting duplicate ids plus ambiguous subset/region combinations. Wired `scripts/run_phase4_regional.py`, `scripts/run_phase4_trend_contract.py`, and `scripts/run_phase4_hotspot_ledger.py` to expose `--subset {canonical,ten}`, log `stage=region-selector ... region_ids=[...]` before fanout, and fail loudly on mixed selector input. For the regional runner, I explicitly preserved the old no-arg macro+priority route as `legacy-all-regions` instead of silently changing it to the contract ten-region path. Added focused regressions for ordering, selector validation, the regional legacy-vs-contract path, and the touched CLIs’ help/ambiguity surfaces, then wrote the stash summary plus knowledge/changelog breadcrumbs for downstream T02–T05 work.

## Verification

Passed the task-plan verification commands: targeted `ruff check`, `python scripts/run_phase4_regional.py --help`, `python scripts/run_phase4_trend_contract.py --help`, `python scripts/run_phase4_hotspot_ledger.py --help`, and `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_phase4_regional.py -q` (`36 passed`). Broader slice-level closeout checks were also run: shell syntax on the existing submit scripts passed and `run_related_tests.py` produced the expected recommendation, while the broader slice ruff/help/pytest commands still fail only because later S05 files/scripts/tests are intentionally not restored yet.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/comparison/evidence_contract.py scripts/run_phase4_regional.py scripts/run_phase4_trend_contract.py scripts/run_phase4_hotspot_ledger.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_phase4_regional.py` | 0 | ✅ pass | 39ms |
| 2 | `python scripts/run_phase4_regional.py --help` | 0 | ✅ pass | 1080ms |
| 3 | `python scripts/run_phase4_trend_contract.py --help` | 0 | ✅ pass | 1074ms |
| 4 | `python scripts/run_phase4_hotspot_ledger.py --help` | 0 | ✅ pass | 1048ms |
| 5 | `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_phase4_regional.py -q` | 0 | ✅ pass | 7684ms |
| 6 | `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_phase4_regional.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_comparison/test_classification_contract.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_hotspot_ledger.py tests/test_comparison/test_scaleout_readiness.py tests/test_visualization/test_phase4.py tests/test_plot_tropical_wetland_025deg.py tests/test_submit_phase4_gwd30_pixel_stats.py tests/test_submit_phase4_gwd30_regional_year_split.py tests/test_submit_phase4_gwd30_tropical_shards.py tests/test_submit_phase4_trend_contract.py -q` | 4 | ❌ fail | 166ms |
| 7 | `ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/phase4_regional.py src/WA/comparison/percentage_backbone.py src/WA/comparison/percentage_hotspots.py src/WA/comparison/classification_contract.py src/WA/comparison/trend_contract.py src/WA/comparison/trends.py src/WA/comparison/hotspot_ledger.py src/WA/comparison/scaleout_readiness.py scripts/plot_tropical_wetland_025deg.py scripts/run_phase4_percentage_contract.py scripts/run_phase4_classification_contract.py scripts/run_phase4_trend_contract.py scripts/run_phase4_hotspot_ledger.py scripts/run_phase4_scaleout_readiness.py src/WA/test_selection.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_phase4_regional.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_comparison/test_classification_contract.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_hotspot_ledger.py tests/test_comparison/test_scaleout_readiness.py tests/test_visualization/test_phase4.py tests/test_plot_tropical_wetland_025deg.py tests/test_submit_phase4_gwd30_pixel_stats.py tests/test_submit_phase4_gwd30_regional_year_split.py tests/test_submit_phase4_gwd30_tropical_shards.py tests/test_submit_phase4_trend_contract.py` | 1 | ❌ fail | 45ms |
| 8 | `bash -n scripts/submit_phase4_gwd30_pixel_stats.sh scripts/submit_phase4_gwd30_regional_year_split.sh scripts/submit_phase4_gwd30_tropical_shards.sh scripts/submit_phase4_trend_contract.sh` | 0 | ✅ pass | 1ms |
| 9 | `python scripts/run_phase4_percentage_contract.py --help && python scripts/run_phase4_classification_contract.py --help && python scripts/run_phase4_trend_contract.py --help && python scripts/run_phase4_hotspot_ledger.py --help && python scripts/run_phase4_scaleout_readiness.py --help` | 2 | ❌ fail | 9ms |
| 10 | `python scripts/run_related_tests.py src/WA/comparison/percentage_backbone.py src/WA/comparison/percentage_hotspots.py src/WA/comparison/classification_contract.py src/WA/comparison/trend_contract.py src/WA/comparison/trends.py src/WA/comparison/scaleout_readiness.py scripts/run_phase4_percentage_contract.py scripts/run_phase4_classification_contract.py scripts/run_phase4_trend_contract.py scripts/run_phase4_hotspot_ledger.py scripts/run_phase4_scaleout_readiness.py scripts/submit_phase4_trend_contract.sh src/WA/test_selection.py` | 0 | ✅ pass | 234ms |

## Deviations

Updated CHANGELOG.md and .gsd/KNOWLEDGE.md and recorded decision D043 because the project contract requires changelog maintenance for user-facing CLI changes and the selector/default split is a durable downstream rule. I also ran the broader slice-level verification commands at T01 closeout; their missing-file failures are expected for this first task in S05.

## Known Issues

Later S05 producer/readiness surfaces are still absent in this snapshot (`percentage_backbone.py`, `percentage_hotspots.py`, `classification_contract.py`, `trend_contract.py`, `scaleout_readiness.py`, related runner scripts, and their focused tests), so the broader slice-level ruff/help/pytest checks still fail on missing files and ten-region ledger reruns can still fail closed until T02–T05 land.

## Files Created/Modified

- `src/WA/comparison/evidence_contract.py`
- `scripts/run_phase4_regional.py`
- `scripts/run_phase4_trend_contract.py`
- `scripts/run_phase4_hotspot_ledger.py`
- `tests/test_comparison/test_evidence_contract.py`
- `tests/test_comparison/test_phase4_regional.py`
- `CHANGELOG.md`
- `.gsd/KNOWLEDGE.md`
- `docs/stashes/2026-04-09-005-m002-s05-t01-ten-region-selector.md`
