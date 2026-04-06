#!/usr/bin/env python3
"""Download GWD30 locally in batches and rsync each completed batch to HPC."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from redownload_obs_api import (  # noqa: E402
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DownloadTask,
    _build_object_key_from_relative_path,
    _local_file_matches_expected_size,
    _looks_like_tiff,
    download_file,
    tqdm,
)

DEFAULT_STAGING_ROOT = Path("temp/check_gwd30/local_rsync_buffer")
DEFAULT_REPORT_DIR = Path("results/maintenance/gwd30_local_then_rsync")
DEFAULT_BATCH_FILES = 100
DEFAULT_RSYNC_WRAPPER = "/Users/mac/.ssh/script/with_pkuhpc_auth.sh"
RSYNC_PROGRESS_RE = re.compile(r"^\s*([\d,]+)\s+\d+%")


def _announce(message: str) -> None:
    tqdm.write(f"[gwd30-local-rsync] {message}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download GWD30 locally from mismatch input, then rsync each completed "
            "batch to an HPC destination and clear local staged files."
        )
    )
    parser.add_argument(
        "recovery_input",
        help="Path to mismatch CSV or legacy corrupted_files_list.txt",
    )
    parser.add_argument(
        "--remote-dest",
        required=True,
        help="Rsync destination, e.g. user@host:/lustre/home/.../GWD30",
    )
    parser.add_argument(
        "--staging-root",
        type=Path,
        default=DEFAULT_STAGING_ROOT,
        help="Local temporary root used for staged downloads before rsync.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Concurrent local download workers per batch.",
    )
    parser.add_argument(
        "--batch-files",
        type=int,
        default=DEFAULT_BATCH_FILES,
        help="Maximum downloaded file count before triggering rsync.",
    )
    parser.add_argument(
        "--batch-size-gib",
        type=float,
        default=0.0,
        help="Optional batch size threshold in GiB (0 disables byte threshold).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Retry count per file download.",
    )
    parser.add_argument(
        "--download-timeout",
        type=int,
        default=DEFAULT_DOWNLOAD_TIMEOUT,
        help="Per-file download timeout in seconds.",
    )
    parser.add_argument(
        "--rsync-bin",
        default="rsync",
        help="Rsync executable to use.",
    )
    parser.add_argument(
        "--rsync-wrapper",
        default=DEFAULT_RSYNC_WRAPPER,
        help=(
            "Optional wrapper command used before rsync, matching sync.sh auth flow. "
            "Use an empty string to call rsync directly."
        ),
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Directory for local run summaries.",
    )
    parser.add_argument(
        "--overlap-rsync",
        action="store_true",
        help=(
            "Pipeline downloads with rsync: while batch N is syncing in the "
            "background, batch N+1 downloads into a separate local buffer."
        ),
    )
    return parser


def _iter_stage_files(staging_root: Path) -> list[Path]:
    if not staging_root.exists():
        return []
    return sorted(
        path
        for path in staging_root.rglob("*")
        if path.is_file() and path.suffix != ".part"
    )


def _stage_file_bytes(staging_root: Path) -> int:
    return sum(path.stat().st_size for path in _iter_stage_files(staging_root))


def _prune_empty_dirs(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                continue
    try:
        root.rmdir()
    except OSError:
        pass


def _remove_partial_files(staging_root: Path) -> int:
    if not staging_root.exists():
        return 0
    removed = 0
    for path in staging_root.rglob("*.part"):
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def _relative_path_from_legacy_line(line: str) -> str:
    path = Path(line.strip())
    return f"{path.parent.name}/{path.name}"


def _iter_transfer_roots(staging_root: Path) -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()
    candidates = [
        staging_root,
        *sorted(staging_root.parent.glob(f"{staging_root.name}.batch_*")),
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        roots.append(candidate)
    return roots


def _batch_staging_root(staging_root: Path, batch_index: int) -> Path:
    return staging_root.parent / f"{staging_root.name}.batch_{batch_index:05d}"


def _rebase_batch_tasks(
    batch: list[DownloadTask],
    *,
    source_root: Path,
    target_root: Path,
) -> list[DownloadTask]:
    if source_root.resolve() == target_root.resolve():
        return batch

    rebased: list[DownloadTask] = []
    for task in batch:
        relative_path = task.local_path.resolve().relative_to(source_root.resolve())
        rebased.append(
            DownloadTask(
                local_path=target_root / relative_path,
                object_key=task.object_key,
                expected_size_bytes=task.expected_size_bytes,
            )
        )
    return rebased


def _find_existing_local_match(
    *,
    staging_root: Path,
    relative_path: str,
    expected_size_bytes: int | None,
) -> Path | None:
    for root in _iter_transfer_roots(staging_root):
        candidate = root / relative_path
        if _local_file_matches_expected_size(candidate, expected_size_bytes):
            return candidate
    return None


def _handoff_stage_files(source_root: Path, target_root: Path) -> int:
    if source_root.resolve() == target_root.resolve():
        return 0

    moved = 0
    for path in _iter_stage_files(source_root):
        relative_path = path.resolve().relative_to(source_root.resolve())
        target_path = target_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            target_path.unlink()
        path.replace(target_path)
        moved += 1

    _prune_empty_dirs(source_root)
    return moved


def build_stage_tasks(
    recovery_input: Path,
    staging_root: Path,
) -> tuple[list[DownloadTask], int]:
    """Build local staged download tasks from CSV or legacy txt input."""

    recovery_input = recovery_input.expanduser().resolve()
    if not recovery_input.exists():
        raise FileNotFoundError(f"recovery input does not exist: {recovery_input}")

    pending_tasks: list[DownloadTask] = []
    already_staged = 0
    seen_relative_paths: set[str] = set()

    if recovery_input.suffix.lower() == ".csv":
        with recovery_input.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required_fields = {"relative_path", "expected_size_bytes"}
            if reader.fieldnames is None or not required_fields.issubset(set(reader.fieldnames)):
                raise ValueError(
                    "mismatch CSV must contain columns: "
                    + ", ".join(sorted(required_fields))
                )
            for row in reader:
                relative_path = str(row.get("relative_path", "")).strip()
                status = str(row.get("status", "")).strip()
                if not relative_path or not _looks_like_tiff(relative_path):
                    continue
                if status and status not in {"missing_file", "size_mismatch", "stat_failed"}:
                    continue
                if relative_path in seen_relative_paths:
                    continue
                seen_relative_paths.add(relative_path)
                expected_size_raw = str(row.get("expected_size_bytes", "")).strip()
                expected_size_bytes = int(expected_size_raw) if expected_size_raw else None
                local_path = staging_root / relative_path
                task = DownloadTask(
                    local_path=local_path,
                    object_key=_build_object_key_from_relative_path(relative_path),
                    expected_size_bytes=expected_size_bytes,
                )
                existing_local = _find_existing_local_match(
                    staging_root=staging_root,
                    relative_path=relative_path,
                    expected_size_bytes=expected_size_bytes,
                )
                if existing_local is not None:
                    already_staged += 1
                    continue
                pending_tasks.append(task)
        return pending_tasks, already_staged

    with recovery_input.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            relative_path = _relative_path_from_legacy_line(stripped)
            if relative_path in seen_relative_paths:
                continue
            seen_relative_paths.add(relative_path)
            local_path = staging_root / relative_path
            task = DownloadTask(
                local_path=local_path,
                object_key=_build_object_key_from_relative_path(relative_path),
                expected_size_bytes=None,
            )
            existing_local = _find_existing_local_match(
                staging_root=staging_root,
                relative_path=relative_path,
                expected_size_bytes=None,
            )
            if existing_local is not None:
                already_staged += 1
                continue
            pending_tasks.append(task)

    return pending_tasks, already_staged


def partition_batches(
    tasks: list[DownloadTask],
    *,
    batch_files: int,
    batch_size_bytes: int,
) -> list[list[DownloadTask]]:
    """Partition tasks by file count and optional total expected size."""

    if batch_files <= 0 and batch_size_bytes <= 0:
        raise ValueError("at least one batch threshold must be positive")

    batches: list[list[DownloadTask]] = []
    current_batch: list[DownloadTask] = []
    current_bytes = 0

    for task in tasks:
        task_bytes = task.expected_size_bytes or 0
        would_exceed_file_limit = batch_files > 0 and len(current_batch) >= batch_files
        would_exceed_size_limit = (
            batch_size_bytes > 0
            and current_batch
            and current_bytes + task_bytes > batch_size_bytes
        )
        if would_exceed_file_limit or would_exceed_size_limit:
            batches.append(current_batch)
            current_batch = []
            current_bytes = 0

        current_batch.append(task)
        current_bytes += task_bytes

    if current_batch:
        batches.append(current_batch)

    return batches


def rsync_staging_root(
    staging_root: Path,
    *,
    remote_dest: str,
    rsync_bin: str,
    rsync_wrapper: str | None,
    progress_bar=None,
    reserve_total_bytes: bool = False,
) -> dict[str, int]:
    """Rsync staged files to HPC and remove successfully transferred local files."""

    stage_files = _iter_stage_files(staging_root)
    if not stage_files:
        return {"transferred_files": 0, "transferred_bytes": 0}

    planned_file_count = len(stage_files)
    planned_bytes = sum(path.stat().st_size for path in stage_files)
    if progress_bar is not None and reserve_total_bytes:
        progress_bar.total = (progress_bar.total or 0) + planned_bytes
        progress_bar.refresh()

    command: list[str] = []
    if rsync_wrapper:
        command.extend([rsync_wrapper, rsync_bin])
    else:
        command.append(rsync_bin)
    command.extend(
        [
            "-avz",
            "--info=progress2",
            "--remove-source-files",
            "--exclude=*.part",
            f"{staging_root}/",
            remote_dest,
        ]
    )
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if process.stdout is None:
        raise RuntimeError("failed to capture rsync output stream")

    transferred_so_far = 0
    recent_messages: deque[str] = deque(maxlen=20)
    buffer = ""
    while True:
        chunk = process.stdout.read(1024)
        if not chunk:
            break
        buffer += chunk
        parts = re.split(r"[\r\n]+", buffer)
        buffer = parts.pop()
        for part in parts:
            progress_bytes = _parse_rsync_progress_bytes(part)
            if progress_bytes is not None:
                target_bytes = min(planned_bytes, progress_bytes)
                if progress_bar is not None and target_bytes > transferred_so_far:
                    progress_bar.update(target_bytes - transferred_so_far)
                transferred_so_far = max(transferred_so_far, target_bytes)
            elif part.strip():
                recent_messages.append(part.strip())

    if buffer.strip():
        progress_bytes = _parse_rsync_progress_bytes(buffer)
        if progress_bytes is not None:
            target_bytes = min(planned_bytes, progress_bytes)
            if progress_bar is not None and target_bytes > transferred_so_far:
                progress_bar.update(target_bytes - transferred_so_far)
            transferred_so_far = max(transferred_so_far, target_bytes)
        else:
            recent_messages.append(buffer.strip())

    returncode = process.wait()
    if returncode != 0:
        raise RuntimeError(
            "rsync failed with exit code "
            f"{returncode}: {' | '.join(recent_messages) if recent_messages else 'no output'}"
        )

    remaining_stage_files = _iter_stage_files(staging_root)
    remaining_bytes = sum(path.stat().st_size for path in remaining_stage_files)
    actual_transferred_files = planned_file_count - len(remaining_stage_files)
    actual_transferred_bytes = planned_bytes - remaining_bytes
    if progress_bar is not None and actual_transferred_bytes > transferred_so_far:
        progress_bar.update(actual_transferred_bytes - transferred_so_far)
    if actual_transferred_files == 0:
        _announce(
            f"rsync exited 0 but transferred 0 files from {staging_root}; "
            "source files remain locally"
        )

    _prune_empty_dirs(staging_root)
    return {
        "transferred_files": actual_transferred_files,
        "transferred_bytes": actual_transferred_bytes,
    }


def _parse_rsync_progress_bytes(output: str) -> int | None:
    match = RSYNC_PROGRESS_RE.match(output)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def write_reports(
    *,
    report_dir: Path,
    summary: dict[str, object],
    failed_downloads: list[dict[str, str]],
) -> dict[str, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = report_dir / "summary.json"
    failed_json = report_dir / "failed_downloads.json"
    failed_txt = report_dir / "failed_downloads.txt"

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    failed_json.write_text(json.dumps(failed_downloads, indent=2), encoding="utf-8")
    failed_txt.write_text(
        "\n".join(
            f"{item['relative_path']}: {item['error']}" for item in failed_downloads
        ),
        encoding="utf-8",
    )
    return {
        "summary": summary_path,
        "failed_json": failed_json,
        "failed_txt": failed_txt,
    }


def _relative_to_staging(local_path: Path, staging_root: Path) -> str:
    resolved = local_path.resolve()
    for root in _iter_transfer_roots(staging_root):
        try:
            return resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return f"{local_path.parent.name}/{local_path.name}"


def _download_batch(
    *,
    batch: list[DownloadTask],
    batch_index: int,
    batch_count: int,
    batch_root: Path,
    staging_root: Path,
    workers: int,
    max_retries: int,
    download_timeout: int,
    failed_downloads: list[dict[str, str]],
    download_progress_bar=None,
) -> int:
    actual_batch = _rebase_batch_tasks(
        batch,
        source_root=staging_root,
        target_root=batch_root,
    )
    successful_downloads = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_task = {
            executor.submit(
                download_file,
                task,
                max_retries,
                download_timeout,
            ): task
            for task in actual_batch
        }
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            path, success, message = future.result()
            if download_progress_bar is not None:
                download_progress_bar.update(1)
            if success:
                successful_downloads += 1
            else:
                failed_downloads.append(
                    {
                        "relative_path": _relative_to_staging(task.local_path, staging_root),
                        "error": message,
                    }
                )
    return successful_downloads


def _run(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    recovery_input = Path(args.recovery_input).expanduser().resolve()
    staging_root = args.staging_root.expanduser().resolve()
    batch_size_bytes = int(args.batch_size_gib * (1024 ** 3))

    _announce(f"recovery input: {recovery_input}")
    removed_partials = 0
    for root in _iter_transfer_roots(staging_root):
        removed_partials += _remove_partial_files(root)
    if removed_partials:
        _announce(f"removed {removed_partials} stale partial file(s) from transfer roots")

    pending_tasks, already_staged = build_stage_tasks(recovery_input, staging_root)
    _announce(
        f"prepared {len(pending_tasks)} pending download task(s); "
        f"{already_staged} file(s) already staged locally"
    )

    pre_existing_roots = [
        root for root in _iter_transfer_roots(staging_root) if _iter_stage_files(root)
    ]
    known_rsync_total_bytes = sum(_stage_file_bytes(root) for root in pre_existing_roots)
    known_rsync_total_bytes += sum(task.expected_size_bytes or 0 for task in pending_tasks)

    total_transferred_files = 0
    total_transferred_bytes = 0
    failed_downloads: list[dict[str, str]] = []
    successful_downloads = 0
    download_progress_bar = tqdm(
        total=len(pending_tasks),
        desc="Download",
        unit="file",
        dynamic_ncols=True,
        position=0,
    )
    rsync_progress_bar = tqdm(
        total=known_rsync_total_bytes,
        desc="Rsync",
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        dynamic_ncols=True,
        position=1,
    )

    batches = partition_batches(
        pending_tasks,
        batch_files=args.batch_files,
        batch_size_bytes=batch_size_bytes,
    ) if pending_tasks else []

    rsync_executor = ThreadPoolExecutor(max_workers=1) if args.overlap_rsync else None
    pending_rsync_future = None
    try:
        for root in pre_existing_roots:
            _announce(f"rsyncing pre-existing staged files from {root} before new downloads")
            transferred = rsync_staging_root(
                root,
                remote_dest=args.remote_dest,
                rsync_bin=args.rsync_bin,
                rsync_wrapper=args.rsync_wrapper.strip() or None,
                progress_bar=rsync_progress_bar,
                reserve_total_bytes=False,
            )
            total_transferred_files += transferred["transferred_files"]
            total_transferred_bytes += transferred["transferred_bytes"]

        for batch_index, batch in enumerate(batches, start=1):
            batch_root = (
                _batch_staging_root(staging_root, batch_index)
                if args.overlap_rsync
                else staging_root
            )
            successful_downloads += _download_batch(
                batch=batch,
                batch_index=batch_index,
                batch_count=len(batches),
                batch_root=batch_root,
                staging_root=staging_root,
                workers=args.workers,
                max_retries=args.max_retries,
                download_timeout=args.download_timeout,
                failed_downloads=failed_downloads,
                download_progress_bar=download_progress_bar,
            )

            if pending_rsync_future is not None:
                transferred = pending_rsync_future.result()
                total_transferred_files += transferred["transferred_files"]
                total_transferred_bytes += transferred["transferred_bytes"]
                pending_rsync_future = None

            if _iter_stage_files(batch_root):
                reserve_total_bytes = any(
                    task.expected_size_bytes is None for task in batch
                )
                rsync_source_root = batch_root
                if args.overlap_rsync:
                    _handoff_stage_files(batch_root, staging_root)
                    rsync_source_root = staging_root
                if args.overlap_rsync and rsync_executor is not None:
                    pending_rsync_future = rsync_executor.submit(
                        rsync_staging_root,
                        rsync_source_root,
                        remote_dest=args.remote_dest,
                        rsync_bin=args.rsync_bin,
                        rsync_wrapper=args.rsync_wrapper.strip() or None,
                        progress_bar=rsync_progress_bar,
                        reserve_total_bytes=reserve_total_bytes,
                    )
                else:
                    transferred = rsync_staging_root(
                        rsync_source_root,
                        remote_dest=args.remote_dest,
                        rsync_bin=args.rsync_bin,
                        rsync_wrapper=args.rsync_wrapper.strip() or None,
                        progress_bar=rsync_progress_bar,
                        reserve_total_bytes=reserve_total_bytes,
                    )
                    total_transferred_files += transferred["transferred_files"]
                    total_transferred_bytes += transferred["transferred_bytes"]

        if pending_rsync_future is not None:
            transferred = pending_rsync_future.result()
            total_transferred_files += transferred["transferred_files"]
            total_transferred_bytes += transferred["transferred_bytes"]
    finally:
        if rsync_executor is not None:
            rsync_executor.shutdown(wait=True)
        download_progress_bar.close()
        rsync_progress_bar.close()

    summary = {
        "completed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "recovery_input": str(recovery_input),
        "remote_dest": args.remote_dest,
        "staging_root": str(staging_root),
        "batch_files": args.batch_files,
        "batch_size_gib": args.batch_size_gib,
        "workers": args.workers,
        "max_retries": args.max_retries,
        "download_timeout": args.download_timeout,
        "rsync_bin": args.rsync_bin,
        "rsync_wrapper": args.rsync_wrapper.strip() or None,
        "overlap_rsync": args.overlap_rsync,
        "pending_tasks": len(pending_tasks),
        "already_staged": already_staged,
        "successful_downloads": successful_downloads,
        "failed_downloads": len(failed_downloads),
        "transferred_files": total_transferred_files,
        "transferred_bytes": total_transferred_bytes,
    }
    outputs = write_reports(
        report_dir=args.report_dir.expanduser().resolve(),
        summary=summary,
        failed_downloads=failed_downloads,
    )
    _announce(
        f"finished: downloaded={successful_downloads} failed={len(failed_downloads)} "
        f"transferred={total_transferred_files} summary={outputs['summary']}"
    )
    return 0 if not failed_downloads else 2


def _main(argv: list[str] | None = None) -> int:
    try:
        return _run(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:
        print(f"[gwd30-local-rsync] fatal: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
