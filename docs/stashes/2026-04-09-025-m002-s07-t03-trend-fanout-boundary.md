# 2026-04-09 M002/S07/T03 trend fanout boundary quick reference

## What changed
- Repaired the local wrapper-test harness so fake-repo dry-run tests delegate to the dependency-complete repo Python instead of inheriting the standalone pytest tool interpreter.
- Expanded `tests/test_submit_phase4_trend_contract.py` to pin the T03 boundary conditions and malformed-input cases:
  - default dataset set still includes `topmodel`
  - `--subset ten` dry-run summary accounts for all ten regions
  - one-region debug reruns via `--region` stay stable
  - wrong `--repo`, bad `--python-bin`, and duplicate `--dataset-id` fail closed
- Wrote `results/phase4/proof/phase4-trend-fanout.md` as the bilingual authenticated-boundary / sync-back note for the missing ten-region trend submit proof.
- Appended one `.gsd/KNOWLEDGE.md` entry for the repo-python requirement in wrapper tests.

## What did not change
- No authenticated HPC rsync/submit/monitor step ran from this auto-mode container.
- `results/phase4/proof/phase4-trend-contract-submit.tsv` is still absent locally.
- Representative percentage/classification/trend manifests for `amazon` / `northernaus` are still absent locally, so T04 remains blocked on real sync-back artifacts.

## Verification status
- `bash -n scripts/submit_phase4_trend_contract.sh` ✅
- `python scripts/run_phase4_percentage_contract.py --help` ✅
- `python scripts/run_phase4_classification_contract.py --help` ✅
- `python scripts/run_phase4_trend_contract.py --help` ✅
- `bash scripts/submit_phase4_trend_contract.sh ... --subset ten ... --no-progress` dry-run ✅
- `uv run pytest tests/test_submit_phase4_trend_contract.py -q` ✅ after the harness fix
- `test -s results/phase4/proof/phase4-trend-contract-dry-run.tsv` ✅
- Authenticated HPC rsync / real producer runs / real trend submit TSV copy-back ❌ not executable from this container because OTP auth is still a hard boundary

## Open risks / TODOs
1. A real authenticated workstation/HPC session still needs to run the frozen percentage + classification + trend ladder.
2. The copied submit TSV must account for all ten regions under `participant_set_key=giems_mc+gwd30+swamps+topmodel+wad2m` before T04 reopens readiness/ledger.
3. If any region is retried remotely, preserve failed and replacement job ids in the proof note or task summary instead of silently overwriting history.

## Exact next HPC commands
```bash
rsync -avz --delete --exclude-from=.gitignore ./ \
  2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/
ssh 2200013429@wm2-data.pku.edu.cn <<'SH'
set -euo pipefail
cd /lustre/home/2200013429/repos/WA2
python scripts/run_phase4_percentage_contract.py \
  --subset ten \
  --output-root results/phase4 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --dataset-key canonical \
  --surface-year 2016 \
  --start-year 1990 \
  --end-year 2020 \
  --no-skip
python scripts/run_phase4_classification_contract.py \
  --subset ten \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --classification-key canonical \
  --year 2016 \
  --phase36-output-dir results/phase3.6 \
  --phase36-cache-dir results/cache/phase3_6 \
  --phase37-output-dir results/phase3.7_hotspots \
  --phase37-cache-dir results/cache/phase3_7 \
  --no-skip
bash scripts/submit_phase4_trend_contract.sh \
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
SH
rsync -avz \
  2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/results/phase4/proof/phase4-trend-contract-submit.tsv \
  results/phase4/proof/
```

## Chinese recap / 中文回顾
- 这次没有假装容器可以越过 OTP 边界；真实十区 trend fanout 仍然必须在已认证 HPC 会话里执行。
- 本地完成的是两类工作：
  1. 修正并扩展 wrapper 测试，让它们真正锚定 repo Python 与 T03 的 fail-closed/边界条件；
  2. 写好 `results/phase4/proof/phase4-trend-fanout.md`，把 sync-back 要求、participant-set key、日志检查面和后续动作固定下来。
- 下一步仍然是按上面的 HPC 命令执行真实 run，并把 `phase4-trend-contract-submit.tsv` 与代表性 manifests 同步回 repo，然后再进入 T04。
