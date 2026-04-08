# 2026-04-09 M002/S07 Slice Plan Quick Reference

## Slice intent / 本 slice 要做什么

S07 不是新合同设计 slice，而是 **真实十区 HPC materialization + readiness/ledger proof**：

1. 先冻结 `--subset ten`、canonical keys、trend participant set（必须包含 `topmodel`）
2. 再在 HPC 上依次跑 percentage / classification / trend submit fanout
3. 然后用 readiness 全绿 + unified ledger 复开作为唯一 closeout proof
4. 严格 paper-pack proof 仍留给 S08

## Planned task split

- **T01** — 冻结十区 command ladder，并用 trend wrapper `--dry-run` 证明 selector / keys / participant set / `--no-skip` 没漂移
- **T02** — 真实 materialize 十区 percentage + classification families
- **T03** — 提交并盯完十区 trend fanout，把 submit summary 复制进 repo proof bundle
- **T04** — 跑 readiness、断言 ten-region all-green、再 rebuild unified ledgers，并保留 proof note

## Frozen keys / selectors

- Region selector: `--subset ten`
- Percentage key: `canonical`
- Classification key: `canonical`
- Trend participant ids: `gwd30`, `giems_mc`, `topmodel`, `swamps`, `wad2m`
- Trend participant-set key: `giems_mc+gwd30+swamps+topmodel+wad2m`
- Ledger key: `canonical`

## Required proof artifacts

- `results/phase4/proof/phase4-ten-region-command-ladder.md`
- `results/phase4/proof/phase4-trend-contract-dry-run.tsv`
- `results/phase4/proof/phase4-producer-materialization.md`
- `results/phase4/proof/phase4-trend-contract-submit.tsv`
- `results/phase4/proof/phase4-trend-fanout.md`
- `results/phase4/proof/phase4-readiness-ledger-proof.md`
- `results/phase4/scaleout_readiness/subset-ten__canonical__canonical__giems_mc+gwd30+swamps+topmodel+wad2m__scaleout_readiness.json`
- `results/phase4/unified_hotspot_ledgers/amazon/canonical__amazon__unified_hotspot_ledger.csv`
- `results/phase4/unified_hotspot_ledgers/northernaus/canonical__northernaus__unified_hotspot_ledger.csv`

## Verification boundary

S07 只在以下条件同时成立时算完成：

- percentage / classification / trend 三条 family 已在真实十区输入上 materialize
- readiness JSON 的 `ready_region_ids` 精确等于：
  `amazon, orinoco, pantanal, indogangetic, mekong, sudd, congo, okavango, borneo, northernaus`
- readiness 没有 `missing` / `partial`
- unified ledger 对十区全部 region 复开成功

## Open risks

- 最容易出错的是人为漂移：手写 region list、漏掉 `topmodel`、误用旧 `--repo` / `--python-bin`、或者偷偷走 `--skip`
- trend fanout 是唯一有 SLURM fanout + checkpoint 复杂度的一腿，失败时必须按 region/job 处理，不能重回“一把梭宽跑”
- readiness / ledger 一旦报 `missing` / `partial`，应回退重跑上游 producer family，不能手改 artifact

## Immediate next step

先执行 T01：本地 `bash -n` + 五个 CLI `--help` + trend wrapper `--dry-run`，再把冻结好的 HPC command ladder 和 copied dry-run summary 写进 repo proof bundle。
