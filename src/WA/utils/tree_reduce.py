"""Tree-structured reduce utility for merging large numbers of files.

This module provides a generic tree-reduce pattern that can merge N files
into ~K regional files through log2(N) rounds of parallel pairwise merging.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar

import numpy as np
import xarray as xr

from WA.loaders.base import BBox
from WA.utils.progress import tqdm

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class MergeFunc(Protocol):
    """Protocol for a merge function that combines two files into one."""

    def __call__(
        self,
        path_a: Path,
        path_b: Path,
        output_path: Path,
    ) -> Path:
        """Merge two files into one.

        Args:
            path_a: First input file
            path_b: Second input file
            output_path: Output file path

        Returns:
            Path to the merged output file
        """
        ...


def tree_reduce(
    inputs: list[tuple[Path, Any]],
    output_dir: Path,
    merge_func: MergeFunc,
    target_count: int = 30,
    worker_count: int = 4,
    show_progress: bool = True,
    cleanup_rounds: bool = True,
) -> list[tuple[Path, Any]]:
    """Reduce input files using tree-structured pairwise merging.

    Args:
        inputs: List of (path, metadata) tuples to merge
        output_dir: Directory for intermediate and final output files
        merge_func: Function to merge two files
        target_count: Target number of output files (default: 30)
        worker_count: Number of parallel workers (default: 4)
        show_progress: Show progress bars (default: True)
        cleanup_rounds: Whether to delete intermediate files after each round

    Returns:
        List of (output_path, metadata) tuples after reduction
    """
    if len(inputs) <= target_count:
        logger.info("Tree-reduce: %d inputs <= target %d, skipping", len(inputs), target_count)
        return inputs

    output_dir.mkdir(parents=True, exist_ok=True)

    current_round = inputs
    round_num = 0

    while len(current_round) > target_count:
        round_num += 1
        next_round: list[tuple[Path, Any]] = []
        pairs = []

        # Pair up adjacent files
        i = 0
        while i < len(current_round) - 1:
            pairs.append((current_round[i], current_round[i + 1]))
            i += 2
        if i < len(current_round):
            # Odd one out - carry forward unchanged
            next_round.append(current_round[i])

        logger.info(
            "Tree-reduce round %d: merging %d pairs -> %d files (target: %d)",
            round_num,
            len(pairs),
            len(pairs) + len(next_round),
            target_count,
        )

        if pairs:
            # Prepare merge tasks
            merge_tasks = []
            for idx, ((path_a, _), (path_b, _)) in enumerate(pairs):
                output_name = f"reduced_r{round_num:02d}_p{idx:04d}.dat"
                output_path = output_dir / output_name
                merge_tasks.append((path_a, path_b, output_path))

            # Execute merges in parallel
            merged_results: list[tuple[Path, Any]] = []
            progress = (
                tqdm(
                    total=len(merge_tasks),
                    desc=f"Round {round_num}",
                    unit="merge",
                    dynamic_ncols=True,
                )
                if show_progress
                else None
            )

            try:
                with ProcessPoolExecutor(max_workers=worker_count) as executor:
                    futures = {
                        executor.submit(merge_func, path_a, path_b, output_path): (
                            path_a,
                            path_b,
                            output_path,
                        )
                        for path_a, path_b, output_path in merge_tasks
                    }
                    for future in as_completed(futures):
                        path_a, path_b, output_path = futures[future]
                        try:
                            result_path = future.result()
                            # Preserve metadata from first input
                            merged_results.append((result_path, pairs[merge_tasks.index((path_a, path_b, output_path))][0][1]))
                        except Exception as exc:
                            logger.warning(
                                "Merge pair (%s, %s) failed: %s",
                                path_a.name,
                                path_b.name,
                                exc,
                            )
                        if progress:
                            progress.update(1)
            finally:
                if progress:
                    progress.close()

            next_round.extend(merged_results)

        # Clean up previous round files if enabled
        if cleanup_rounds and round_num > 1:
            files_to_clean = 0
            for path, _ in current_round:
                if path.exists() and path.name.startswith(f"reduced_r{round_num - 1:02d}"):
                    path.unlink(missing_ok=True)
                    files_to_clean += 1
            if files_to_clean > 0:
                logger.debug(
                    "Tree-reduce round %d: cleaned up %d files from round %d",
                    round_num,
                    files_to_clean,
                    round_num - 1,
                )

        current_round = next_round
        logger.info(
            "Tree-reduce round %d complete: %d files remaining",
            round_num,
            len(current_round),
        )

    logger.info(
        "Tree-reduce complete: %d output files after %d rounds",
        len(current_round),
        round_num,
    )
    return current_round


def merge_gwd30_staged_tiles(
    path_a: Path,
    path_b: Path,
    output_path: Path,
) -> Path:
    """Merge two GWD30 staged tile files into one.

    Both tiles must have the same grid structure (same coords).
    Returns the merged file path.
    """
    with xr.open_dataset(path_a, engine="netcdf4") as src_a:
        weighted_a = np.asarray(src_a["weighted"].values, dtype=np.float32)
        coverage_a = np.asarray(src_a["coverage"].values, dtype=np.float32)
        time_coords = np.asarray(src_a.coords["time"].values)
        class_coords = np.asarray(src_a.coords["class_id"].values)
        y_dim = "lat" if "lat" in src_a.coords else "y"
        x_dim = "lon" if "lon" in src_a.coords else "x"
        y_coords = np.asarray(src_a.coords[y_dim].values)
        x_coords = np.asarray(src_a.coords[x_dim].values)

    with xr.open_dataset(path_b, engine="netcdf4") as src_b:
        weighted_b = np.asarray(src_b["weighted"].values, dtype=np.float32)
        coverage_b = np.asarray(src_b["coverage"].values, dtype=np.float32)

    weighted_sum = weighted_a + weighted_b
    coverage_sum = coverage_a + coverage_b

    coords = {
        "time": time_coords,
        "class_id": class_coords,
        y_dim: y_coords,
        x_dim: x_coords,
    }
    merged = xr.Dataset(
        {
            "weighted": xr.DataArray(
                weighted_sum,
                dims=("time", "class_id", y_dim, x_dim),
                coords=coords,
            ),
            "coverage": xr.DataArray(
                coverage_sum,
                dims=("time", y_dim, x_dim),
                coords={"time": time_coords, y_dim: y_coords, x_dim: x_coords},
            ),
        },
        attrs={"merged_from": [path_a.name, path_b.name]},
    )

    temp_path = output_path.parent / f".{output_path.name}.tmp-{os.getpid()}"
    try:
        merged.to_netcdf(temp_path, format="NETCDF4", engine="netcdf4")
        os.replace(temp_path, output_path)
    finally:
        merged.close()
        temp_path.unlink(missing_ok=True)

    return output_path
