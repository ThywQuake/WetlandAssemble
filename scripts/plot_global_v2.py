#!/usr/bin/env python3
"""绘制每个数据集的全球湿地百分比分布图 - 使用 loader 加载原始数据"""

import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import xarray as xr

# 添加 src 到路径
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from WA._geo_env import configure_geospatial_runtime
from WA.classification import wetland_fraction_from_standardized_classes
from WA.config import load_config
from WA.loaders import get_loader

configure_geospatial_runtime()

# 数据目录
DATA_DIR = Path("/lustre/home/2200013429/Wetland_Assemble/data/standardized")
OUTPUT_DIR = Path("results/figures/global_v2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 目标分辨率：0.25°×0.25° (1440×720)
TARGET_RESOLUTION = (1440, 720)
TARGET_YEAR = 2016

# 需要使用 loader 的数据集
LOADER_DATASETS = {"giems_mc", "swamps", "wad2m", "topmodel"}


def load_with_loader(dataset_id: str, target_year: int) -> xr.DataArray | None:
    """使用 loader 从原始文件加载数据"""
    print("  -> 使用 loader 加载原始数据...", flush=True)

    config = load_config("config/datasets.yaml", "config/gee_config.yaml")
    ds_config = config.datasets.get(dataset_id)

    if ds_config is None:
        print(f"  -> [错误] 未找到 {dataset_id} 配置", flush=True)
        return None

    try:
        loader = get_loader(dataset_id, ds_config)

        # 定义全球热带/亚热带范围
        bbox = (-180, -35, 180, 23.5)

        # 根据数据集类型设置时间范围
        if dataset_id in ["giems_mc", "swamps", "wad2m"]:
            time_range = (f"{target_year}-01-01", f"{target_year}-12-31")
        elif dataset_id == "topmodel":
            time_range = (f"{target_year}-01-01", f"{target_year}-12-31")
        else:
            time_range = None

        print(f"  -> 加载 {dataset_id} (year={target_year}, bbox={bbox})...", flush=True)

        # 使用 loader 加载
        if time_range:
            ds = loader.load(bbox=bbox, time_range=time_range)
        else:
            ds = loader.load(bbox=bbox)

        print(f"  -> loader 加载完成，维度：{ds.dims}", flush=True)

        # 提取湿地变量
        if "wetland_fraction" in ds.data_vars:
            wetland = ds["wetland_fraction"]
        elif "inundation" in ds.data_vars:
            wetland = ds["inundation"]
        elif "fw" in ds.data_vars:
            wetland = ds["fw"]
        else:
            print("  -> [错误] 未找到湿地变量", flush=True)
            return None

        # 聚合时间维度 (年平均)
        if "time" in wetland.dims:
            print("  -> 聚合时间维度 (年平均)...", flush=True)
            wetland = wetland.mean(dim="time", skipna=True)

        # 聚合其他非空间维度
        for dim in ["config", "forcing"]:
            if dim in wetland.dims:
                print(f"  -> 聚合维度 '{dim}'...", flush=True)
                wetland = wetland.mean(dim=dim, skipna=True)

        return wetland

    except Exception as e:
        print(f"  -> [错误] loader 加载失败：{e}", flush=True)
        return None


def load_from_standardized(dataset_id: str, target_year: int) -> xr.DataArray | None:
    """从标准化文件加载"""
    print("  -> 从标准化文件加载...", flush=True)

    # 静态数据集
    if dataset_id in ["g2017", "glwd_v2"]:
        file_path = DATA_DIR / f"{dataset_id}.nc"
    else:
        file_path = DATA_DIR / f"{dataset_id}_{target_year}.nc"

    if not file_path.exists():
        print(f"  -> [错误] 文件不存在：{file_path}", flush=True)
        return None

    print(f"  -> 加载文件：{file_path.name}", flush=True)
    ds = xr.open_dataset(file_path)

    wetland = wetland_fraction_from_standardized_classes(dataset_id, ds)
    if wetland is None:
        print(f"  -> [错误] 无法从 {dataset_id} 标准化分类中提取湿地百分比", flush=True)
        return None

    print(f"  -> 聚合完成，形状：{wetland.shape}", flush=True)
    return wetland


def resample_to_target(
    wetland: xr.DataArray,
    target_resolution: tuple[int, int],
    dataset_id: str,
) -> xr.DataArray:
    """降采样到目标分辨率"""
    lat_dim = "lat" if "lat" in wetland.dims else "y"
    lon_dim = "lon" if "lon" in wetland.dims else "x"

    orig_lat = len(wetland.coords[lat_dim])
    orig_lon = len(wetland.coords[lon_dim])
    target_lon, target_lat = target_resolution

    # 检查是否需要降采样
    needs_resampling = abs(orig_lon - target_lon) > 10 or abs(orig_lat - target_lat) > 10

    if needs_resampling:
        print(f"  -> 降采样：{orig_lon}x{orig_lat} -> {target_lon}x{target_lat}", flush=True)
        factor_lat = max(1, orig_lat // target_lat)
        factor_lon = max(1, orig_lon // target_lon)

        # 使用块平均降采样
        wetland = wetland.coarsen(
            {lat_dim: factor_lat, lon_dim: factor_lon},
            boundary='trim'
        ).mean(skipna=True)
    else:
        print("  -> 原生分辨率接近目标，跳过降采样", flush=True)

    return wetland


def plot_global_distribution(
    wetland: xr.DataArray,
    dataset_id: str,
    output_path: Path,
    year: int | None = None,
) -> Path:
    """绘制全球分布图"""
    print(f"\n[{dataset_id}] 开始绘图...", flush=True)
    t0 = time.time()

    lat_dim = "lat" if "lat" in wetland.dims else "y"
    lon_dim = "lon" if "lon" in wetland.dims else "x"

    print(f"  -> 数据形状：{wetland.shape}", flush=True)

    # 白蓝 colormap
    from matplotlib.colors import LinearSegmentedColormap
    wb_cmap = LinearSegmentedColormap.from_list("wetland_wb", ["#ffffff", "#1f77b4"])

    # 尝试使用 cartopy
    use_cartopy = False
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
        use_cartopy = True
        print("  -> 使用 cartopy 绘制海岸线...", flush=True)
    except ImportError:
        print("  -> cartopy 未安装，使用标准 matplotlib", flush=True)

    fig = plt.figure(figsize=(12, 8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 0.04], wspace=0.05)

    print("  -> 绘制地图...", flush=True)
    if use_cartopy:
        ax_map = fig.add_subplot(gs[0, 0], projection=ccrs.PlateCarree())
    else:
        ax_map = fig.add_subplot(gs[0, 0])

    m = wetland.plot.pcolormesh(
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

    ax_map.set_aspect('equal')

    # 从数据坐标获取范围
    plot_lons = wetland.coords[lon_dim].values
    plot_lats = wetland.coords[lat_dim].values
    ax_map.set_xlim(plot_lons[0], plot_lons[-1])
    ax_map.set_ylim(plot_lats[-1], plot_lats[0])

    if use_cartopy:
        ax_map.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black')

    # colorbar
    ax_cbar = fig.add_subplot(gs[0, 1])
    fig.colorbar(m, cax=ax_cbar, label="Wetland Fraction", shrink=0.95)
    ax_cbar.tick_params(labelsize=8)
    ax_cbar.outline.set_visible(False)

    print("  -> 保存图像...", flush=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    elapsed = time.time() - t0
    print(f"  -> 绘图完成，耗时：{elapsed:.2f}秒", flush=True)
    print(f"  -> 已保存：{output_path}", flush=True)

    return output_path


def main():
    """主函数"""
    print("\n" + "=" * 60, flush=True)
    print(f"全球湿地百分比分布图绘制程序 (基准年：{TARGET_YEAR})", flush=True)
    print("=" * 60, flush=True)

    # 数据集配置：(dataset_id, year_override, use_loader)
    datasets = [
        ("berkeley_rwawc", 2019, False),  # Berkeley 用 2019
        ("g2017", None, False),  # 静态
        ("giems_mc", TARGET_YEAR, True),  # 使用 loader
        ("glwd_v2", None, False),  # 静态
        ("swamps", TARGET_YEAR, True),  # 使用 loader
        ("topmodel", TARGET_YEAR, True),  # 使用 loader
        ("wad2m", TARGET_YEAR, True),  # 使用 loader
    ]

    print(f"\n数据目录：{DATA_DIR}", flush=True)
    print(f"输出目录：{OUTPUT_DIR}", flush=True)
    ds_info = [(d[0], d[1], 'loader' if d[2] else 'std') for d in datasets]
    print(f"待处理数据集：{ds_info}", flush=True)

    total_start = time.time()
    success_count = 0
    fail_count = 0

    for i, (ds_id, year_override, use_loader) in enumerate(datasets, 1):
        print(f"\n\n{'#'*60}", flush=True)
        print(f"#{' '*20} 数据集 {i}/{len(datasets)}: {ds_id} {' '*20}#", flush=True)
        print(f"{'#'*60}\n", flush=True)

        target_year = year_override if year_override is not None else TARGET_YEAR

        # 加载数据
        if use_loader:
            wetland = load_with_loader(ds_id, target_year)
        else:
            wetland = load_from_standardized(ds_id, target_year)

        if wetland is None:
            print(f"\n[{ds_id}] [跳过] 无法加载数据", flush=True)
            fail_count += 1
            continue

        # 降采样
        wetland = resample_to_target(wetland, TARGET_RESOLUTION, ds_id)

        # 绘图
        output_path = OUTPUT_DIR / f"{ds_id}_global_wetland.png"
        if year_override is not None:
            plot_year = year_override
        elif ds_id in ["g2017", "glwd_v2"]:
            plot_year = None
        else:
            plot_year = TARGET_YEAR
        plot_global_distribution(wetland, ds_id, output_path, year=plot_year)
        success_count += 1

    total_elapsed = time.time() - total_start

    print("\n\n" + "=" * 60, flush=True)
    print("程序执行完成！", flush=True)
    print("=" * 60, flush=True)
    print(f"总耗时：{total_elapsed:.2f}秒 ({total_elapsed/60:.1f}分钟)", flush=True)
    print(f"成功：{success_count} 个数据集", flush=True)
    print(f"失败：{fail_count} 个数据集", flush=True)
    print(f"\n输出文件位置：{OUTPUT_DIR.absolute()}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
