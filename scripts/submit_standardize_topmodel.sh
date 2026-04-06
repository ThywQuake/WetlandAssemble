#!/bin/bash
# Submit TOPMODEL standardization job to SLURM.
#
# Usage:
#   bash scripts/submit_standardize_topmodel.sh
#   bash scripts/submit_standardize_topmodel.sh --dry-run
#   bash scripts/submit_standardize_topmodel.sh --years 2016,2017
#   bash scripts/submit_standardize_topmodel.sh --no-split-years

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$HOME/repos/WA2}"
OUTPUT_DIR="${OUTPUT_DIR:-$HOME/Wetland_Assemble/data/standardized}"
CONFIG="${CONFIG:-$REPO/config/datasets.yaml}"
TMP_ROOT="${TMP_ROOT:-$HOME/temp}"
JOBS_BASE="${JOBS_BASE:-${TMP_ROOT}/slurm-jobs}"
ACCOUNT="${ACCOUNT:-hpc1506186103}"
QOS="${QOS:-high}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RESOLUTION="${RESOLUTION:-500}"
PYTHON_BIN="${PYTHON_BIN:-$REPO/.venv/bin/python}"
SKIP_EXISTING=1
VERBOSE=0
DRY_RUN=0
SPLIT_YEARS=1
YEAR_FILTERS=()
YEAR_FILTER_CSV=""

# TOPMODEL specific defaults
TIME_MIN="${TIME_MIN:-240}"
CPUS="${CPUS:-8}"
PARTITION="${PARTITION:-high}"

DATASET="topmodel"

usage() {
    cat <<'EOF'
Usage:
  bash scripts/submit_standardize_topmodel.sh [options]

Options:
  --dry-run               Print generated job script but do not submit
  --resolution METERS     Pass resolution to standardize_datasets.py (default: 500)
  --output-dir PATH       Override output directory
  --config PATH           Override datasets config path
  --repo PATH             Override repo path on HPC
  --python-bin PATH       Override Python executable
  --tmp-root PATH         Override runtime temp root
  --jobs-base PATH        Override SLURM jobs directory
  --account NAME          Override SLURM account
  --qos NAME              Override SLURM QoS
  --partition NAME        Override SLURM partition (default: high)
  --time MINUTES          Override walltime in minutes (default: 240)
  --cpus N                Override CPU count (default: 8)
  --split-years           Split into one job per year (default)
  --no-split-years        Keep single job for all years
  --years Y1,Y2,...       Only submit selected calendar years
  --verbose               Pass -v for DEBUG logs
  --no-skip-existing      Do not pass --skip-existing
  -h, --help              Show this message

Environment variables:
  REPO, OUTPUT_DIR, CONFIG, TMP_ROOT, JOBS_BASE, ACCOUNT, QOS
  TIME_MIN, CPUS, PARTITION
EOF
}

discover_topmodel_years() {
    # Discover years from TOPMODEL config
    local block
    block="$(awk '
        /^  topmodel:/ {capture = 1; next}
        capture && /^  [^[:space:]][^:]*:/ {exit}
        capture {print}
    ' "${CONFIG}")"

    if [[ -z "${block}" ]]; then
        return 0
    fi

    # Try explicit years first
    local -a explicit_years=()
    while IFS= read -r year; do
        [[ -n "${year}" ]] || continue
        explicit_years+=("${year}")
    done < <(
        printf '%s\n' "${block}" | awk '
            /^    years:/ {capture = 1; next}
            capture && /^      - / {
                value = $0
                sub(/^      - /, "", value)
                gsub(/"/, "", value)
                gsub(/\047/, "", value)
                print value
                next
            }
            capture {exit}
        '
    )

    if [[ ${#explicit_years[@]} -gt 0 ]]; then
        printf '%s\n' "${explicit_years[@]}"
        return 0
    fi

    # Try start/end range
    local start_year="" end_year=""
    start_year="$(printf '%s\n' "${block}" | sed -n "s/^      start: *['\\\"]\\{0,1\\}\\([0-9]\\{4\\}\\).*/\\1/p" | head -n1)"
    end_year="$(printf '%s\n' "${block}" | sed -n "s/^      end: *['\\\"]\\{0,1\\}\\([0-9]\\{4\\}\\).*/\\1/p" | head -n1)"

    if [[ -n "${start_year}" && -n "${end_year}" ]]; then
        seq "${start_year}" "${end_year}"
        return 0
    fi

    # Discover from filesystem
    local topmodel_path=""
    topmodel_path="$(printf '%s\n' "${block}" | sed -n "s/^    path: *['\\\"]\\{0,1\\}\\(.*\\)['\\\"]\\{0,1\\}$/\\1/p" | head -n1)"

    if [[ -n "${topmodel_path}" && -d "${topmodel_path}" ]]; then
        find "${topmodel_path}" -type f -name 'fwet_*_reso025_*.nc' -print 2>/dev/null \
            | sed -n 's/.*_\([0-9][0-9][0-9][0-9]\)\.nc$/\1/p' \
            | sort -nu
    fi
}

resolve_years() {
    local -a discovered_years=()
    while IFS= read -r year; do
        [[ -n "${year}" ]] || continue
        discovered_years+=("${year}")
    done < <(discover_topmodel_years)

    if [[ ${#discovered_years[@]} -eq 0 ]]; then
        echo "Warning: No TOPMODEL years discovered, submitting without --years" >&2
        return 0
    fi

    if [[ ${#YEAR_FILTERS[@]} -eq 0 ]]; then
        printf '%s\n' "${discovered_years[@]}"
        return 0
    fi

    local year selected
    for year in "${discovered_years[@]}"; do
        for selected in "${YEAR_FILTERS[@]}"; do
            if [[ "${year}" == "${selected}" ]]; then
                printf '%s\n' "${year}"
                break
            fi
        done
    done
}

submit_task() {
    local task_year="$1"
    local task_label="all"
    local job_name="std-topmodel-${TIMESTAMP}"

    if [[ -n "${task_year}" ]]; then
        task_label="${task_year}"
        job_name="std-topmodel-${task_year}-${TIMESTAMP}"
    fi

    local job_dir="${JOBS_BASE}/${job_name}"
    local job_tmp_dir="${TMP_ROOT}/${job_name}"
    local metadata_path="${job_dir}/metadata.json"

    mkdir -p "${job_dir}" "${job_tmp_dir}"

    local -a standardize_args=(
        "--datasets" "topmodel"
        "--output-dir" "${OUTPUT_DIR}"
        "--config" "${CONFIG}"
        "--resolution" "${RESOLUTION}"
        "--metadata-path" "${metadata_path}"
    )

    if [[ -n "${task_year}" ]]; then
        standardize_args+=("--years" "${task_year}")
    fi

    if [[ "${SKIP_EXISTING}" -eq 1 ]]; then
        standardize_args+=("--skip-existing")
    fi

    if [[ "${VERBOSE}" -eq 1 ]]; then
        standardize_args+=("-v")
    fi

    local script="${job_dir}/submit.slurm"
    {
        echo '#!/bin/bash'
        echo "#SBATCH -A ${ACCOUNT}"
        echo "#SBATCH --partition=${PARTITION}"
        echo "#SBATCH --qos=${QOS}"
        echo "#SBATCH -J ${job_name}"
        echo '#SBATCH --nodes=1'
        echo "#SBATCH -c ${CPUS}"
        echo "#SBATCH --time=${TIME_MIN}"
        echo "#SBATCH --chdir=${job_dir}"
        echo '#SBATCH --output=job.%j.out'
        echo '#SBATCH --error=job.%j.err'
        echo '#SBATCH --get-user-env'
        echo
        echo "mkdir -p ${job_tmp_dir}"
        echo "export TMPDIR=${job_tmp_dir}"
        echo "export TMP=${job_tmp_dir}"
        echo "export TEMP=${job_tmp_dir}"
        echo "export WA_STANDARDIZE_WORKERS=${CPUS}"
        echo
        echo "cd ${REPO} || exit 1"
        echo 'echo "Repo: $(pwd)"'
        echo "if [[ ! -f ${REPO}/scripts/standardize_datasets.py ]]; then"
        echo "  echo 'Bad REPO path: ${REPO}' >&2"
        echo "  exit 1"
        echo "fi"
        echo "if [[ ! -x ${PYTHON_BIN} ]]; then"
        echo "  echo 'Bad PYTHON_BIN: ${PYTHON_BIN}' >&2"
        echo "  exit 1"
        echo "fi"
        echo
        echo "echo \"=== Standardizing TOPMODEL (${task_label}) ===\""
        echo 'echo "Start: $(date)"'
        printf '%q scripts/standardize_datasets.py' "${PYTHON_BIN}"
        local arg
        for arg in "${standardize_args[@]}"; do
            printf ' %q' "${arg}"
        done
        printf '\n'
        echo 'echo "End: $(date)"'
    } > "${script}"

    chmod +x "${script}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        echo "[TOPMODEL:${task_label}] dry-run (time=${TIME_MIN}min, cpus=${CPUS}, partition=${PARTITION})"
        echo "  script: ${script}"
        printf "  cmd:    sbatch %q\n" "${script}"
        return 0
    fi

    local job_id
    job_id="$(sbatch "${script}" 2>&1)"
    echo "[TOPMODEL:${task_label}] ${job_id} (time=${TIME_MIN}min, cpus=${CPUS}, partition=${PARTITION})"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --resolution)
            RESOLUTION="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --repo)
            REPO="$2"
            shift 2
            ;;
        --python-bin)
            PYTHON_BIN="$2"
            shift 2
            ;;
        --tmp-root)
            TMP_ROOT="$2"
            shift 2
            ;;
        --jobs-base)
            JOBS_BASE="$2"
            shift 2
            ;;
        --account)
            ACCOUNT="$2"
            shift 2
            ;;
        --qos)
            QOS="$2"
            shift 2
            ;;
        --partition)
            PARTITION="$2"
            shift 2
            ;;
        --time)
            TIME_MIN="$2"
            shift 2
            ;;
        --cpus)
            CPUS="$2"
            shift 2
            ;;
        --split-years)
            SPLIT_YEARS=1
            shift
            ;;
        --no-split-years)
            SPLIT_YEARS=0
            shift
            ;;
        --years)
            YEAR_FILTER_CSV="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=1
            shift
            ;;
        --no-skip-existing)
            SKIP_EXISTING=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

# Parse year filter
if [[ -n "${YEAR_FILTER_CSV}" ]]; then
    IFS=',' read -r -a YEAR_FILTERS <<< "${YEAR_FILTER_CSV}"
    CLEANED=()
    for y in "${YEAR_FILTERS[@]}"; do
        y="${y//[[:space:]]/}"
        [[ -n "${y}" ]] || continue
        CLEANED+=("${y}")
    done
    YEAR_FILTERS=("${CLEANED[@]}")
fi

# Validate paths
if [[ ! -f "${REPO}/scripts/standardize_datasets.py" ]]; then
    echo "Missing: ${REPO}/scripts/standardize_datasets.py" >&2
    echo "Pass --repo /lustre/home/2200013429/repos/WA2" >&2
    exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Python not found: ${PYTHON_BIN}" >&2
    exit 1
fi

mkdir -p "${TMP_ROOT}" "${JOBS_BASE}"

echo "=== TOPMODEL Standardization ==="
echo "Repo:         ${REPO}"
echo "Python:       ${PYTHON_BIN}"
echo "Output dir:   ${OUTPUT_DIR}"
echo "Config:       ${CONFIG}"
echo "Tmp root:     ${TMP_ROOT}"
echo "Resolution:   ${RESOLUTION}"
echo "Time:         ${TIME_MIN} min"
echo "CPUs:         ${CPUS}"
echo "Partition:    ${PARTITION}"
echo "Split years:  ${SPLIT_YEARS}"
if [[ ${#YEAR_FILTERS[@]} -gt 0 ]]; then
    echo "Year filter:  ${YEAR_FILTERS[*]}"
fi
echo "Skip exists:  ${SKIP_EXISTING}"
echo "Verbose:      ${VERBOSE}"
echo "Dry run:      ${DRY_RUN}"
echo ""

# Discover years and submit
TASK_YEARS=()
if [[ "${SPLIT_YEARS}" -eq 1 ]]; then
    while IFS= read -r year; do
        [[ -n "${year}" ]] || continue
        TASK_YEARS+=("${year}")
    done < <(resolve_years)
fi

if [[ "${SPLIT_YEARS}" -eq 1 && ${#TASK_YEARS[@]} -gt 0 ]]; then
    echo "[TOPMODEL] Split into ${#TASK_YEARS[@]} year task(s): ${TASK_YEARS[*]}"
    for TASK_YEAR in "${TASK_YEARS[@]}"; do
        submit_task "${TASK_YEAR}"
    done
else
    echo "[TOPMODEL] Submitting unsplit task"
    submit_task ""
fi

echo ""
echo "Monitor with: squeue -u $(whoami)"
