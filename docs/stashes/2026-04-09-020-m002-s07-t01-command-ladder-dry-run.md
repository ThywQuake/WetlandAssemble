# 2026-04-09 M002/S07/T01 command ladder + dry-run quick reference

## What shipped
- Fixed `scripts/submit_phase4_trend_contract.sh` preflight so region resolution uses the explicit `--python-bin` instead of bare `python3`.
- Copied the ten-region trend wrapper dry-run summary to `results/phase4/proof/phase4-trend-contract-dry-run.tsv`.
- Wrote `results/phase4/proof/phase4-ten-region-command-ladder.md` as the bilingual frozen ladder for S07 T02-T04.
- Added/updated verification coverage in `tests/test_submit_phase4_trend_contract.py` for the wrapper dry-run interpreter path.
- Logged the operator-facing fix in `CHANGELOG.md` and the gotcha in `.gsd/KNOWLEDGE.md`.

## Frozen contract
- `--subset ten`
- Percentage key: `canonical`
- Classification key: `canonical`
- Trend dataset ids: `gwd30`, `giems_mc`, `topmodel`, `swamps`, `wad2m`
- Trend participant-set key: `giems_mc+gwd30+swamps+topmodel+wad2m`
- Ordered regions: `amazon, orinoco, pantanal, indogangetic, mekong, sudd, congo, okavango, borneo, northernaus`

## Verification status
- `bash -n scripts/submit_phase4_trend_contract.sh` ✅
- `python scripts/run_phase4_percentage_contract.py --help` ✅
- `python scripts/run_phase4_classification_contract.py --help` ✅
- `python scripts/run_phase4_trend_contract.py --help` ✅
- `python scripts/run_phase4_scaleout_readiness.py --help` ✅
- `python scripts/run_phase4_hotspot_ledger.py --help` ✅
- `python -m pytest tests/test_submit_phase4_trend_contract.py -q` ✅ (`3 passed`)
- Trend wrapper dry-run with explicit repo/python/std root/jobs dirs ✅
- `results/phase4/proof/phase4-trend-contract-dry-run.tsv` exists and is non-empty ✅

## Main risk / TODO
- Real standardized data still lives only at `/lustre/home/2200013429/Wetland_Assemble/data/standardized`; T02-T04 must run on HPC.
- Keep using `--no-skip` for real producer/readiness/ledger runs.
- Reuse the frozen ladder note instead of retyping region lists or trend dataset ids.

## HPC next commands / 下一步 HPC 命令
```bash
cd "$HOME/repos/WA"
python scripts/run_phase4_percentage_contract.py --subset ten --output-root results/phase4 --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --dataset-key canonical --surface-year 2016 --start-year 1990 --end-year 2020 --top-hotspots 10 --no-skip
python scripts/run_phase4_classification_contract.py --subset ten --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --year 2016 --phase36-output-dir results/phase3.6 --phase36-cache-dir results/cache/phase3_6 --phase37-output-dir results/phase3.7_hotspots --phase37-cache-dir results/cache/phase3_7 --no-skip
bash scripts/submit_phase4_trend_contract.sh --repo "$HOME/repos/WA" --python-bin "$HOME/repos/WA/.venv/bin/python" --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --subset ten --dataset-id gwd30 --dataset-id giems_mc --dataset-id topmodel --dataset-id swamps --dataset-id wad2m --aggregation annual --start-year 1990 --end-year 2020 --min-observations 5 --min-overlap-years 5 --top-hotspots 10 --cpus 2 --time 480 --partition C064M0256G --jobs-base temp/slurm-jobs-s07 --tmp-root temp/slurm-tmp-s07 --no-progress
```

## 中文摘要
- 本次 T01 不是新功能设计，而是先把十区 selector / canonical keys / trend participant set 冻结下来。
- 真正暴露的问题是 trend submit wrapper 的预检阶段偷偷调用了系统 `python3`，导致在没有完整科学依赖的解释器里先炸掉，连 dry-run 都跑不到脚本生成。
- 现在 dry-run 已经能稳定解析十个 region，并把五个 dataset（包含 `topmodel`）和 `--no-skip` 意图打印出来；后续 T02-T04 直接复用 `results/phase4/proof/phase4-ten-region-command-ladder.md` 即可。
