"""标准化数据加载器测试."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from WA.standardized_loader import StandardizedDataLoader


class TestListAvailableDatasets:
    """测试 list_available_datasets 方法."""

    def test_empty_directory(self) -> None:
        """空目录应返回空列表."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = StandardizedDataLoader(tmpdir)
            datasets = loader.list_available_datasets()
            assert datasets == []

    def test_static_dataset(self) -> None:
        """应正确识别静态数据集."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建 mock 文件
            Path(tmpdir, "g2017.nc").touch()
            Path(tmpdir, "glwd_v2.nc").touch()

            loader = StandardizedDataLoader(tmpdir)
            datasets = loader.list_available_datasets()

            assert len(datasets) == 2
            g2017 = next(ds for ds in datasets if ds.dataset_id == "g2017")
            assert g2017.is_static is True
            assert g2017.year is None

    def test_dynamic_dataset(self) -> None:
        """应正确识别动态数据集及其年份."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "wad2m_2016.nc").touch()
            Path(tmpdir, "wad2m_2017.nc").touch()

            loader = StandardizedDataLoader(tmpdir)
            datasets = loader.list_available_datasets()

            assert len(datasets) == 2
            wad2m_2016 = next(ds for ds in datasets if ds.dataset_id == "wad2m_2016")
            assert wad2m_2016.is_static is False
            assert wad2m_2016.year == 2016


class TestLoad:
    """测试 load 方法."""

    def test_load_static_dataset(self) -> None:
        """加载静态数据集."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建有效的 netCDF 文件
            ds = xr.Dataset({
                "wetland_fraction": xr.DataArray(
                    np.random.rand(10, 10).astype(np.float32),
                    dims=("lat", "lon"),
                    coords={
                        "lat": np.linspace(-35, 35, 10),
                        "lon": np.linspace(-180, 180, 10),
                    },
                )
            })
            ds.to_netcdf(Path(tmpdir, "g2017.nc"))

            loader = StandardizedDataLoader(tmpdir)
            loaded = loader.load("g2017")

            assert "wetland_fraction" in loaded
            assert loaded.sizes["lat"] == 10
            assert loaded.sizes["lon"] == 10

    def test_load_dynamic_dataset(self) -> None:
        """加载动态数据集（指定年份）."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ds = xr.Dataset({
                "wetland_fraction": xr.DataArray(
                    np.random.rand(12, 10, 10).astype(np.float32),
                    dims=("time", "lat", "lon"),
                    coords={
                        "time": xr.date_range("2016-01", periods=12, freq="MS"),
                        "lat": np.linspace(-35, 35, 10),
                        "lon": np.linspace(-180, 180, 10),
                    },
                )
            })
            ds.to_netcdf(Path(tmpdir, "wad2m_2016.nc"))

            loader = StandardizedDataLoader(tmpdir)
            loaded = loader.load("wad2m", year=2016)

            assert "wetland_fraction" in loaded
            assert loaded.sizes["time"] == 12

    def test_file_not_found(self) -> None:
        """文件不存在应抛出异常."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = StandardizedDataLoader(tmpdir)

            with pytest.raises(FileNotFoundError):
                loader.load("nonexistent")

    def test_load_with_bbox(self) -> None:
        """测试 bbox 裁剪."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ds = xr.Dataset({
                "wetland_fraction": xr.DataArray(
                    np.random.rand(20, 40).astype(np.float32),
                    dims=("lat", "lon"),
                    coords={
                        "lat": np.linspace(-35, 35, 20),
                        "lon": np.linspace(-180, 180, 40),
                    },
                )
            })
            ds.to_netcdf(Path(tmpdir, "g2017.nc"))

            loader = StandardizedDataLoader(tmpdir)
            loaded = loader.load("g2017", bbox=(0, 0, 90, 35))

            # 验证裁剪后的范围
            assert float(loaded["lon"].min()) >= 0
            assert float(loaded["lon"].max()) <= 90
            assert float(loaded["lat"].min()) >= 0
            assert float(loaded["lat"].max()) <= 35

    def test_load_with_time_range(self) -> None:
        """测试时间范围裁剪."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ds = xr.Dataset({
                "wetland_fraction": xr.DataArray(
                    np.random.rand(12, 10, 10).astype(np.float32),
                    dims=("time", "lat", "lon"),
                    coords={
                        "time": xr.date_range("2016-01", periods=12, freq="MS"),
                        "lat": np.linspace(-35, 35, 10),
                        "lon": np.linspace(-180, 180, 10),
                    },
                )
            })
            ds.to_netcdf(Path(tmpdir, "wad2m_2016.nc"))

            loader = StandardizedDataLoader(tmpdir)
            loaded = loader.load(
                "wad2m",
                year=2016,
                time_range=("2016-03", "2016-08"),
            )

            assert loaded.sizes["time"] == 6  # Mar-Aug


class TestLoadAllForYear:
    """测试 load_all_for_year 方法."""

    def test_load_all_for_year(self) -> None:
        """加载指定年份的所有数据集."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 静态数据集
            xr.Dataset({"wetland_fraction": xr.DataArray(np.random.rand(5, 5))}).to_netcdf(
                Path(tmpdir, "g2017.nc")
            )
            # 2016 年动态数据集
            xr.Dataset({"wetland_fraction": xr.DataArray(np.random.rand(5, 5))}).to_netcdf(
                Path(tmpdir, "wad2m_2016.nc")
            )
            # 2017 年动态数据集（不应被加载）
            xr.Dataset({"wetland_fraction": xr.DataArray(np.random.rand(5, 5))}).to_netcdf(
                Path(tmpdir, "wad2m_2017.nc")
            )

            loader = StandardizedDataLoader(tmpdir)
            datasets = loader.load_all_for_year(2016)

            assert "g2017" in datasets
            assert "wad2m_2016" in datasets
            assert "wad2m_2017" not in datasets

    def test_load_all_for_year_with_exclude(self) -> None:
        """测试排除指定数据集."""
        with tempfile.TemporaryDirectory() as tmpdir:
            xr.Dataset({"wetland_fraction": xr.DataArray(np.random.rand(5, 5))}).to_netcdf(
                Path(tmpdir, "g2017.nc")
            )
            xr.Dataset({"wetland_fraction": xr.DataArray(np.random.rand(5, 5))}).to_netcdf(
                Path(tmpdir, "wad2m_2016.nc")
            )

            loader = StandardizedDataLoader(tmpdir)
            datasets = loader.load_all_for_year(2016, exclude=["g2017"])

            assert "g2017" not in datasets
            assert "wad2m_2016" in datasets


class TestGetTimeRange:
    """测试 get_time_range 方法."""

    def test_get_time_range_dynamic(self) -> None:
        """获取动态数据集的时间范围."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ds = xr.Dataset({
                "wetland_fraction": xr.DataArray(
                    np.random.rand(12, 5, 5).astype(np.float32),
                    dims=("time", "lat", "lon"),
                    coords={
                        "time": xr.date_range("2016-01", periods=12, freq="MS"),
                        "lat": np.linspace(-35, 35, 5),
                        "lon": np.linspace(-180, 180, 5),
                    },
                )
            })
            ds.to_netcdf(Path(tmpdir, "wad2m_2016.nc"))

            loader = StandardizedDataLoader(tmpdir)
            time_range = loader.get_time_range("wad2m", year=2016)

            assert time_range is not None
            assert time_range[0] == "2016-01-01"
            assert time_range[1] == "2016-12-01"

    def test_get_time_range_static(self) -> None:
        """静态数据集应返回 None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            xr.Dataset({"wetland_fraction": xr.DataArray(np.random.rand(5, 5))}).to_netcdf(
                Path(tmpdir, "g2017.nc")
            )

            loader = StandardizedDataLoader(tmpdir)
            time_range = loader.get_time_range("g2017")

            assert time_range is None
