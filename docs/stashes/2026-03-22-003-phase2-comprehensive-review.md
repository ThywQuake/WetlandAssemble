# Phase 2 综合评审报告

**日期:** 2026-03-22
**分支:** `feat/phase2-rough-binary-modis-truth`
**状态:** Phase 2 代码审阅完成，82 tests passing，ruff clean

---

## 一、项目整体进展评判

### Phase 完成度总览

| Phase | 名称 | 状态 | 完成度 |
|-------|------|------|--------|
| Phase 1 | Loader Foundation | **COMPLETE** | 100% |
| Phase 2 | Rough Binary Comparison + MODIS Truth | **SUBSTANTIALLY COMPLETE** | ~95% |
| Phase 3 | Fine-Grained + Entropy + S2 Truth | NOT STARTED | 0% |
| Phase 4 | Trend Analysis | NOT STARTED | 0% |
| Phase 5 | Review Manifests & Documentation | NOT STARTED | 0% |

### Phase 2 交付物清单 vs 计划

| 计划交付物 | 实际文件 | 状态 |
|-----------|---------|------|
| `comparison/harmonize.py` | 560 行，含二值化 + 月聚合 + 网格对齐 + 1x1 单元边界修复 | Done |
| `comparison/rough_binary.py` | 180 行，pairwise metrics + disagreement + vote fraction | Done |
| `comparison/focus_areas.py` | 232 行，区域分层 AOI 选取 + 去重 | Done |
| `validation/gee_client.py` | 75 行，Earth Engine 懒加载包装 | Done |
| `validation/modis_reference.py` | 294 行，QA 去云 + 多时段融合 composite | Done |
| `validation/landsat_reference.py` | 328 行，多传感器 Collection 2 L2 参考 | Done (超出计划) |
| `rough_probe.py` | 1011 行，HPC 粗尺度诊断 | Done |
| `rough_batch.py` | 732 行，批量 9 区域 × 2 窗口执行 | Done |
| `modis_batch.py` | 331 行，独立 MODIS 批量下载 | Done |
| `landsat_batch.py` | 203 行，独立 Landsat 批量下载 | Done (超出计划) |
| `landsat_review_manifest.py` | 238 行，审查清单聚合 | Done (超出计划) |
| 7 个 CLI 脚本 | 570 行 | Done |

**代码量统计:**
- Phase 2 核心源码: **5,371 行**
- Phase 2 测试代码: **2,579 行**
- Phase 2 CLI 脚本: **570 行**
- 测试覆盖: **82 tests passing**

### Phase 2 超额完成的部分

- Landsat 参考影像下载链（计划中仅有 MODIS，实际并行建设了 Landsat）
- review manifest + priority shortlist 生成工具
- GWD30 三层执行形态（串行/并行/shard-reduce）
- 失败巡检脚本 `inspect_phase2_rough_failures.py`
- HPC OOM hardening（GWD30 逐 tile 直达 coarse grid）

### Phase 2 剩余 ~5% 尾巴

- HPC 端到端验证检查项中 `mekong_flooded_forest_200003` mean_iou=0.0 需科学层面解释
- `danau_sentarum` 因 participant_count=2 未进 priority list（策略层面，非工程 bug）
- Export.image 回退策略推迟到 Phase 5
- Manifest 持久化推迟到 Phase 5

---

## 二、Phase 2 代码质量审阅

### 2.1 comparison 模块

| 文件 | 质量评级 | 核心优点 | 核心问题 |
|------|---------|---------|---------|
| `harmonize.py` | **Strong** | 结构化异常层次、三阶段空值检测、1x1 单元边界修复精巧 | `_prepare_binary_source` 基于字符串分支（可维护性）；逐时步 reproject 缺注释 |
| `rough_binary.py` | **Very Strong** | 冻结 dataclass、disagreement score 公式优雅、标量坐标防御性剥离 | pairwise 指标不对称性（哪个是 prediction / reference）未文档化 |
| `focus_areas.py` | **Good** | 两轮分层选择算法合理、地理边界钳位 | 欧氏度空间距离近似（热带可接受）；测试覆盖最弱（仅 1 个测试） |

### 2.2 validation 模块

| 文件 | 质量评级 | 核心优点 | 核心问题 |
|------|---------|---------|---------|
| `gee_client.py` | **Good** | 懒加载设计、幂等初始化、clean factory | 裸 `Exception` 捕获（intentional for 不可预测 SDK） |
| `modis_reference.py` | **Good** | artifact-as-return-value 模式优秀、原子文件写入、QA 去云完整 | `urlopen` 无 timeout；`response.read()` 全量缓冲（大 AOI 风险） |
| `landsat_reference.py` | **Acceptable** | 与 MODIS 一致的 API 设计、多传感器融合 | **与 modis_reference 有 5 个完全相同的私有函数**，维护风险 |

### 2.3 batch/probe 模块

| 文件 | 质量评级 | 核心优点 | 核心问题 |
|------|---------|---------|---------|
| `rough_probe.py` | **High** | emit_progress 可观测性好、错误状态码完整 | `locals()` 检查代码异味；`_load_precomputed_gwd30_surface` 静默吞异常 |
| `rough_batch.py` | **Good** | 完整 provenance、GeoJSON trace 输出 | `_run_single_region_time` 140+ 行上帝函数；200 行内嵌 YAML |
| `modis_batch.py` | **Good** | 优雅 tqdm fallback、bbox 解析防御性好 | tqdm fallback 存在潜在 bug（见下） |
| `landsat_batch.py` | **Acceptable** | 遵循 modis_batch 模式 | 重复月份解析逻辑；从 modis_batch 导入 tqdm（反向依赖） |
| `landsat_review_manifest.py` | **Good** | 30 字段 dataclass 完整、双格式输出 | 两个写函数体完全相同；JSON 序列化参数不一致 |

### 2.4 loaders + scripts

| 文件 | 质量评级 | 核心问题 |
|------|---------|---------|
| `glwd.py` | **Good** | `_combined_raster_priority` 对候选双次调用；选取时 I/O 无 try/except |
| `gwd30.py` | **Good (复杂)** | `load_rough_binary_surface` 双路径由 trace dict 字符串控制（脆弱）；`accumulated_count` 用 `int16` 有溢出风险 |
| 7 个 CLI 脚本 | **Pass** | `_coerce_exit_code` 重复 7 次；`os._exit` 无注释 |

---

## 三、发现的 Bug 和风险

### 实际 Bug（需修复）

1. **tqdm fallback `_noop_tqdm` 潜在 crash** — 当 `tqdm` 不可用时，`_noop_tqdm(iterable)` 返回原始 iterable。后续调用 `.set_postfix_str()` / `.close()` 会抛 `AttributeError`。影响 `modis_batch.py` 和 `landsat_batch.py`。

2. **`landsat_review_manifest.py` JSON 序列化不一致** — 缺少 `sort_keys=True` 和 `allow_nan=False`，与项目其他模块不一致，可能导致 NaN 污染和非确定性输出。

### 中等风险（建议修复）

3. **`urlopen` 无 timeout** — `modis_reference.py` 和 `landsat_reference.py` 的 `_download_file` 没有设置超时，HPC 上挂连接会阻塞进程。

4. **`response.read()` 全量缓冲** — 大 AOI + 低 scale_meters 时可能 OOM，建议改为 `shutil.copyfileobj` 流式写入。

5. **`gwd30.py` `accumulated_count` 使用 `np.int16`** — 理论上超 32767 会溢出，应改为 `np.int32`。

6. **modis/landsat reference 5 个相同私有函数** — `_download_file`、`_collection_size`、`_format_date`、`_month_window`、`_classify_failure` 完全重复，需同步维护。

### 低风险（可后续处理）

7. `_prepare_binary_source` 字符串分支——可维护但不易扩展
8. `focus_areas._is_far_enough` 欧氏度空间近似——热带可接受
9. `rough_probe.py` 使用 `locals()` 检查局部变量
10. `_coerce_exit_code` 重复 7 次——建议提取到共享模块
11. `rough_batch._run_single_region_time` 140+ 行——建议拆分

---

## 四、测试覆盖评估

### 覆盖良好的区域
- `rough_probe.py` — 9 个测试，覆盖主要路径
- `harmonize.py` — 7 个测试，覆盖核心场景
- `modis_reference.py` — 4 个测试，含端到端集成测试

### 覆盖不足的区域
- **`focus_areas.py`** — 仅 1 个测试，缺少距离过滤、区域配额、边界情况
- **`rough_binary.py`** — 仅 2 个测试，缺少 < 2 surface 验证、NaN 处理、kappa 边界
- **`landsat_batch.py`** — 仅 1 个测试，缺少失败路径
- **validation 状态分支** — `empty_collection`、`cached`、`gee_auth_failed`、`download_failed` 均无测试
- **测试间重复** — `FakeEeModule` 在多个测试文件中重复，`_focus_area_csv_line` 重复 3 次

---

## 五、架构设计评价

### 设计亮点
1. **artifact-as-return-value** — GEE 下载从不抛异常，用终态状态码替代 try/except，极大简化批处理编排
2. **原子文件写入** — `NamedTemporaryFile` + `replace()` 防止中断导致的损坏文件
3. **GWD30 逐 tile 直达 coarse grid** — 避免 OOM 的低内存路径设计
4. **BrokenProcessPool 串行回退** — HPC 容错设计
5. **结构化异常** — `EmptyBinarySurfaceError` 携带 `dataset_id`、`source_variable`、`stage`
6. **三阶段空值检测** — prepared_source / aligned_to_reference_grid / comparison_slice

### 架构隐忧
1. **validation 包内部重复** — 5 个相同函数跨 modis/landsat 两个模块
2. **batch 模块反向依赖** — landsat_batch 从 modis_batch 导入 tqdm 工具
3. **rough_batch 内嵌 200 行 YAML** — 应移至独立数据文件或 config/
4. **状态码为裸字符串** — 应使用 `Literal` 或 `Enum` 增强类型安全

---

## 六、建议优先级

### P0: 修复实际 Bug
- [ ] 修复 `_noop_tqdm` fallback 使其返回支持 `.set_postfix_str()` / `.close()` 的包装对象
- [ ] 统一 `landsat_review_manifest.py` 的 JSON 序列化参数

### P1: 中等风险修复
- [ ] 给 `urlopen` 添加 `timeout` 参数
- [ ] 将 `response.read()` 改为流式下载
- [ ] `gwd30.py` 的 `accumulated_count` 改为 `np.int32`
- [ ] 提取 validation 包中的 5 个重复函数到 `_download_utils.py`

### P2: 测试加固
- [ ] 为 `focus_areas.py` 补充距离过滤、区域配额等测试
- [ ] 为 validation 模块补充 `empty_collection` / `cached` / failure 等状态分支测试
- [ ] 提取 `FakeEeModule` 到 `tests/test_validation/conftest.py`

### P3: 代码整理（可与 Phase 3 一并处理）
- [ ] 提取 `_coerce_exit_code` 到共享模块
- [ ] 拆分 `rough_batch._run_single_region_time`
- [ ] 文档化 `rough_binary.py` pairwise 指标不对称性
- [ ] tqdm fallback 移到 `src/WA/utils/progress.py`

---

## 七、Phase 3 启动建议

Phase 2 工程质量扎实，HPC 已验证通过（82 tests, ruff clean, results/phase2/rough 无 failed runs）。建议：

1. **先修 P0 bug**（预计 30 分钟）
2. **可选做 P1 修复**（如果要在当前分支提交 Phase 2 收尾 PR）
3. **然后切入 Phase 3**：`docs/plans/2026-03-19-004-feat-phase3-fine-grained-entropy-s2-plan.md`
   - fine_grained.py: G2017 / GLWD v2 / GWD30 共享类别对比
   - hotspots.py: Shannon entropy hotspot 提取
   - s2_reference.py: Sentinel-2 cloud-masked composite
