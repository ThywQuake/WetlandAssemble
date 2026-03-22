# Landsat 优先审查清单脚本 — 摘要

**日期:** 2026-03-21  
**分支:** `feat/phase2-rough-binary-modis-truth`  
**状态:** 已新增简单 CLI 脚本，可从 `landsat_review_manifest.csv` 筛选高优先级 AOI

## Architecture decisions

- 用户希望“写成一个简单的 python 脚本实现”，因此本轮没有继续扩展成新模块体系，而是直接新增单文件脚本。
- 脚本输入：
  - `results/phase2/rough/landsat_review_manifest.csv`
- 脚本输出：
  - 默认 `results/phase2/rough/landsat_review_priority.csv`
  - 以及同名 `.json`
- 默认筛选规则：
  - `disagreement_score >= 0.8`
  - `participant_count >= 4`
  - `image_status in {downloaded, cached}`

## Modified files and key changes

- `scripts/build_phase2_landsat_review_priority.py`
  - 新增优先审查清单 CLI
  - 支持：
    - `--input`
    - `--output`
    - `--output-json`
    - `--min-disagreement`
    - `--min-participants`
    - `--image-status`
    - `--region`
    - `--target-time`
    - `--top-n`

## Verification status

- `uv run ruff check scripts/build_phase2_landsat_review_priority.py`: pass
- `uv run python scripts/build_phase2_landsat_review_priority.py --input results/phase2/rough/landsat_review_manifest.csv --output temp/landsat_review_priority.csv --output-json temp/landsat_review_priority.json --min-disagreement 0.8 --min-participants 4`: pass (`rows=30`)

## Open risks, TODOs, rollback notes

- 当前脚本仍然是“AOI 级主表 + run 级指标摘要”的筛选，不包含 patch-level pairwise ranking。
- 如果后续 reviewer 需要“最值得先看”的更细排序，可以增加：
  - `mean_iou` 升序优先
  - `min_kappa` 升序优先
  - 或区域配额约束（每个 region 最多 N 个）
