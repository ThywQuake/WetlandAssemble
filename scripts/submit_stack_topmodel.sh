#!/bin/bash
# Submit TOPMODEL stacking job to SLURM (no reprojection, native 0.25° grid).
#
# Usage:
#   bash scripts/submit_stack_topmodel.sh
#   bash scripts/submit_stack_topmodel.sh --dry-run
#   bash scripts/submit_stack_topmodel.sh --years 2016,2017

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
PYTHON_BIN="${PYTHON_BIN:-$REPO/.venv/bin/python}"
SKIP_EXISTING=1
VERBOSE=0
DRY_RUN=0
SPLIT_YEARS=1
YEAR_FILTER_CSV=""
YEAR_FILTERS=()

# TOPMODEL defaults
TIME_MIN="${TIME_MIN:-120}"
CPUS="${CPUS:-4}"
PARTITION="${PARTITION:-high}"

DATASET="topmodel"

usage() {
    cat <<'EOF'
Usage:
  bash scripts/submit_stack_topmodel.sh [options]

Options:
  --dry-run               Print generated job script but do not submit
  --output-dir PATH       Override output directory
  --config PATH           Override datasets config path
  --repo PATH             Override repo path on HPC
  --python-bin PATH       Override Python executable
  --tmp-root PATH         Override runtime temp root
  --jobs-base PATH        Override SLURM jobs directory
  --account NAME          Override SLURM account
  --qos NAME              Override SLURM QoS
  --partition NAME        Override SLURM partition (default: high)
  --time MINUTES          Override walltime in minutes (default: 120)
  --cpus N                Override CPU count (default: 4)
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
    local block
    block="$(awk '
        /^  topmodel:/ {capture = 1; next}
        capture && /^  [^[:space:]][^:]*:/ {exit}
        capture {print}
    ' "${CONFIG}")"

    if [[ -z "${block}" ]]; then
        return 0
    fi

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

    local start_year="" end_year=""
    start_year="$(printf '%s\n' "${block}" | sed -n "s/^      start: *['\\\"]\\{0,1\\}\\([0-9]\\{4\\}\\).*/\\1/p" | head -n1)"
    end_year="$(printf '%s\n' "${block}" | sed -n "s/^      end: *['\\\"]\\{0,1\\}\\([0-9]\\{4\\}\\).*/\\1/p" | head -n1)"

    if [[ -n "${start_year}" && -n "${end_year}" ]]; then
        seq "${start_year}" "${end_year}"
        return 0
    fi

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
        echo "Warning: No TOPMODEL years discovered" >&2
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
    local job_name="stack-topmodel-${TIMESTAMP}"

    if [[ -n "${task_year}" ]]; then
        task_label="${task_year}"
        job_name="stack-topmodel-${task_year}-${TIMESTAMP}"
    fi

    local job_dir="${JOBS_BASE}/${job_name}"
    local job_tmp_dir="${TMP_ROOT}/${job_name}"

    mkdir -p "${job_dir}" "${job_tmp_dir}"

    local -a stack_args=(
        "--output-dir" "${OUTPUT_DIR}"
        "--config" "${CONFIG}"
    )

    if [[ -n "${task_year}" ]]; then
        stack_args+=("--years" "${task_year}")
    fi

    if [[ "${SKIP_EXISTING}" -eq 1 ]]; then
        stack_args+=("--skip-existing")
    fi

    if [[ "${VERBOSE}" -eq 1 ]]; then
        stack_args+=("-v")
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
        echo
        echo "cd ${REPO} || exit 1"
        echo 'echo "Repo: $(pwd)"'
        echo "if [[ ! -f ${REPO}/scripts/stack_topmodel.py ]]; then"
        echo "  echo 'Bad REPO path: ${REPO}' >&2"
        echo "  exit 1"
        echo "fi"
        echo "if [[ ! -x ${PYTHON_BIN} ]]; then"
        echo "  echo 'Bad PYTHON_BIN: ${PYTHON_BIN}' >&2"
        echo "  exit 1"
        echo "fi"
        echo
        echo "echo \"=== Stacking TOPMODEL (${task_label}) ===\""
        echo 'echo "Start: $(date)"'
        printf '%q scripts/stack_topmodel.py' "${PYTHON_BIN}"
        local arg
        for arg in "${stack_args[@]}"; do
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

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
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

if [[ ! -f "${REPO}/scripts/stack_topmodel.py" ]]; then
    echo "Missing: ${REPO}/scripts/stack_topmodel.py" >&2
    exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Python not found: ${PYTHON_BIN}" >&2
    exit 1
fi

mkdir -p "${TMP_ROOT}" "${JOBS_BASE}"

echo "=== TOPMODEL Stacking (Native 0.25°, No Reprojection) ==="
echo "Repo:         ${REPO}"
echo "Python:       ${PYTHON_BIN}"
echo "Output dir:   ${OUTPUT_DIR}"
echo "Config:       ${CONFIG}"
echo "Tmp root:     ${TMP_ROOT}"
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
