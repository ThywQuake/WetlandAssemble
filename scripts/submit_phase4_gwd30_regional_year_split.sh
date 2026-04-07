#!/bin/bash
# Submit one Phase 4 GWD30 regional SLURM job per year plus one dependent merge job.

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
REGION="${REGION:-pan_trop_subtrop}"
DATASET_ID="${DATASET_ID:-gwd30}"
CPUS="${PHASE4_REGIONAL_CPUS:-1}"
TIME_MIN="${PHASE4_REGIONAL_TIME:-480}"
PARTITION="${PHASE4_REGIONAL_PARTITION:-C064M0256G}"
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
  bash scripts/submit_phase4_gwd30_regional_year_split.sh [options]

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
  --region NAME           Region id passed to run_phase4_regional.py (default: pan_trop_subtrop)
  --dataset-id NAME       Dataset id passed to run_phase4_regional.py (default: gwd30)
  --years Y1,Y2,...       Only submit the selected calendar years
  --cpus N                SLURM CPU count for year jobs and merge job
  --time MINUTES          SLURM walltime in minutes
  --partition NAME        SLURM partition
  --no-skip               Force yearly cache rebuild instead of reusing year caches
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

build_year_script() {
    local year="$1"
    local job_name="phase4-gwd30-region-${REGION}-${year}-${TIMESTAMP}"
    local job_dir="${JOBS_BASE}/${job_name}"
    local job_tmp_dir="${TMP_ROOT}/${job_name}"
    local script="${job_dir}/submit.slurm"
    mkdir -p "${job_dir}" "${job_tmp_dir}"

    local -a run_args=(
        "--dataset-id" "${DATASET_ID}"
        "--region" "${REGION}"
        "--standardized-dir" "${STANDARDIZED_DIR}"
        "--output-root" "${OUTPUT_ROOT}"
        "--start-year" "${year}"
        "--end-year" "${year}"
    )
    if [[ "${SKIP}" -eq 0 ]]; then
        run_args+=("--no-skip")
    fi
    if [[ "${PROGRESS}" -eq 0 ]]; then
        run_args+=("--no-progress")
    fi
    if [[ "${VERBOSE}" -eq 1 ]]; then
        run_args+=("--log-level" "DEBUG")
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
        echo "if [[ ! -f ${REPO}/scripts/run_phase4_regional.py ]]; then"
        echo "  echo 'Bad REPO path: ${REPO}' >&2"
        echo "  exit 1"
        echo "fi"
        echo "if [[ ! -x ${PYTHON_BIN} ]]; then"
        echo "  echo 'Bad PYTHON_BIN path: ${PYTHON_BIN}' >&2"
        echo "  exit 1"
        echo "fi"
        echo
        echo "echo \"=== Phase4 regional year=${year} region=${REGION} dataset=${DATASET_ID} ===\""
        echo 'echo "Start: $(date)"'
        printf '%q scripts/run_phase4_regional.py' "${PYTHON_BIN}"
        local arg
        for arg in "${run_args[@]}"; do
            printf ' %q' "${arg}"
        done
        printf '\n'
        echo 'echo "End: $(date)"'
    } > "${script}"
    chmod +x "${script}"

    printf '%s\t%s\t%s\n' "${job_name}" "${script}" "${job_dir}"
}

build_merge_script() {
    local years_csv="$1"
    local dependency="$2"
    local job_name="phase4-gwd30-region-merge-${REGION}-${TIMESTAMP}"
    local job_dir="${JOBS_BASE}/${job_name}"
    local job_tmp_dir="${TMP_ROOT}/${job_name}"
    local script="${job_dir}/submit.slurm"
    mkdir -p "${job_dir}" "${job_tmp_dir}"

    local -a merge_args=(
        "--dataset-id" "${DATASET_ID}"
        "--region" "${REGION}"
        "--standardized-dir" "${STANDARDIZED_DIR}"
        "--output-root" "${OUTPUT_ROOT}"
        "--start-year" "${YEARS[0]}"
        "--end-year" "${YEARS[${#YEARS[@]}-1]}"
    )
    if [[ "${PROGRESS}" -eq 0 ]]; then
        merge_args+=("--no-progress")
    fi
    if [[ "${VERBOSE}" -eq 1 ]]; then
        merge_args+=("--log-level" "DEBUG")
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
        if [[ -n "${dependency}" ]]; then
            echo "#SBATCH --dependency=afterok:${dependency}"
        fi
        echo
        echo "mkdir -p ${job_tmp_dir}"
        echo "export TMPDIR=${job_tmp_dir}"
        echo "export TMP=${job_tmp_dir}"
        echo "export TEMP=${job_tmp_dir}"
        echo 'export PYTHONUNBUFFERED=1'
        echo
        echo "cd ${REPO} || exit 1"
        echo "if [[ ! -f ${REPO}/scripts/run_phase4_regional.py ]]; then"
        echo "  echo 'Bad REPO path: ${REPO}' >&2"
        echo "  exit 1"
        echo "fi"
        echo "if [[ ! -x ${PYTHON_BIN} ]]; then"
        echo "  echo 'Bad PYTHON_BIN path: ${PYTHON_BIN}' >&2"
        echo "  exit 1"
        echo "fi"
        echo
        echo "echo \"=== Phase4 regional merge region=${REGION} dataset=${DATASET_ID} years=${years_csv} ===\""
        echo 'echo "Start: $(date)"'
        printf '%q scripts/run_phase4_regional.py' "${PYTHON_BIN}"
        local arg
        for arg in "${merge_args[@]}"; do
            printf ' %q' "${arg}"
        done
        printf '\n'
        echo 'echo "End: $(date)"'
    } > "${script}"
    chmod +x "${script}"

    printf '%s\t%s\t%s\n' "${job_name}" "${script}" "${job_dir}"
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
        --region)
            REGION="$2"
            shift 2
            ;;
        --dataset-id)
            DATASET_ID="$2"
            shift 2
            ;;
        --years)
            YEAR_FILTER_CSV="$2"
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
SUMMARY_FILE="${JOBS_BASE}/phase4-gwd30-region-${REGION}-${TIMESTAMP}.tsv"
printf "kind\tyear\tjob_name\tjob_id\tscript\n" > "${SUMMARY_FILE}"

if [[ ! -f "${CONFIG}" ]]; then
    echo "Missing config: ${CONFIG}" >&2
    exit 1
fi
if [[ ! -f "${REPO}/scripts/run_phase4_regional.py" ]]; then
    echo "Missing: ${REPO}/scripts/run_phase4_regional.py" >&2
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

years_csv="$(IFS=,; printf '%s' "${YEARS[*]}")"
echo "Repo:         ${REPO}"
echo "Config:       ${CONFIG}"
echo "Python:       ${PYTHON_BIN}"
echo "Dataset:      ${DATASET_ID}"
echo "Region:       ${REGION}"
echo "Years:        ${years_csv}"
echo "Output root:  ${OUTPUT_ROOT}"
echo "Std dir:      ${STANDARDIZED_DIR}"
echo "Jobs base:    ${JOBS_BASE}"
echo "CPUs:         ${CPUS}"
echo "Time:         ${TIME_MIN}"
echo "Partition:    ${PARTITION}"
echo "Skip:         ${SKIP}"
echo "Progress:     ${PROGRESS}"
echo "Summary TSV:  ${SUMMARY_FILE}"

declare -a JOB_IDS=()
for year in "${YEARS[@]}"; do
    IFS=$'\t' read -r job_name script job_dir < <(build_year_script "${year}")
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        echo "[${REGION}:${year}] dry-run  (time=${TIME_MIN}min, cpus=${CPUS}, partition=${PARTITION})"
        echo "  script: ${script}"
        printf "  cmd:    sbatch %q\n" "${script}"
        printf "year\t%s\t%s\tdry-run\t%s\n" "${year}" "${job_name}" "${script}" >> "${SUMMARY_FILE}"
        continue
    fi

    submit_output="$(sbatch "${script}" 2>&1)"
    job_id="$(extract_job_id "${submit_output}")"
    JOB_IDS+=("${job_id}")
    echo "[${REGION}:${year}] ${job_id}  (time=${TIME_MIN}min, cpus=${CPUS}, partition=${PARTITION})"
    printf "year\t%s\t%s\t%s\t%s\n" "${year}" "${job_name}" "${job_id}" "${script}" >> "${SUMMARY_FILE}"
done

dependency=""
if [[ ${#JOB_IDS[@]} -gt 0 ]]; then
    dependency="$(IFS=:; printf '%s' "${JOB_IDS[*]}")"
fi
IFS=$'\t' read -r merge_job_name merge_script merge_job_dir < <(build_merge_script "${years_csv}" "${dependency}")
if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[${REGION}:merge] dry-run  (time=${TIME_MIN}min, cpus=${CPUS}, partition=${PARTITION})"
    echo "  script: ${merge_script}"
    printf "  cmd:    sbatch %q\n" "${merge_script}"
    printf "merge\t%s\t%s\tdry-run\t%s\n" "${years_csv}" "${merge_job_name}" "${merge_script}" >> "${SUMMARY_FILE}"
else
    merge_submit_output="$(sbatch "${merge_script}" 2>&1)"
    merge_job_id="$(extract_job_id "${merge_submit_output}")"
    echo "[${REGION}:merge] ${merge_job_id}  (time=${TIME_MIN}min, cpus=${CPUS}, partition=${PARTITION})"
    printf "merge\t%s\t%s\t%s\t%s\n" "${years_csv}" "${merge_job_name}" "${merge_job_id}" "${merge_script}" >> "${SUMMARY_FILE}"
fi

echo "Done. Summary written to ${SUMMARY_FILE}"
