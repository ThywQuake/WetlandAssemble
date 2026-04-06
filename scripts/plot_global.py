#!/usr/bin/env python3
"""绘制每个数据集的全球湿地百分比分布图 - 使用 xarray coarsen 降采样"""

import time
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

# 添加 src 到路径
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from WA.classification import wetland_fraction_from_standardized_classes

# 数据目录
DATA_DIR = Path("/lustre/home/2200013429/Wetland_Assemble/data/standardized")
OUTPUT_DIR = Path("results/figures/global")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def find_best_year_file(dataset_id: str, target_year: int = 2016) -> tuple[Path, int] | None:
    """查找指定年份的文件，如果没有则找最近的年份"""
    print(f"[{dataset_id}] 步骤 1/4: 查找 {target_year} 年数据...", flush=True)

    # 静态数据集
    if dataset_id in ["g2017", "glwd_v2"]:
        files = sorted(DATA_DIR.glob(f"{dataset_id}.nc"))
        if files:
            print(f"  -> 静态数据集，使用：{files[0].name}", flush=True)
            return files[0], target_year
        return None

    # 时间序列数据集：查找目标年份
    target_file = DATA_DIR / f"{dataset_id}_{target_year}.nc"
    if target_file.exists():
        print(f"  -> 找到 {target_year} 年数据：{target_file.name}", flush=True)
        return target_file, target_year

    # 没找到，找最近的年份
    print(f"  -> {target_year} 年数据不存在，查找最近年份...", flush=True)
    all_files = sorted(DATA_DIR.glob(f"{dataset_id}_*.nc"))

    if not all_files:
        print(f"  -> [错误] 未找到任何 {dataset_id} 数据！", flush=True)
        return None

    # 从文件名提取年份
    def extract_year(path: Path) -> int:
        try:
            # 格式：dataset_YYYY.nc
            return int(path.stem.split("_")[-1])
        except (ValueError, IndexError):
            return 0

    available_years = [(f, extract_year(f)) for f in all_files]
    available_years = [(f, y) for f, y in available_years if y > 0]

    if not available_years:
        print("  -> [错误] 无法解析年份！", flush=True)
        return None

    # 找最近的年份
    best_file, best_year = min(available_years, key=lambda x: abs(x[1] - target_year))
    print(f"  -> 使用最近年份：{best_year} 年 ({best_file.name})", flush=True)

    return best_file, best_year


def load_and_process(
    dataset_id: str,
    target_year: int = 2016,
    target_resolution: tuple[int, int] | None = None,  # (lon, lat) 目标分辨率
) -> xr.DataArray | None:
    """加载并处理数据集，返回 2D 湿地百分比表面（已降采样）"""
    print(f"\n{'='*50}", flush=True)
    print(f"[{dataset_id}] 开始处理 (目标年份：{target_year})", flush=True)
    print(f"{'='*50}", flush=True)

    # 步骤 1: 查找文件
    file_result = find_best_year_file(dataset_id, target_year)
    if file_result is None:
        return None

    file_path, actual_year = file_result
    print(f"\n[{dataset_id}] 步骤 2/4: 加载数据...", flush=True)
    t0 = time.time()

    try:
        print(f"  -> 加载文件：{file_path.name}", flush=True)
        ds = xr.open_dataset(file_path)

        print("  -> 加载完成！", flush=True)
        print(f"  -> 数据集维度：{ds.dims}", flush=True)
        print(f"  -> 数据变量：{list(ds.data_vars.keys())[:10]}", flush=True)
        if len(ds.data_vars) > 10:
            print(f"     ... 还有 {len(ds.data_vars) - 10} 个变量", flush=True)

    except Exception as e:
        print(f"  -> [错误] 加载失败：{e}", flush=True)
        return None

    # 步骤 3: 提取湿地变量（先不聚合，先降采样）
    print(f"\n[{dataset_id}] 步骤 3/5: 提取湿地变量...", flush=True)
    if dataset_id in {"g2017", "glwd_v2", "gwd30"}:
        wetland = wetland_fraction_from_standardized_classes(dataset_id, ds)
        if wetland is None:
            print("  -> [错误] 未找到可用的分类湿地百分比变量！", flush=True)
            return None
        print("  -> 使用 YAML 分类规则汇总湿地类（排除 waterbody）", flush=True)
        wetland_vars_list = [name for name in ds.data_vars if name.startswith("frac_")]
        extra_vars: list[str] = []

    elif dataset_id == "giems_mc":
        # GIEMS-MC: 标准化后已是 wetland_fraction
        print("  -> GIEMS-MC: 使用 wetland_fraction 变量 (年平均值)", flush=True)
        wetland_vars_list = ["wetland_fraction"]
        extra_vars = []
        wetland = None

    elif dataset_id == "swamps":
        # SWAMPS: 标准化后变量名为 wetland_fraction
        print("  -> SWAMPS: 使用 wetland_fraction 变量 (年平均值)", flush=True)
        wetland_vars_list = ["wetland_fraction"]
        extra_vars = []
        wetland = None

    elif dataset_id == "wad2m":
        # WAD2M: 使用原始 wetland_fraction 变量
        print("  -> WAD2M: 使用 wetland_fraction 变量 (年平均值)", flush=True)
        wetland_vars_list = ["wetland_fraction"]
        extra_vars = []
        wetland = None

    elif "wetland_fraction" in ds.data_vars:
        print("  -> 找到 wetland_fraction 变量", flush=True)
        wetland_vars_list = ["wetland_fraction"]
        extra_vars = []
        wetland = None

    elif "watermask" in ds.data_vars:
        print("  -> 找到 watermask 变量", flush=True)
        wetland_vars_list = ["watermask"]
        extra_vars = []
        wetland = None

    else:
        print("  -> [错误] 未找到湿地变量！", flush=True)
        return None

    # 确定空间维度
    sample_var = ds[wetland_vars_list[0]]
    lat_dim = "lat" if "lat" in sample_var.dims else "y"
    lon_dim = "lon" if "lon" in sample_var.dims else "x"

    orig_lat = len(sample_var.coords[lat_dim])
    orig_lon = len(sample_var.coords[lon_dim])
    print(f"  -> 原始分辨率：{orig_lon} x {orig_lat}", flush=True)

    # 如果没有指定目标分辨率，使用原始分辨率
    if target_resolution is None:
        target_lon, target_lat = orig_lon, orig_lat
    else:
        target_lon, target_lat = target_resolution

    # 检查是否需要降采样 (原生 0.25°≈1440x720 不需要)
    needs_resampling = abs(orig_lon - target_lon) > 10 or abs(orig_lat - target_lat) > 10
    if needs_resampling:
        factor_lat = max(1, orig_lat // target_lat)
        factor_lon = max(1, orig_lon // target_lon)
        print(f"  -> 降采样因子：lat={factor_lat}, lon={factor_lon}", flush=True)
    else:
        print("  -> 原生分辨率接近 0.25°，跳过降采样", flush=True)
        target_lon, target_lat = orig_lon, orig_lat

    # 步骤 4: 先降采样，再聚合（时间友好）
    print(f"\n[{dataset_id}] 步骤 4/5: 降采样后聚合...", flush=True)

    # 对每个变量降采样后求和
    print("  -> 降采样并聚合湿地类...", flush=True)
    total_vars = len(wetland_vars_list) + len(extra_vars)
    if wetland is None:
        for i, var_name in enumerate(wetland_vars_list):
            print(f"     处理 {var_name} ({i+1}/{total_vars})...", flush=True)
            var = ds[var_name]

            # 聚合非空间维度（time, config, forcing, month）- 计算年平均
            for dim in ["config", "forcing", "time", "month"]:
                if dim in var.dims:
                    print(f"       -> 聚合维度 '{dim}' (年平均)", flush=True)
                    var = var.mean(dim=dim, skipna=True)

            # 降采样（如果需要）- 使用局部平均而非最近邻
            if needs_resampling:
                # 计算降采样因子
                factor_lat = max(1, orig_lat // target_lat)
                factor_lon = max(1, orig_lon // target_lon)
                # 使用 coarsen 进行块平均降采样
                var_ds = var.coarsen(
                    {lat_dim: factor_lat, lon_dim: factor_lon},
                    boundary='trim'
                ).mean(skipna=True)
            else:
                var_ds = var

            if wetland is None:
                wetland = var_ds
            else:
                wetland = wetland + var_ds
    else:
        for dim in ["config", "forcing", "time", "month"]:
            if dim in wetland.dims:
                print(f"       -> 聚合维度 '{dim}' (年平均)", flush=True)
                wetland = wetland.mean(dim=dim, skipna=True)
        if needs_resampling:
            factor_lat = max(1, orig_lat // target_lat)
            factor_lon = max(1, orig_lon // target_lon)
            wetland = wetland.coarsen(
                {lat_dim: factor_lat, lon_dim: factor_lon},
                boundary='trim'
            ).mean(skipna=True)

    print(f"  -> 聚合完成，最终形状：{wetland.shape}", flush=True)

    # 步骤 5: 计算统计信息
    print(f"\n[{dataset_id}] 步骤 5/5: 计算统计信息...", flush=True)
    valid_values = wetland.values.flatten()
    valid_values = valid_values[~np.isnan(valid_values)]

    if len(valid_values) > 0:
        print(f"  -> 有效像元数：{len(valid_values):,}", flush=True)
        print(f"  -> 平均值：{np.mean(valid_values):.4%}", flush=True)
        print(f"  -> 标准差：{np.std(valid_values):.4%}", flush=True)
        print(f"  -> 最小值：{np.min(valid_values):.4%}", flush=True)
        print(f"  -> 最大值：{np.max(valid_values):.4%}", flush=True)
        print(f"  -> 中位数：{np.median(valid_values):.4%}", flush=True)
    else:
        print("  -> [警告] 没有有效数据！", flush=True)

    elapsed = time.time() - t0
    print(f"\n[{dataset_id}] 处理完成，耗时：{elapsed:.2f}秒", flush=True)

    return wetland


def plot_global_distribution(
    wetland: xr.DataArray,
    dataset_id: str,
    output_path: Path,
    year: int | None = None,
) -> Path:
    """绘制全球分布图（数据已在 load_and_process 中降采样）"""
    print(f"\n[{dataset_id}] 开始绘图...", flush=True)
    t0 = time.time()

    # 数据已经在 load_and_process 中降采样到 0.25°，直接使用
    agg = wetland

    # 确定空间维度
    lat_dim = "lat" if "lat" in wetland.dims else "y"
    lon_dim = "lon" if "lon" in wetland.dims else "x"

    print(f"  -> 使用已降采样的数据，形状：{agg.shape}", flush=True)

    # 创建图形 - 地图 + 右侧 colorbar
    print("  -> 创建图形...", flush=True)

    # 白蓝 colormap
    from matplotlib.colors import LinearSegmentedColormap
    wb_cmap = LinearSegmentedColormap.from_list("wetland_wb", ["#ffffff", "#1f77b4"])

    # 尝试使用 cartopy 添加大陆轮廓线
    use_cartopy = False
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
        use_cartopy = True
        print("  -> 使用 cartopy 绘制大陆轮廓线...", flush=True)
    except ImportError:
        print("  -> cartopy 未安装，使用标准 matplotlib", flush=True)

    fig = plt.figure(figsize=(12, 8))
    gs = fig.add_gridspec(
        1, 2,
        width_ratios=[1, 0.04],
        wspace=0.05,
    )

    # 地图
    print("  -> 绘制全球分布地图...", flush=True)
    if use_cartopy:
        ax_map = fig.add_subplot(gs[0, 0], projection=ccrs.PlateCarree())
    else:
        ax_map = fig.add_subplot(gs[0, 0])

    m = agg.plot.pcolormesh(
        ax=ax_map,
        x=lon_dim,
        y=lat_dim,
        cmap=wb_cmap,
        vmin=0,
        vmax=1,
        add_colorbar=False,
        rasterized=True,
    )
    year_str = f" ({year})" if year else ""
    title = f"{dataset_id} - Global Wetland Percentage{year_str}"
    ax_map.set_title(title, fontsize=14, fontweight="bold")
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")

    # 设置等纵横比 (经纬度 1:1)，上正下负
    ax_map.set_aspect('equal')
    # 从 agg 的坐标获取范围
    plot_lons = agg.coords[lon_dim].values
    plot_lats = agg.coords[lat_dim].values
    ax_map.set_xlim(plot_lons[0], plot_lons[-1])
    ax_map.set_ylim(plot_lats[-1], plot_lats[0])

    # 添加大陆轮廓线
    if use_cartopy:
        ax_map.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black')

    # 与地图等高的 colorbar（窄版）
    ax_cbar = fig.add_subplot(gs[0, 1])
    cbar = fig.colorbar(m, cax=ax_cbar, label="Wetland Fraction", shrink=0.95)
    cbar.ax.tick_params(labelsize=8)
    cbar.outline.set_visible(False)

    print("  -> 地图绘制完成", flush=True)

    # 保存
    print(f"  -> 保存图片到：{output_path}", flush=True)
    # 使用 bbox_inches='tight' 替代 tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    elapsed = time.time() - t0
    print(f"  -> 绘图完成，耗时：{elapsed:.2f}秒", flush=True)
    print(f"  -> 已保存：{output_path}", flush=True)

    return output_path


TARGET_YEAR = 2016  # 目标年份
# 目标分辨率：0.25°×0.25° (全球约 1440×720)
# 原生就是 0.25° 的数据集 (giems_mc, topmodel, wad2m) 不需要重采样
TARGET_RESOLUTION = (1440, 720)


def main():
    """主函数"""
    print("\n" + "=" * 60, flush=True)
    print(f"全球湿地百分比分布图绘制程序 (基准年：{TARGET_YEAR})", flush=True)
    print("=" * 60, flush=True)

    datasets = [
        ("berkeley_rwawc", 2019),  # Berkeley 用 2019 (2018 不完整)
        ("g2017", None),  # 静态
        ("giems_mc", 2016),  # 2016 年
        ("glwd_v2", None),  # 静态
        ("swamps", 2016),  # 2016 年
        # ("gwd30", 2016),  # 暂未标准化完成
        ("topmodel", 2016),  # 2016 年
        ("wad2m", 2016),  # 2016 年
    ]

    print(f"\n数据目录：{DATA_DIR}", flush=True)
    print(f"输出目录：{OUTPUT_DIR}", flush=True)
    print(f"待处理数据集：{[d[0] for d in datasets]}", flush=True)
    print(f"目标分辨率：{TARGET_RESOLUTION[0]} x {TARGET_RESOLUTION[1]}", flush=True)

    total_start = time.time()
    success_count = 0
    fail_count = 0
    actual_years: dict[str, int | str] = {}

    for i, (ds_id, year_override) in enumerate(datasets, 1):
        print(f"\n\n{'#'*60}", flush=True)
        print(f"#{' '*20} 数据集 {i}/{len(datasets)}: {ds_id} {' '*20}#", flush=True)
        print(f"{'#'*60}\n", flush=True)

        # 使用覆盖年份或默认目标年份
        target_year = year_override if year_override is not None else TARGET_YEAR
        wetland = load_and_process(ds_id, target_year, TARGET_RESOLUTION)

        if wetland is not None:
            # 记录实际使用的年份
            if year_override is None:
                actual_years[ds_id] = "static"
            else:
                actual_years[ds_id] = target_year

            output_path = OUTPUT_DIR / f"{ds_id}_global_wetland.png"
            plot_year = actual_years[ds_id] if isinstance(actual_years[ds_id], int) else None
            plot_global_distribution(wetland, ds_id, output_path, year=plot_year)
            success_count += 1
        else:
            print(f"\n[{ds_id}] [跳过] 无法处理此数据集", flush=True)
            fail_count += 1

    total_elapsed = time.time() - total_start

    print("\n\n" + "=" * 60, flush=True)
    print("程序执行完成！", flush=True)
    print("=" * 60, flush=True)
    print(f"总耗时：{total_elapsed:.2f}秒 ({total_elapsed/60:.1f}分钟)", flush=True)
    print(f"成功：{success_count} 个数据集", flush=True)
    print(f"失败：{fail_count} 个数据集", flush=True)
    print("\n实际使用年份:", flush=True)
    for ds_id, year in actual_years.items():
        print(f"  - {ds_id}: {year}", flush=True)
    print(f"\n输出文件位置：{OUTPUT_DIR.absolute()}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
