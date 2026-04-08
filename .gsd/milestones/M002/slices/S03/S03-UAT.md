# S03: Classification-disagreement backbone on the shared contract — UAT

**Milestone:** M002
**Written:** 2026-04-08T14:43:25.320Z

# S03 UAT — Classification-disagreement backbone on the shared contract

## Preconditions

1. Run from the repository root / GSD worktree with project dependencies installed.
2. Local UAT uses synthetic fixtures embedded in the test suite; no HPC data is required for the local checks.
3. For the optional HPC smoke at the end, standardized inputs must already be available on the cluster under `/lustre/home/2200013429/Wetland_Assemble/data/standardized`.

---

## UAT-1 — Shared contract recognizes classification artifact families and protects the stem grammar

### Steps

1. Run:
   ```bash
   ruff check src/WA/comparison/evidence_contract.py tests/test_comparison/test_evidence_contract.py
   ```
2. Run:
   ```bash
   python -m pytest tests/test_comparison/test_evidence_contract.py -q
   ```

### Expected outcomes

- Ruff passes.
- Pytest reports `12 passed`.
- Classification artifact kinds now exist in the shared contract.
- The contract emits classification relpaths using the participant-set key in the dataset slot.
- The outer filename grammar stays `<dataset_or_key>__<region>__<suffix>`.

### Edge cases covered by this UAT

- Unknown classification artifact kinds are rejected.
- Dataset / participant tokens containing `__` are rejected before relpaths are emitted.
- Missing classification artifact semantics fail contract construction instead of silently omitting a family.

---

## UAT-2 — Phase 3.6 / Phase 3.7 sources can be rewritten into contract-scoped classification artifacts

### Steps

1. Run:
   ```bash
   ruff check src/WA/comparison/classification_contract.py tests/test_comparison/test_classification_contract.py
   ```
2. Run:
   ```bash
   python -m pytest tests/test_comparison/test_classification_contract.py -q
   ```

### Expected outcomes

- Ruff passes.
- Pytest reports `8 passed`.
- Synthetic Phase 3.6 metrics + dominant datasets produce a region-scoped classification surface `.nc` and regional summary `.csv` under contract-stable relpaths.
- Synthetic Phase 3.7 manifest / hotspot CSV / region CSV sources rewrite into a region-scoped hotspot manifest `.json` plus companion `.csv`.
- Summary output contains `participant_set_key`, source paths, and contract metadata.
- Hotspot output preserves quota / selected-count / shortfall / threshold fields.

### Edge cases covered by this UAT

- Missing `*_source_dominant_class` variables fail before any output files are left behind.
- Zero joint-valid cells fail summary generation explicitly.
- Missing Phase 3.6 source files fail explicitly.
- Malformed hotspot bbox JSON fails before writing a contract hotspot pair.
- Unknown region ids fail instead of silently skipping.

---

## UAT-3 — The canonical runner and semantic reload helpers are wired end to end

### Steps

1. Run:
   ```bash
   ruff check scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py tests/test_visualization/test_phase4.py src/WA/test_selection.py docs/testing/test-categories.md CHANGELOG.md
   ```
2. Run:
   ```bash
   python scripts/run_phase4_classification_contract.py --help
   ```
3. Run:
   ```bash
   python -m pytest tests/test_visualization/test_phase4.py -q
   ```

### Expected outcomes

- Ruff passes.
- `--help` succeeds and shows the narrow-first classification HPC ladder plus the key flags (`--region`, `--subset`, `--output-root`, `--year`, `--skip/--no-skip`, `--progress/--no-progress`).
- Pytest reports `18 passed`.
- Classification summaries and hotspot tables can be reopened by contract semantics through `src/WA/visualization/phase4.py`.
- The runner rejects invalid selection inputs before trying to execute heavy work.

### Edge cases covered by this UAT

- Summary reload fails with `missing_surface_path` when the paired surface is absent.
- Malformed `contract_metadata_json` fails explicitly.
- Hotspot reload rejects participant-set mismatch.
- Hotspot reload rejects region mismatch.
- The runner rejects `--subset canonical --region amazon`.
- The runner rejects unknown region ids.

---

## UAT-4 — Phase 4 related-test routing and repository-wide regression still recognize the classification path

### Steps

1. Run:
   ```bash
   python scripts/run_related_tests.py src/WA/comparison/classification_contract.py scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py
   ```
2. Run:
   ```bash
   python -m pytest tests/
   ```

### Expected outcomes

- `run_related_tests.py` reports the `phase4` category and suggests a pytest subset that includes `tests/test_comparison/test_classification_contract.py` and `tests/test_visualization/test_phase4.py`.
- Full pytest passes with `476 passed`.
- Warning noise may still appear, but there should be no failing tests.

### Edge cases covered by this UAT

- The changed-path routing should not omit the classification contract adapter or runner once those paths are passed in.
- Repository-wide regression confirms the new classification contract path did not break unrelated Phase 2/3/4 families.

---

## Optional HPC smoke — real-data proof ladder for the newly closed S03 route

### Preconditions

- Standardized data available on HPC.
- `results/phase3.6` and `results/phase4` writable.
- Use `--no-skip` so rebuild behavior stays visible.

### Steps

1. Rebuild or refresh the global Phase 3.6 backbone:
   ```bash
   python scripts/run_phase3_6_global_entropy.py \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-dir results/phase3.6 \
     --cache-dir results/cache/phase3_6 \
     --year 2016 \
     --lat-chunk-size 512 \
     --static-worker-count 1 \
     --gwd30-worker-count 4
   ```
2. Run one-region smoke test:
   ```bash
   python scripts/run_phase4_classification_contract.py \
     --region amazon \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --year 2016 \
     --no-skip
   ```
3. Run canonical-subset proof:
   ```bash
   python scripts/run_phase4_classification_contract.py \
     --subset canonical \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --year 2016 \
     --no-skip
   ```

### Expected outcomes

- Logs show stage-tagged progress for `phase36`, `phase37`, `classification_contract_write`, and `classification_reload`.
- For each completed region, `results/phase4/classification_surfaces/`, `classification_regional_summaries/`, and `classification_hotspots/` contain the contract-aligned outputs for `g2017+glwd_v2+gwd30`.
- Hotspot JSON / CSV outputs preserve `quota`, `selected_count`, and `shortfall` status for each region.

### Edge cases to check during the HPC smoke

- If a source Phase 3.7 file is malformed or mismatched, the runner should fail explicitly with region / participant-set context instead of producing a half-valid hotspot pair.
- If a region output is manually corrupted, rerunning with `--no-skip` should rebuild it rather than silently trusting the broken files.

