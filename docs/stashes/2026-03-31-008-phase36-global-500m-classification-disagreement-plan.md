# 2026-03-31 Phase 3.6 global 500m classification disagreement plan

## Summary

- 新建 `Phase 3.6` 方案文档，目标是在全球 `500m` 尺度上比较 `G2017 / GLWD v2 / GWD30` 三个分类数据集。
- 统一类别体系只认 `config/classification_mappings.yaml`，不再依赖旧的硬编码 4-class / 8-class 映射。
- 核心硬约束：**只在三个数据集都有效的格点上比较**；任一数据集缺失则该格点不参与计算。
- 主指标定义为三者主导类别投票后的 **normalized Shannon entropy**，归一化分母固定为 `log2(3)`。
- 计划输出 `entropy / majority_class / agreement_count / joint_valid_mask`，并附带全局面积加权汇总统计。

## Files

- `docs/plans/2026-03-31-001-phase36-global-500m-classification-disagreement-plan.md`

## Verification

- 文档改动，无代码验证步骤。
