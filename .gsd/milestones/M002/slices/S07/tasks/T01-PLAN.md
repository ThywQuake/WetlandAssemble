---
estimated_steps: 12
estimated_files: 8
skills_used:
  - sync-hpc
---

# T01: Freeze the ten-region HPC command ladder and prove the trend wrapper dry-run

Why: catch selector/key drift before any real ten-region compute so later tasks do not debug stale participant sets or hand-written region lists.

## Steps
1. Reconfirm from live code that wide execution stays on `--subset ten`, `percentage_key=canonical`, `classification_key=canonical`, and `trend_participant_set_key=giems_mc+gwd30+swamps+topmodel+wad2m`; keep `topmodel` in every trend/readiness/ledger command.
2. Run the local preflight surface: `bash -n` on `scripts/submit_phase4_trend_contract.sh`, `--help` on the five Phase 4 CLIs, then the trend wrapper `--dry-run` with explicit `--repo`, `--python-bin`, HPC standardized dir, repo-local `--jobs-base`, and `--no-progress`.
3. Copy the generated dry-run summary TSV into `results/phase4/proof/phase4-trend-contract-dry-run.tsv`; if preflight exposes a selector or wrapper bug, patch only the touched contract/runner files, rerun focused tests/help commands, and resync before any real submit.
4. Write `results/phase4/proof/phase4-ten-region-command-ladder.md` in bilingual form, recording the frozen region order, keys, participant ids, exact HPC commands, and where later tasks should copy proof artifacts.

## Must-Haves
- [ ] No later task uses a hand-written ten-region list or drops `topmodel` from the trend participant set.
- [ ] The dry-run summary proves ten resolved regions, five datasets, and visible `--no-skip` intent.
- [ ] Any local bug fix is backed by the touched shell/help/pytest surfaces before HPC reruns continue.

## Done when
The repo has one checked command ladder plus a copied dry-run summary, and later tasks can reuse it without re-deriving keys or selectors.

## Inputs

- `.gsd/PROJECT.md`
- `.gsd/REQUIREMENTS.md`
- `scripts/run_phase4_percentage_contract.py`
- `scripts/run_phase4_classification_contract.py`
- `scripts/run_phase4_trend_contract.py`
- `scripts/submit_phase4_trend_contract.sh`
- `scripts/run_phase4_scaleout_readiness.py`
- `scripts/run_phase4_hotspot_ledger.py`

## Expected Output

- `results/phase4/proof/phase4-ten-region-command-ladder.md`
- `results/phase4/proof/phase4-trend-contract-dry-run.tsv`

## Verification

bash -n scripts/submit_phase4_trend_contract.sh
python scripts/run_phase4_percentage_contract.py --help
python scripts/run_phase4_classification_contract.py --help
python scripts/run_phase4_trend_contract.py --help
python scripts/run_phase4_scaleout_readiness.py --help
python scripts/run_phase4_hotspot_ledger.py --help
bash scripts/submit_phase4_trend_contract.sh \
  --dry-run \
  --repo "$PWD" \
  --python-bin "$PWD/.venv/bin/python" \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --subset ten \
  --dataset-id gwd30 \
  --dataset-id giems_mc \
  --dataset-id topmodel \
  --dataset-id swamps \
  --dataset-id wad2m \
  --aggregation annual \
  --start-year 1990 \
  --end-year 2020 \
  --min-observations 5 \
  --min-overlap-years 5 \
  --top-hotspots 10 \
  --cpus 2 \
  --time 480 \
  --partition C064M0256G \
  --jobs-base temp/slurm-jobs-s07 \
  --tmp-root temp/slurm-tmp-s07 \
  --no-progress
test -s results/phase4/proof/phase4-trend-contract-dry-run.tsv

## Observability Impact

- Signals added/changed: wrapper preflight stdout showing `Regions`, `Datasets`, `Skip mode`, and the copied dry-run summary TSV.
- How a future agent inspects this: open `results/phase4/proof/phase4-ten-region-command-ladder.md` and `results/phase4/proof/phase4-trend-contract-dry-run.tsv` before any real HPC submission.
- Failure state exposed: selector drift, missing repo/python paths, or dropped dataset ids fail before any SLURM job is submitted.

## Failure Modes

- **Dependencies**: `scripts/submit_phase4_trend_contract.sh`, the five Phase 4 CLIs, the local `.venv/bin/python`, and the frozen HPC standardized-dir path.
- **On error**: stop before any real submit, patch only the touched selector/wrapper code, rerun `bash -n` plus focused help/pytest surfaces, then regenerate the dry-run summary.
- **On timeout**: dry-run should be fast; if it stalls, inspect repo-local `temp/slurm-jobs-s07/` script generation and path resolution before assuming HPC is at fault.
- **On malformed response**: reject mixed `--subset` / `--region`, missing `--repo`, dropped dataset ids, or wrong region order instead of silently accepting the ladder.

## Load Profile

- **Shared resources**: repo-local temp jobs dir, copied dry-run summary TSV, and the frozen command-ladder note.
- **Per-operation cost**: one shell syntax pass, five `--help` calls, and one ten-region dry-run script generation.
- **10x breakpoint**: command drift, wrong paths, or missing dataset ids break trust long before runtime cost matters.

## Negative Tests

- **Malformed inputs**: missing `--repo`, bad `--python-bin`, mixed selector flags, missing `topmodel`, or a wrong standardized-dir path.
- **Error paths**: wrapper help/syntax and `--dry-run` must fail loudly on stale defaults or missing scripts instead of broadening silently.
- **Boundary conditions**: `canonical` vs `ten` selector order, repo-local `--jobs-base`, and explicit `--no-progress` / `--no-skip` intent remain deterministic.
