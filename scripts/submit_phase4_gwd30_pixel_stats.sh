#!/bin/bash
# Submit one Phase 4 Stage-1 GWD30 pixel-statistics SLURM job per year.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$HOME/repos/WA2}"
STANDARDIZED_DIR="${STANDARDIZED_DIR:-$HOME/Wetland_Assemble/data/standardized}"
OUTPUT_ROOT="${OUTPUT_ROOT:-results/phase4}"
CONFIG="${CONFIG:-}"
TMP_ROOT="${TMP_ROOT:-$HOME/temp}"
JOBS_BASE="${JOBS_BASE:-${TMP_ROOT}/slurm-jobs}"
ACCOUNT="${ACCOUNT:-hpc1506186103}"
QOS="${QOS:-high}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
PYTHON_BIN="${PYTHON_BIN:-}"
AGGREGATION="${AGGREGATION:-monthly}"
WORKER_COUNT="${PHASE4_GWD30_STATS_WORKERS:-1}"
CPUS="${PHASE4_GWD30_STATS_CPUS:-$WORKER_COUNT}"
TIME_MIN="${PHASE4_GWD30_STATS_TIME:-480}"
PARTITION="${PHASE4_GWD30_STATS_PARTITION:-C064M0256G}"
SKIP=1
PROGRESS=1
VERBOSE=0
DRY_RUN=0
YEAR_FILTER_CSV=""
YEAR_FILTERS=()
SUMMARY_FILE=""

usage() {
    cat <<'EOF'
Usage:
  bash scripts/submit_phase4_gwd30_pixel_stats.sh [options]

Options:
  --dry-run               Print generated job scripts but do not submit
  --repo PATH             Override repo path on HPC
  --python-bin PATH       Override Python executable (default: REPO/.venv/bin/python)
  --standardized-dir PATH Override standardized root
  --output-root PATH      Override Phase 4 output root
  --config PATH           Override datasets config path for year discovery
  --tmp-root PATH         Override runtime temp root
  --jobs-base PATH        Override SLURM jobs directory
  --account NAME          Override SLURM account
  --qos NAME              Override SLURM QoS
  --years Y1,Y2,...       Only submit the selected calendar years
  --aggregation MODE      native | monthly | annual (default: monthly)
  --worker-count N        Tile workers for build_phase4_gwd30_pixel_stats.py
  --cpus N                SLURM CPU count
  --time MINUTES          SLURM walltime in minutes
  --partition NAME        SLURM partition
  --no-skip               Force rebuild instead of reusing existing tiles
  --no-progress           Disable progress bars in Python job logs
  --verbose               Pass DEBUG logging to Python script
  -h, --help              Show this message
EOF
}

dataset_block() {
    awk -v dataset="gwd30" '
        BEGIN {capture = 0; in_datasets = 0}
        /^datasets:/ {in_datasets = 1; next}
        in_datasets && /^[^[:space:]]/ {in_datasets = 0}
        in_datasets && $0 ~ "^  " dataset ":" {capture = 1; next}
        capture && $0 ~ "^  [^[:space:]][^:]*:" {exit}
        capture {print}
    ' "${CONFIG}"
}

resolve_gwd30_years() {
    local block
    block="$(dataset_block)"
    if [[ -z "${block}" ]]; then
        return 0
    fi

    local -a discovered_years=()
    while IFS= read -r year; do
        [[ -n "${year}" ]] || continue
        discovered_years+=("${year}")
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

    if [[ ${#YEAR_FILTERS[@]} -eq 0 ]]; then
        printf '%s\n' "${discovered_years[@]}"
        return 0
    fi

    local year
    local selected
    for year in "${discovered_years[@]}"; do
        for selected in "${YEAR_FILTERS[@]}"; do
            if [[ "${year}" == "${selected}" ]]; then
                printf '%s\n' "${year}"
                break
            fi
        done
    done
}

extract_job_id() {
    local submit_output="$1"
    printf '%s\n' "${submit_output}" | awk '{print $NF}'
}

submit_year_task() {
    local year="$1"
    local job_name="phase4-gwd30-pixel-stats-${year}-${TIMESTAMP}"
    local job_dir="${JOBS_BASE}/${job_name}"
    local job_tmp_dir="${TMP_ROOT}/${job_name}"
    local script="${job_dir}/submit.slurm"
    mkdir -p "${job_dir}"
    mkdir -p "${job_tmp_dir}"

    local -a build_args=(
        "--year" "${year}"
        "--standardized-dir" "${STANDARDIZED_DIR}"
        "--output-root" "${OUTPUT_ROOT}"
        "--aggregation" "${AGGREGATION}"
        "--worker-count" "${WORKER_COUNT}"
    )
    if [[ "${SKIP}" -eq 0 ]]; then
        build_args+=("--no-skip")
    fi
    if [[ "${PROGRESS}" -eq 0 ]]; then
        build_args+=("--no-progress")
    fi
    if [[ "${VERBOSE}" -eq 1 ]]; then
        build_args+=("--log-level" "DEBUG")
    fi

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
        echo 'export PYTHONUNBUFFERED=1'
        echo
        echo "cd ${REPO} || exit 1"
        echo 'echo "Repo: $(pwd)"'
        echo "if [[ ! -f ${REPO}/scripts/build_phase4_gwd30_pixel_stats.py ]]; then"
        echo "  echo 'Bad REPO path: ${REPO}' >&2"
        echo "  exit 1"
        echo "fi"
        echo "if [[ ! -x ${PYTHON_BIN} ]]; then"
        echo "  echo 'Bad PYTHON_BIN path: ${PYTHON_BIN}' >&2"
        echo "  exit 1"
        echo "fi"
        echo
        echo "echo \"=== Phase4 GWD30 pixel stats year=${year} aggregation=${AGGREGATION} ===\""
        echo 'echo "Start: $(date)"'
        printf '%q scripts/build_phase4_gwd30_pixel_stats.py' "${PYTHON_BIN}"
        local arg
        for arg in "${build_args[@]}"; do
            printf ' %q' "${arg}"
        done
        printf '\n'
        echo 'echo "End: $(date)"'
    } > "${script}"
    chmod +x "${script}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        echo "[${year}] dry-run  (time=${TIME_MIN}min, cpus=${CPUS}, workers=${WORKER_COUNT}, partition=${PARTITION})"
        echo "  script: ${script}"
        printf "  cmd:    sbatch %q\n" "${script}"
        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
            "${year}" "${job_name}" "dry-run" "${TIME_MIN}" "${CPUS}" "${WORKER_COUNT}" "${script}" \
            >> "${SUMMARY_FILE}"
        return 0
    fi

    local submit_output
    submit_output="$(sbatch "${script}" 2>&1)"
    local job_id
    job_id="$(extract_job_id "${submit_output}")"
    echo "[${year}] ${job_id}  (time=${TIME_MIN}min, cpus=${CPUS}, workers=${WORKER_COUNT}, partition=${PARTITION})"
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
        "${year}" "${job_name}" "${job_id}" "${TIME_MIN}" "${CPUS}" "${WORKER_COUNT}" "${script}" \
        >> "${SUMMARY_FILE}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --repo)
            REPO="$2"
            shift 2
            ;;
        --python-bin)
            PYTHON_BIN="$2"
            shift 2
            ;;
        --standardized-dir)
            STANDARDIZED_DIR="$2"
            shift 2
            ;;
        --output-root)
            OUTPUT_ROOT="$2"
            shift 2
            ;;
        --config)
            CONFIG="$2"
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
        --years)
            YEAR_FILTER_CSV="$2"
            shift 2
            ;;
        --aggregation)
            AGGREGATION="$2"
            shift 2
            ;;
        --worker-count)
            WORKER_COUNT="$2"
            shift 2
            ;;
        --cpus)
            CPUS="$2"
            shift 2
            ;;
        --time)
            TIME_MIN="$2"
            shift 2
            ;;
        --partition)
            PARTITION="$2"
            shift 2
            ;;
        --no-skip)
            SKIP=0
            shift
            ;;
        --no-progress)
            PROGRESS=0
            shift
            ;;
        --verbose)
            VERBOSE=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
        *)
            echo "Unexpected positional argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

case "${AGGREGATION}" in
    native|monthly|annual) ;;
    *)
        echo "Unsupported aggregation: ${AGGREGATION}" >&2
        exit 1
        ;;
esac

if [[ -z "${CONFIG}" ]]; then
    CONFIG="${REPO}/config/datasets.yaml"
fi

if [[ -z "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="${REPO}/.venv/bin/python"
fi

if [[ -n "${YEAR_FILTER_CSV}" ]]; then
    IFS=',' read -r -a YEAR_FILTERS <<< "${YEAR_FILTER_CSV}"
fi

mkdir -p "${JOBS_BASE}"
SUMMARY_FILE="${JOBS_BASE}/phase4-gwd30-pixel-stats-${TIMESTAMP}.tsv"
printf "year\tjob_name\tjob_id\ttime_min\tcpus\tworkers\tscript\n" > "${SUMMARY_FILE}"

if [[ ! -f "${CONFIG}" ]]; then
    echo "Missing config: ${CONFIG}" >&2
    exit 1
fi
if [[ ! -f "${REPO}/scripts/build_phase4_gwd30_pixel_stats.py" ]]; then
    echo "Missing: ${REPO}/scripts/build_phase4_gwd30_pixel_stats.py" >&2
    exit 1
fi

YEARS=()
while IFS= read -r year; do
    [[ -n "${year}" ]] || continue
    YEARS+=("${year}")
done < <(resolve_gwd30_years)
if [[ ${#YEARS[@]} -eq 0 ]]; then
    echo "No GWD30 years selected for submission." >&2
    exit 1
fi

year_csv="$(IFS=,; printf '%s' "${YEARS[*]}")"
echo "Repo:         ${REPO}"
echo "Config:       ${CONFIG}"
echo "Python:       ${PYTHON_BIN}"
echo "Years:        ${year_csv}"
echo "Aggregation:  ${AGGREGATION}"
echo "Output root:  ${OUTPUT_ROOT}"
echo "Std dir:      ${STANDARDIZED_DIR}"
echo "Jobs base:    ${JOBS_BASE}"
echo "Workers:      ${WORKER_COUNT}"
echo "CPUs:         ${CPUS}"
echo "Time:         ${TIME_MIN}"
echo "Partition:    ${PARTITION}"
echo "Skip:         ${SKIP}"
echo "Progress:     ${PROGRESS}"
echo "Summary TSV:  ${SUMMARY_FILE}"

for year in "${YEARS[@]}"; do
    submit_year_task "${year}"
done

echo "Done. Summary written to ${SUMMARY_FILE}"
