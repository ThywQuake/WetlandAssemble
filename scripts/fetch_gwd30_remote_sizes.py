#!/usr/bin/env python3
"""Fetch the authoritative remote size manifest for all GWD30 GeoTIFF files."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.config import get_dataset_config  # noqa: E402
from WA.utils.progress import tqdm  # noqa: E402

DEFAULT_ENDPOINT = "https://data-starcloud.pcl.ac.cn/aiforearth/api/data/getFileListByPage"
DEFAULT_OUTPUT_DIR = Path("results/maintenance/gwd30_remote_size_manifest")
DEFAULT_TABLE = "rs_gwd"
DEFAULT_COUNT = 1000
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 5


@dataclass(frozen=True)
class RemoteSizeRecord:
    """One GWD30 file entry returned by the remote catalog."""

    year: int
    file_name: str
    relative_path: str
    size_bytes: int
    gid: int | None


def _announce(message: str) -> None:
    print(f"[gwd30-remote-sizes] {message}", flush=True)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch the remote GWD30 TIFF size manifest from data-starcloud.",
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="*",
        help="Optional subset of GWD30 years to fetch. Defaults to config/datasets.yaml.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/datasets.yaml"),
        help="Dataset config used when --years is omitted.",
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="Catalog API endpoint.",
    )
    parser.add_argument(
        "--table",
        default=DEFAULT_TABLE,
        help="API table parameter.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help="Requested page size. The live API currently accepts values from 1 to 1000.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Retry count for transient network failures.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the fetched manifest files.",
    )
    return parser


def resolve_years(years: list[int] | None, *, dataset_config_path: Path) -> list[int]:
    """Resolve the year list from CLI or dataset config."""

    if years:
        return sorted({int(year) for year in years})

    dataset_config = get_dataset_config("gwd30", dataset_config_path=dataset_config_path)
    raw_years = dataset_config.get("years")
    if not isinstance(raw_years, list) or not raw_years:
        raise ValueError("datasets.gwd30.years must be a non-empty list")
    return sorted({int(year) for year in raw_years})


def _request_headers() -> dict[str, str]:
    """Headers mirrored from the captured browser request where helpful."""

    return {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json",
        "Origin": "https://data-starcloud.pcl.ac.cn",
        "Referer": "https://data-starcloud.pcl.ac.cn/iearthdata/map?id=60",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/146.0.0.0 Safari/537.36"
        ),
        'sec-ch-ua': '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        'sec-ch-ua-platform': '"macOS"',
    }


def fetch_page(
    *,
    endpoint: str,
    table: str,
    year: int,
    page: int,
    count: int,
    timeout: int,
    max_retries: int,
) -> tuple[list[RemoteSizeRecord], int]:
    """Fetch one catalog page for a given GWD30 year."""

    payload = {
        "params": {
            "table": table,
            "path": f"GWD30/{year}",
            "page": page,
            "enableSpatialQuery": False,
            "count": count,
        }
    }
    response_payload = _request_json(
        endpoint=endpoint,
        payload=payload,
        timeout=timeout,
        max_retries=max_retries,
        year=year,
        page=page,
    )

    if not isinstance(response_payload, dict):
        raise ValueError(
            f"unexpected response type for year {year} page {page}: "
            f"{type(response_payload).__name__}"
        )

    raw_items = response_payload.get("response")
    if not isinstance(raw_items, list):
        raise ValueError(f"response.response must be a list for year {year} page {page}")

    total = int(response_payload.get("total", len(raw_items)))
    records: list[RemoteSizeRecord] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError(
                f"response item must be an object for year {year} page {page}, "
                f"got {type(item).__name__}"
            )
        file_name = item.get("file")
        size_value = item.get("size")
        gid_value = item.get("gid")
        if not isinstance(file_name, str) or not file_name.lower().endswith((".tif", ".tiff")):
            continue
        if not isinstance(size_value, int):
            raise ValueError(
                f"response item for {file_name} in year {year} page {page} "
                "is missing an integer size"
            )
        gid = int(gid_value) if isinstance(gid_value, int) else None
        records.append(
            RemoteSizeRecord(
                year=year,
                file_name=file_name,
                relative_path=f"{year}/{file_name}",
                size_bytes=size_value,
                gid=gid,
            )
        )

    return records, total


def _request_json(
    *,
    endpoint: str,
    payload: dict[str, object],
    timeout: int,
    max_retries: int,
    year: int,
    page: int,
) -> object:
    """Request one JSON payload, preferring curl because the site blocks urllib."""

    if shutil.which("curl"):
        return _request_json_with_curl(
            endpoint=endpoint,
            payload=payload,
            timeout=timeout,
            max_retries=max_retries,
            year=year,
            page=page,
        )
    return _request_json_with_urllib(
        endpoint=endpoint,
        payload=payload,
        timeout=timeout,
        max_retries=max_retries,
        year=year,
        page=page,
    )


def _request_json_with_curl(
    *,
    endpoint: str,
    payload: dict[str, object],
    timeout: int,
    max_retries: int,
    year: int,
    page: int,
) -> object:
    """Request JSON with curl, matching the browser request shape."""

    last_exc: Exception | None = None
    headers = _request_headers()
    command = [
        "curl",
        endpoint,
        "-X",
        "POST",
        "--silent",
        "--show-error",
        "--fail-with-body",
        "--max-time",
        str(timeout),
    ]
    for key, value in headers.items():
        command.extend(["-H", f"{key}: {value}"])
    command.extend(["--data-raw", json.dumps(payload, separators=(",", ":"))])

    for attempt in range(1, max_retries + 1):
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            return json.loads(completed.stdout)
        except (subprocess.CalledProcessError, OSError, json.JSONDecodeError) as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise RuntimeError(
                    f"failed to fetch GWD30 year {year} page {page}: {exc}"
                ) from exc
            wait_seconds = DEFAULT_RETRY_BACKOFF_SECONDS * attempt
            _announce(
                f"year {year} page {page} attempt {attempt}/{max_retries} failed: {exc}; "
                f"retrying in {wait_seconds}s"
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"failed to fetch GWD30 year {year} page {page}") from last_exc


def _request_json_with_urllib(
    *,
    endpoint: str,
    payload: dict[str, object],
    timeout: int,
    max_retries: int,
    year: int,
    page: int,
) -> object:
    """Fallback for environments without curl."""

    encoded_payload = json.dumps(payload).encode("utf-8")
    request = Request(
        endpoint,
        data=encoded_payload,
        headers=_request_headers(),
        method="POST",
    )

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise RuntimeError(
                    f"failed to fetch GWD30 year {year} page {page}: {exc}"
                ) from exc
            wait_seconds = DEFAULT_RETRY_BACKOFF_SECONDS * attempt
            _announce(
                f"year {year} page {page} attempt {attempt}/{max_retries} failed: {exc}; "
                f"retrying in {wait_seconds}s"
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"failed to fetch GWD30 year {year} page {page}") from last_exc


def fetch_gwd30_remote_sizes(
    *,
    years: list[int],
    endpoint: str,
    table: str,
    count: int,
    timeout: int,
    max_retries: int,
) -> list[RemoteSizeRecord]:
    """Fetch the full remote size manifest across all requested years."""

    if count <= 0:
        raise ValueError("--count must be positive")

    all_records: dict[str, RemoteSizeRecord] = {}
    progress = tqdm(years, total=len(years), desc="GWD30 remote size years", unit="year")
    try:
        for year in progress:
            _announce(f"fetching catalog entries for year {year} with count={count}")
            page = 1
            expected_total: int | None = None
            year_records = 0

            while True:
                records, total = fetch_page(
                    endpoint=endpoint,
                    table=table,
                    year=year,
                    page=page,
                    count=count,
                    timeout=timeout,
                    max_retries=max_retries,
                )
                if expected_total is None:
                    expected_total = total

                if not records:
                    break

                for record in records:
                    if record.relative_path in all_records:
                        raise ValueError(
                            "duplicate remote record detected: "
                            f"{record.relative_path}"
                        )
                    all_records[record.relative_path] = record
                    year_records += 1

                _announce(
                    f"year {year}: page {page} returned {len(records)} TIFF(s); "
                    f"fetched {year_records}/{expected_total}"
                )
                progress.set_postfix_str(f"{year}:{year_records}", refresh=False)

                if expected_total <= year_records:
                    break
                page += 1

            if expected_total is None:
                raise RuntimeError(f"year {year}: did not receive any API response")
            if year_records != expected_total:
                raise RuntimeError(
                    f"year {year}: fetched {year_records} TIFF(s) "
                    f"but API reported total={expected_total}"
                )
    finally:
        progress.close()

    return [all_records[key] for key in sorted(all_records)]


def write_size_manifest(
    records: list[RemoteSizeRecord],
    *,
    output_dir: Path,
    years: list[int],
    endpoint: str,
    table: str,
    count: int,
) -> dict[str, Path]:
    """Write fetched remote size manifest files."""

    output_dir.mkdir(parents=True, exist_ok=True)

    per_year_counts: dict[str, int] = {}
    per_year_total_bytes: dict[str, int] = {}
    for record in records:
        year_key = str(record.year)
        per_year_counts[year_key] = per_year_counts.get(year_key, 0) + 1
        per_year_total_bytes[year_key] = per_year_total_bytes.get(year_key, 0) + record.size_bytes

    summary = {
        "fetched_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "endpoint": endpoint,
        "table": table,
        "count": count,
        "years": years,
        "total_files": len(records),
        "total_size_bytes": sum(record.size_bytes for record in records),
        "per_year_counts": per_year_counts,
        "per_year_total_size_bytes": per_year_total_bytes,
    }

    json_path = output_dir / "gwd30_remote_sizes.json"
    csv_path = output_dir / "gwd30_remote_sizes.csv"
    summary_path = output_dir / "summary.json"

    json_path.write_text(
        json.dumps([asdict(record) for record in records], indent=2),
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["year", "file_name", "relative_path", "size_bytes", "gid"],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return {
        "json": json_path,
        "csv": csv_path,
        "summary": summary_path,
    }


def _run(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    years = resolve_years(args.years, dataset_config_path=args.config)
    _announce(f"resolved years: {', '.join(str(year) for year in years)}")

    records = fetch_gwd30_remote_sizes(
        years=years,
        endpoint=args.endpoint,
        table=args.table,
        count=args.count,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )

    _announce(f"writing manifest files to {args.output_dir}")
    outputs = write_size_manifest(
        records,
        output_dir=args.output_dir,
        years=years,
        endpoint=args.endpoint,
        table=args.table,
        count=args.count,
    )
    _announce(
        f"finished: {len(records)} TIFF(s), csv={outputs['csv']}, json={outputs['json']}"
    )
    return 0


def _main(argv: list[str] | None = None) -> int:
    try:
        return _run(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return code
    except Exception as exc:
        print(f"[gwd30-remote-sizes] fatal: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
