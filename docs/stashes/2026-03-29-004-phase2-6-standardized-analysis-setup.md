# 2026-03-29 Phase 2.6 标准化数据分析

## 完成内容

### 1. 标准化数据加载器 (`src/WA/standardized_loader.py`)

完全独立的加载器类，不依赖现有 `DatasetLoader` 架构：

```python
from WA.standardized_loader import StandardizedDataLoader

loader = StandardizedDataLoader("output/standardized")

# 列出所有可用数据集
datasets = loader.list_available_datasets()

# 加载单个数据集
g2017 = loader.load("g2017")                    # 静态
wad2m_2016 = loader.load("wad2m", year=2016)   # 动态

# 加载某年所有数据集
all_2016 = loader.load_all_for_year(2016, bbox=(100, 10, 110, 20))
```

### 2. Harmonize 支持 (`src/WA/comparison/harmonize.py`)

新增函数：
- `harmonize_standardized_datasets()` - 批量 harmonize 标准化目录中的所有数据集
- `load_standardized_surface()` - 加载并 harmonize 单个数据集

### 3. CLI 脚本 (`scripts/run_phase2_6_analysis.py`)

```bash
# 完整分析（全域）
python scripts/run_phase2_6_analysis.py \
    --standardized-dir output/standardized \
    --output-dir results/phase2.6 \
    --bbox -180 -35 180 35

# 快速测试（小区域）
python scripts/run_phase2_6_analysis.py \
    --standardized-dir output/standardized \
    --output-dir results/phase2.6 \
    --bbox 100 10 110 20 \
    --datasets g2017 glwd_v2

# 指定年份
python scripts/run_phase2_6_analysis.py \
    --standardized-dir output/standardized \
    --output-dir results/phase2.6 \
    --years 2016 2017

# Dry run（仅列出数据集）
python scripts/run_phase2_6_analysis.py --dry-run
```

### 4. 测试 (`tests/test_standardized_loader.py`)

12 个测试全部通过：
- 空目录处理
- 静态/动态数据集识别
- bbox 裁剪
- time_range 裁剪
- load_all_for_year
- exclude 功能

## 标准化数据现状

```
output/standardized/
├── g2017.nc                    # 静态
├── glwd_v2.nc                  # 静态
├── berkeley_rwawc_2018.nc      # 2018-2025 (8 年)
├── giems_mc_1993.nc            # 1993-2007 (15 年)
├── swamps_1992.nc              # 1992-1999 (8 年)
├── wad2m_2000.nc               # 2000-2020 (21 年)
└── ... (共 55 个文件)
```

**缺失**: GWD30, TOPMODEL (Phase 1.5 未完成)

## TOPMODEL 标准化

创建专用脚本 `scripts/submit_standardize_topmodel.sh`：

```bash
# 提交 TOPMODEL 标准化（按年份拆分）
bash scripts/submit_standardize_topmodel.sh

# 仅提交特定年份
bash scripts/submit_standardize_topmodel.sh --years 2016,2017

# 不拆分年份（单作业处理所有年）
bash scripts/submit_standardize_topmodel.sh --no-split-years

# Dry run 预览
bash scripts/submit_standardize_topmodel.sh --dry-run

# 自定义资源
bash scripts/submit_standardize_topmodel.sh --time 480 --cpus 16
```

**TOPMODEL 配置：**
- 默认时间：240 分钟（4 小时）
- 默认 CPU: 8
- 分区：high
- 分辨率：500m

## 下一步

1. 在 HPC 上运行小区域测试验证
2. 添加趋势分析支持（复用 `trends.py`）
3. 添加可视化面板生成（复用 `comparison_panel.py`）

## 测试命令

```bash
# 单元测试
python -m pytest tests/test_standardized_loader.py -v

# 完整测试
python -m pytest tests/ -v

# CLI dry run
python scripts/run_phase2_6_analysis.py --dry-run
```
