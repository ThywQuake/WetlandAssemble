from __future__ import annotations

import argparse
import base64
import csv
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: The 'requests' library is required. Install it using: uv pip install requests")
    sys.exit(1)

try:
    import rsa
except ImportError:
    print("Error: The 'rsa' library is required. Install it using: uv pip install rsa")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        print("Processing... (Hint: 'uv pip install tqdm' for a visual progress bar)")
        return iterable

# ==========================================
# CONFIGURATION
# ==========================================
AUTH_URL = "https://data-starcloud.pcl.ac.cn/starcloud/api/user/authenticate"
API_URL = "https://data-starcloud.pcl.ac.cn/starcloud/api/file/downloadResource"
BASE_PREFIX = "shared-dataset/Wetland/GWD30"
DEFAULT_MAX_RETRIES = 3
DEFAULT_DOWNLOAD_TIMEOUT = 180

# Public key for RSA encryption (from auth_infos.txt)
PUBLIC_KEY_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvrzz4DGWHc6YmK0BZ30LMqZv"
    "WTLOsuIzPJn9LrJ++5416UwqpnnR5DxI4NOAdwwAOv7aOdiZ6ny5u8BX5potv+cB3evrc"
    "pw5HbxSbj1kUzfOv4VCnGSdPMRnx/i3DCaQN1ubliJrm/jfGBEVioTNkT+iNxcZZYxazg"
    "P1PHJOpmUwu7LME+zdGSB+y0MIZasmKi6aVFBIHug83ku0lNpA+hdWTJu+Unsl6cD58wf"
    "7fSF3zLbb9Cmy/kg+qcS0QzzBajSXh1UuRm+4KuQZfDRDuIagICtXvrY/u2Ow3Kdw4YGqE"
    "Me+TLiuxFoCQO9smGCOi9sCFAVrC3DaGPhGYT422QIDAQAB"
)

# Global state for Token
CURRENT_TOKEN = None
TOKEN_LOCK = threading.Lock()
# ==========================================


@dataclass(frozen=True)
class DownloadTask:
    local_path: Path
    object_key: str
    expected_size_bytes: int | None = None


def _looks_like_tiff(file_name: str) -> bool:
    return file_name.lower().endswith((".tif", ".tiff"))


def _local_file_matches_expected_size(local_path: Path, expected_size_bytes: int | None) -> bool:
    """Return True when the existing local file already matches the available size signal."""

    if not local_path.exists():
        return False
    try:
        actual_size = local_path.stat().st_size
    except OSError:
        return False
    if expected_size_bytes is None:
        return actual_size > 0
    return actual_size == expected_size_bytes


def _verify_downloaded_file(local_path: Path, expected_size_bytes: int | None) -> str | None:
    """Return None when the downloaded file passes size verification, otherwise an error."""

    try:
        actual_size = local_path.stat().st_size
    except OSError as exc:
        return f"failed to stat downloaded file: {exc}"

    if expected_size_bytes is not None and actual_size != expected_size_bytes:
        return (
            f"downloaded size mismatch: expected {expected_size_bytes}, "
            f"got {actual_size}"
        )
    if actual_size <= 0:
        return "downloaded file is empty"
    return None


def _response_content_length(response) -> int | None:
    """Extract Content-Length from a urllib response when available."""

    content_length = None
    if hasattr(response, "getheader"):
        content_length = response.getheader("Content-Length")
    elif hasattr(response, "headers"):
        content_length = response.headers.get("Content-Length")
    if content_length in {None, ""}:
        return None
    try:
        return int(content_length)
    except (TypeError, ValueError):
        return None


def _build_object_key_from_relative_path(relative_path: str) -> str:
    normalized = relative_path.strip().replace("\\", "/").lstrip("/")
    return f"{BASE_PREFIX}/{normalized}"


def _download_task_from_csv_row(
    row: dict,
) -> DownloadTask | None:
    """Build one download task from a mismatch CSV row."""

    relative_path = str(row.get("relative_path", "")).strip()
    absolute_path = str(row.get("absolute_path", "")).strip()
    file_name = str(row.get("file_name", "")).strip()
    status = str(row.get("status", "")).strip()

    if status and status not in {"missing_file", "size_mismatch", "stat_failed"}:
        return None

    if relative_path:
        if not _looks_like_tiff(relative_path):
            return None
    elif file_name:
        if not _looks_like_tiff(file_name):
            return None
    else:
        return None

    if absolute_path:
        local_path = Path(absolute_path)
    elif relative_path:
        local_path = Path(relative_path)
    else:
        return None

    if relative_path:
        object_key = _build_object_key_from_relative_path(relative_path)
    else:
        year_dir = local_path.parent.name
        object_key = _build_object_key_from_relative_path(f"{year_dir}/{local_path.name}")

    expected_size_raw = str(row.get("expected_size_bytes", "")).strip()
    expected_size_bytes = int(expected_size_raw) if expected_size_raw else None
    return DownloadTask(
        local_path=local_path,
        object_key=object_key,
        expected_size_bytes=expected_size_bytes,
    )


def load_download_tasks(input_path: Path) -> tuple[list[DownloadTask], int]:
    """Load download tasks from a legacy txt list or a mismatch CSV."""

    download_tasks: list[DownloadTask] = []
    already_downloaded = 0
    seen_paths = set()

    if input_path.suffix.lower() == ".csv":
        with open(input_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            required_columns = {"relative_path", "absolute_path", "expected_size_bytes"}
            if reader.fieldnames is None or not required_columns.issubset(set(reader.fieldnames)):
                raise ValueError(
                    f"CSV file must contain columns: {', '.join(sorted(required_columns))}. "
                    f"Got: {reader.fieldnames}"
                )
            for row in reader:
                task = _download_task_from_csv_row(row)
                if task is None:
                    continue
                resolved_local_path = task.local_path.expanduser()
                path_key = str(resolved_local_path)
                if path_key in seen_paths:
                    continue
                seen_paths.add(path_key)
                if _local_file_matches_expected_size(
                    resolved_local_path,
                    task.expected_size_bytes,
                ):
                    already_downloaded += 1
                    continue
                download_tasks.append(
                    DownloadTask(
                        local_path=resolved_local_path,
                        object_key=task.object_key,
                        expected_size_bytes=task.expected_size_bytes,
                    )
                )
            return download_tasks, already_downloaded

    with open(input_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            local_path = Path(line).expanduser()
            path_key = str(local_path)
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)

            if _local_file_matches_expected_size(local_path, None):
                already_downloaded += 1
                continue

            year_dir = local_path.parent.name
            filename = local_path.name
            object_key = _build_object_key_from_relative_path(
                f"{year_dir}/{filename}"
            )

            download_tasks.append(
                DownloadTask(local_path=local_path, object_key=object_key)
            )

    return download_tasks, already_downloaded

def fetch_new_token():
    """Fetch a new Bearer token using RSA encryption for authentication."""
    print("\n[Auth] Fetching new Bearer Token...")
    try:
        pub_key_der = base64.b64decode(PUBLIC_KEY_B64)
        pub_key = rsa.PublicKey.load_pkcs1_openssl_der(pub_key_der)

        payload = {
            "account": "thywquake@stu.pku.edu.cn",
            "password": "362525cscPL,,,",
            "rememberMe": True
        }
        
        payload_str = json.dumps(payload)
        encrypted_bytes = rsa.encrypt(payload_str.encode('utf-8'), pub_key)
        encrypted_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')
        
        response = requests.post(
            AUTH_URL,
            headers={"Content-Type": "application/json"},
            json={"key": encrypted_b64},
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("success") and "data" in data and "token" in data["data"]:
            token = data["data"]["token"]
            print("[Auth] Successfully fetched new Token.")
            return token
        else:
            raise ValueError(f"Auth failed: {data}")
    except Exception as e:
        print(f"[Auth Error] Failed to fetch token: {e}")
        return None

def get_valid_token(force_refresh=False):
    """Get the current token, refreshing it if necessary or forced."""
    global CURRENT_TOKEN
    with TOKEN_LOCK:
        if CURRENT_TOKEN is None or force_refresh:
            new_token = fetch_new_token()
            if new_token:
                CURRENT_TOKEN = new_token
            else:
                if not CURRENT_TOKEN:
                    raise RuntimeError("Cannot proceed without a valid token.")
        return CURRENT_TOKEN

def get_headers(token):
    return {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Origin": "https://data-starcloud.pcl.ac.cn",
        "Referer": "https://data-starcloud.pcl.ac.cn/iearthdata/map?id=60",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/145.0.0.0 Safari/537.36"
            ),
    }

def get_signed_url(object_key, token):
    """Fetch the signed URL via the data-starcloud API."""
    payload = {
        "objectKey": object_key,
        "resourceId": "60",
        "userAccount": "Thyw",
        "userId": "8671",
        "country": "Singapore",
        "resourceType": "REMOTE_SENSING"
    }
    
    headers = get_headers(token)
    response = requests.post(API_URL, headers=headers, json=payload, timeout=10)
    
    # Check for 401 Unauthorized to trigger a token refresh
    if response.status_code == 401:
        raise PermissionError("401 Unauthorized")
        
    response.raise_for_status()
    data = response.json()
    
    if data.get("code") == 401 or "Token" in str(data.get("msg", "")):
        raise PermissionError("Token expired in API response payload")
        
    if "signedUrl" in data:
        return data["signedUrl"]
    else:
        raise ValueError(f"API responded but did not contain 'signedUrl': {data}")

def download_file(
    task: DownloadTask,
    max_retries: int = DEFAULT_MAX_RETRIES,
    download_timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
) -> tuple[Path, bool, str]:
    local_path = task.local_path
    object_key = task.object_key
    expected_size_bytes = task.expected_size_bytes
    temp_path = local_path.with_name(f"{local_path.name}.part")
    
    last_error = ""
    for attempt in range(max_retries):
        try:
            # 1. Get current token
            token = get_valid_token()
            
            # 2. Fetch fresh signed URL from API
            url = get_signed_url(object_key, token)
            
            # 3. Download the file
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.unlink(missing_ok=True)
            with urllib.request.urlopen(req, timeout=download_timeout) as response, open(
                temp_path,
                'wb',
            ) as out_file:
                remote_content_length = _response_content_length(response)
                if (
                    expected_size_bytes is not None
                    and remote_content_length is not None
                    and remote_content_length != expected_size_bytes
                ):
                    raise ValueError(
                        "response Content-Length mismatch: "
                        f"expected {expected_size_bytes}, got {remote_content_length}"
                    )
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    out_file.write(chunk)
            
            # 4. Verify size immediately before this worker moves on
            verification_error = _verify_downloaded_file(temp_path, expected_size_bytes)
            if verification_error is None:
                temp_path.replace(local_path)
                return local_path, True, "Success"
            temp_path.unlink(missing_ok=True)
            print(
                f"\n[Retry] {local_path.name}: {verification_error}. "
                f"Re-downloading... (Attempt {attempt+1}/{max_retries})"
            )
            last_error = verification_error
            time.sleep(min(30, 5 * (attempt + 1)))
                
        except PermissionError as pe:
            # Token expired or unauthorized, force refresh for the next attempt
            logger_msg = (
                f"Token expired for {local_path.name}, refreshing... "
                f"(Attempt {attempt+1}/{max_retries})"
            )
            print(f"\n[Retry] {logger_msg}")
            get_valid_token(force_refresh=True)
            last_error = str(pe)
            time.sleep(2)
            
        except requests.exceptions.HTTPError as he:
            # Handle 500 Server Error specifically as requested
            status_code = he.response.status_code if he.response is not None else 0
            if status_code == 500:
                wait_time = 10
                print(
                    f"\n[Retry] 500 Server Error for {local_path.name}. "
                    f"Waiting {wait_time}s and regenerating token... "
                    f"(Attempt {attempt+1}/{max_retries})"
                )
                time.sleep(wait_time)
                get_valid_token(force_refresh=True)
                last_error = f"500 Server Error: {he}"
            else:
                temp_path.unlink(missing_ok=True)
                return local_path, False, f"HTTP Error {status_code}: {he}"
                
        except Exception as e:
            temp_path.unlink(missing_ok=True)
            # For other unexpected errors, retry a few times then fail
            print(f"\n[Error] {local_path.name}: {e}. Retrying...")
            last_error = str(e)
            time.sleep(min(30, 5 * (attempt + 1)))
            
    return local_path, False, f"Failed after {max_retries} retries. Last error: {last_error}"

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Batch re-downloader via Peng Cheng Lab API with Auto Token Refresh."
        ),
    )
    parser.add_argument(
        "corrupted_list",
        help="Path to legacy corrupted_files_list.txt or mismatch CSV generated from size checks",
    )
    parser.add_argument("--workers", type=int, default=16, help="Number of concurrent downloads")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Retry count per file when the API or downloaded size is wrong.",
    )
    parser.add_argument(
        "--download-timeout",
        type=int,
        default=DEFAULT_DOWNLOAD_TIMEOUT,
        help="Per-file download timeout in seconds.",
    )
    
    args = parser.parse_args()

    corrupted_path = Path(args.corrupted_list)
    if not corrupted_path.exists():
        print(f"Error: Corrupted list not found: {corrupted_path}")
        sys.exit(1)

    print("Parsing recovery input...")
    download_tasks, already_downloaded = load_download_tasks(corrupted_path)

    if already_downloaded > 0:
        print(f"Skipped {already_downloaded} files that are already successfully downloaded.")
    print(f"Prepared {len(download_tasks)} files for API-based download.")
    if not download_tasks:
        sys.exit(0)

    # Initialize Token before starting threads
    get_valid_token(force_refresh=True)

    print(f"\nStarting concurrent download with {args.workers} workers...")
    success_count = 0
    failed_tasks = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_task = {
            executor.submit(
                download_file,
                task,
                args.max_retries,
                args.download_timeout,
            ): task
            for task in download_tasks
        }
        
        for future in tqdm(
            as_completed(future_to_task),
            total=len(download_tasks),
            desc="Downloading",
            unit="file",
        ):
            path, success, msg = future.result()
            if success:
                success_count += 1
            else:
                failed_tasks.append((path.name, msg))

    print("\n--- Download Summary ---")
    print(f"Successfully recovered: {success_count} / {len(download_tasks)}")
    
    if failed_tasks:
        print(f"Failed to recover {len(failed_tasks)} files.")
        with open("failed_recovery_list.txt", "w") as f:
            for fname, msg in failed_tasks:
                f.write(f"{fname}: {msg}\n")
        print("See 'failed_recovery_list.txt' for details.")

if __name__ == "__main__":
    main()
