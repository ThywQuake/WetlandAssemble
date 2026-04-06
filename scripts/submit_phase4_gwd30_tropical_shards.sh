#!/bin/bash
# Submit sharded Phase 4 GWD30 tropical tile-cache jobs plus one dependent reduce job per year.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$HOME/repos/WA2}"
STANDARDIZED_DIR="${STANDARDIZED_DIR:-$HOME/Wetland_Assemble/data/standardized}"
OUTPUT_ROOT="${OUTPUT_ROOT:-results/phase4}"
PHASE36_CACHE_DIR="${PHASE36_CACHE_DIR:-results/cache/phase3_6}"
PHASE36_MASK_PATH="${PHASE36_MASK_PATH:-}"
PHASE36_MASK_YEAR="${PHASE36_MASK_YEAR:-2016}"
CONFIG="${CONFIG:-config/datasets.yaml}"
TMP_ROOT="${TMP_ROOT:-$HOME/temp}"
JOBS_BASE="${JOBS_BASE:-${TMP_ROOT}/slurm-jobs}"
ACCOUNT="${ACCOUNT:-hpc1506186103}"
QOS="${QOS:-high}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
PYTHON_BIN="${PYTHON_BIN:-}"
SKIP=1
VERBOSE=0
DRY_RUN=0
TASK_LISTS="${PHASE4_GWD30_TASK_LISTS:-16}"
TASK_CPUS="${PHASE4_GWD30_TASK_CPUS:-4}"
TASK_TIME="${PHASE4_GWD30_TASK_TIME:-480}"
TASK_PARTITION="${PHASE4_GWD30_TASK_PARTITION:-C064M0256G}"
REDUCE_CPUS="${PHASE4_GWD30_REDUCE_CPUS:-4}"
REDUCE_TIME="${PHASE4_GWD30_REDUCE_TIME:-120}"
REDUCE_PARTITION="${PHASE4_GWD30_REDUCE_PARTITION:-C064M0256G}"
YEAR_FILTER_CSV=""
YEAR_FILTERS=()

usage() {
    cat <<'EOF'
Usage:
  bash scripts/submit_phase4_gwd30_tropical_shards.sh [options]

Options:
  --dry-run               Print generated job scripts but do not submit
  --repo PATH             Override repo path on HPC
  --python-bin PATH       Override Python executable (default: REPO/.venv/bin/python)
  --standardized-dir PATH Override standardized root
  --output-root PATH      Override Phase 4 output root
  --phase36-cache-dir PATH
  --phase36-mask-path PATH
  --phase36-mask-year Y
  --config PATH           Override datasets config path for year discovery
  --tmp-root PATH         Override runtime temp root
  --jobs-base PATH        Override SLURM jobs directory
  --account NAME          Override SLURM account
  --qos NAME              Override SLURM QoS
  --years Y1,Y2,...       Only submit the selected calendar years
  --task-lists N          Number of manifest-list tasks per year (default: 16)
  --task-cpus N           CPUs per task job (default: 4)
  --task-time MINUTES     Walltime per task job (default: 480)
  --task-partition NAME   Partition for task jobs
  --reduce-cpus N         CPUs for reduce job (default: 4)
  --reduce-time MINUTES   Walltime for reduce job (default: 120)
  --reduce-partition NAME Partition for reduce job
  --no-skip               Force shard tasks to recompute partials
  --verbose               Pass DEBUG logging to Python scripts
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

manifest_lists_dir() {
    local year="$1"
    printf '%s/cache/gwd30/full_tropics/gwd30_%s/manifest_lists' "${OUTPUT_ROOT}" "${year}"
}

partials_dir() {
    local year="$1"
    printf '%s/cache/gwd30/full_tropics/gwd30_%s/partials' "${OUTPUT_ROOT}" "${year}"
}

build_manifest_lists_for_year() {
    local year="$1"
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        return 0
    fi

    local build_cmd=(
        "${PYTHON_BIN}" "scripts/build_phase4_gwd30_shard_lists.py"
        "--year" "${year}"
        "--task-count" "${TASK_LISTS}"
        "--standardized-dir" "${STANDARDIZED_DIR}"
        "--output-root" "${OUTPUT_ROOT}"
    )
    if [[ "${VERBOSE}" -eq 1 ]]; then
        build_cmd+=("--log-level" "DEBUG")
    fi
    (cd "${REPO}" && "${build_cmd[@]}")
}

count_manifest_lists_for_year() {
    local year="$1"
    local list_dir
    list_dir="$(manifest_lists_dir "${year}")"
    if [[ ! -d "${list_dir}" ]]; then
        echo 0
        return 0
    fi
    find "${list_dir}" -maxdepth 1 -name 'manifest_list_*.txt' | wc -l | tr -d ' '
}

write_task_script() {
    local year="$1"
    local script_path="$2"
    local job_name="$3"
    local job_tmp_dir="$4"
    local list_count="$5"
    local list_dir
    list_dir="$(manifest_lists_dir "${year}")"
    {
        echo '#!/bin/bash'
        echo "#SBATCH -A ${ACCOUNT}"
        echo "#SBATCH --partition=${TASK_PARTITION}"
        echo "#SBATCH --qos=${QOS}"
        echo "#SBATCH -J ${job_name}"
        echo '#SBATCH --nodes=1'
        echo "#SBATCH -c ${TASK_CPUS}"
        echo "#SBATCH --time=${TASK_TIME}"
        echo "#SBATCH --array=0-$((list_count - 1))"
        echo "#SBATCH --chdir=$(dirname "${script_path}")"
        echo '#SBATCH --output=job.%A_%a.out'
        echo '#SBATCH --error=job.%A_%a.err'
        echo '#SBATCH --get-user-env'
        echo
        echo 'TASK_TMPDIR="'"${job_tmp_dir}"'/task_${SLURM_ARRAY_TASK_ID}"'
        echo 'mkdir -p "${TASK_TMPDIR}"'
        echo 'export TMPDIR="${TASK_TMPDIR}"'
        echo 'export TMP="${TASK_TMPDIR}"'
        echo 'export TEMP="${TASK_TMPDIR}"'
        echo
        echo "cd ${REPO} || exit 1"
        echo 'echo "Repo: $(pwd)"'
        echo "LIST_DIR=${list_dir}"
        echo 'LIST_FILE="$(find "${LIST_DIR}" -maxdepth 1 -name '\''manifest_list_*.txt'\'' | sort | sed -n "$((SLURM_ARRAY_TASK_ID + 1))p")"'
        echo 'if [[ -z "${LIST_FILE}" ]]; then echo "No manifest list for task ${SLURM_ARRAY_TASK_ID}" >&2; exit 1; fi'
        echo "echo \"=== Phase4 GWD30 tropical shard year=${year} task=\${SLURM_ARRAY_TASK_ID}/${list_count} ===\""
        echo 'echo "Manifest list: ${LIST_FILE}"'
        echo 'echo "Start: $(date)"'
        printf '%q scripts/run_phase4_gwd30_tropical_shard.py' "${PYTHON_BIN}"
        printf ' %q' "--year" "${year}"
        printf ' %s' '--manifest-list "${LIST_FILE}"'
        printf ' %q' "--output-root" "${OUTPUT_ROOT}"
        printf ' %q' "--standardized-dir" "${STANDARDIZED_DIR}"
        printf ' %q' "--worker-count" "${TASK_CPUS}"
        if [[ "${SKIP}" -eq 0 ]]; then
            printf ' %q' "--no-skip"
        fi
        if [[ "${VERBOSE}" -eq 1 ]]; then
            printf ' %q %q' "--log-level" "DEBUG"
        fi
        printf '\n'
        echo 'echo "End: $(date)"'
    } > "${script_path}"
    chmod +x "${script_path}"
}

write_reduce_script() {
    local year="$1"
    local script_path="$2"
    local job_name="$3"
    local job_tmp_dir="$4"
    {
        echo '#!/bin/bash'
        echo "#SBATCH -A ${ACCOUNT}"
        echo "#SBATCH --partition=${REDUCE_PARTITION}"
        echo "#SBATCH --qos=${QOS}"
        echo "#SBATCH -J ${job_name}"
        echo '#SBATCH --nodes=1'
        echo "#SBATCH -c ${REDUCE_CPUS}"
        echo "#SBATCH --time=${REDUCE_TIME}"
        echo "#SBATCH --chdir=$(dirname "${script_path}")"
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
        echo "echo \"=== Phase4 GWD30 tropical reduce ${year} ===\""
        echo 'echo "Partials: '"$(partials_dir "${year}")"'"'
        echo 'echo "Start: $(date)"'
        printf '%q scripts/reduce_phase4_gwd30_tropical_shards.py' "${PYTHON_BIN}"
        printf ' %q' "--year" "${year}"
        printf ' %q' "--output-root" "${OUTPUT_ROOT}"
        if [[ -n "${PHASE36_MASK_PATH}" ]]; then
            printf ' %q' "--phase36-mask-path" "${PHASE36_MASK_PATH}"
        else
            printf ' %q' "--phase36-cache-dir" "${PHASE36_CACHE_DIR}"
            printf ' %q' "--phase36-mask-year" "${PHASE36_MASK_YEAR}"
        fi
        printf ' %q' "--worker-count" "${REDUCE_CPUS}"
        if [[ "${VERBOSE}" -eq 1 ]]; then
            printf ' %q %q' "--log-level" "DEBUG"
        fi
        printf '\n'
        echo 'echo "End: $(date)"'
    } > "${script_path}"
    chmod +x "${script_path}"
}

submit_year() {
    local year="$1"
    build_manifest_lists_for_year "${year}"

    local list_count
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        list_count="${TASK_LISTS}"
    else
        list_count="$(count_manifest_lists_for_year "${year}")"
        if [[ "${list_count}" -lt 1 ]]; then
            echo "No manifest lists were built for year ${year}" >&2
            exit 1
        fi
    fi

    local task_job_name="phase4-gwd30-trop-task-${year}-${TIMESTAMP}"
    local task_job_dir="${JOBS_BASE}/${task_job_name}"
    local task_job_tmp_dir="${TMP_ROOT}/${task_job_name}"
    local task_script="${task_job_dir}/submit.slurm"
    mkdir -p "${task_job_dir}" "${task_job_tmp_dir}"
    write_task_script "${year}" "${task_script}" "${task_job_name}" "${task_job_tmp_dir}" "${list_count}"

    local task_job_id=""
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        echo "[phase4-gwd30:${year}:task] dry-run  (array=${list_count}, time=${TASK_TIME}min, cpus=${TASK_CPUS}, partition=${TASK_PARTITION})"
        echo "  script: ${task_script}"
        echo "  cmd:    sbatch ${task_script}"
        task_job_id="DRYRUN_TASK_${year}"
    else
        local task_submit_output
        task_submit_output="$(sbatch "${task_script}")"
        task_job_id="$(extract_job_id "${task_submit_output}")"
        echo "[phase4-gwd30:${year}:task] ${task_submit_output}  (array=${list_count}, time=${TASK_TIME}min, cpus=${TASK_CPUS}, partition=${TASK_PARTITION})"
    fi

    local reduce_job_name="phase4-gwd30-trop-reduce-${year}-${TIMESTAMP}"
    local reduce_job_dir="${JOBS_BASE}/${reduce_job_name}"
    local reduce_job_tmp_dir="${TMP_ROOT}/${reduce_job_name}"
    local reduce_script="${reduce_job_dir}/submit.slurm"
    mkdir -p "${reduce_job_dir}" "${reduce_job_tmp_dir}"
    write_reduce_script "${year}" "${reduce_script}" "${reduce_job_name}" "${reduce_job_tmp_dir}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        echo "[phase4-gwd30:${year}:reduce] dry-run  (time=${REDUCE_TIME}min, cpus=${REDUCE_CPUS}, partition=${REDUCE_PARTITION})"
        echo "  script: ${reduce_script}"
        echo "  cmd:    sbatch --dependency=afterok:${task_job_id} ${reduce_script}"
    else
        local reduce_submit_output
        reduce_submit_output="$(sbatch --dependency=afterok:${task_job_id} "${reduce_script}")"
        echo "[phase4-gwd30:${year}:reduce] ${reduce_submit_output}  (time=${REDUCE_TIME}min, cpus=${REDUCE_CPUS}, partition=${REDUCE_PARTITION})"
    fi
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
        --phase36-cache-dir)
            PHASE36_CACHE_DIR="$2"
            shift 2
            ;;
        --phase36-mask-path)
            PHASE36_MASK_PATH="$2"
            shift 2
            ;;
        --phase36-mask-year)
            PHASE36_MASK_YEAR="$2"
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
        --task-lists)
            TASK_LISTS="$2"
            shift 2
            ;;
        --task-cpus)
            TASK_CPUS="$2"
            shift 2
            ;;
        --task-time)
            TASK_TIME="$2"
            shift 2
            ;;
        --task-partition)
            TASK_PARTITION="$2"
            shift 2
            ;;
        --reduce-cpus)
            REDUCE_CPUS="$2"
            shift 2
            ;;
        --reduce-time)
            REDUCE_TIME="$2"
            shift 2
            ;;
        --reduce-partition)
            REDUCE_PARTITION="$2"
            shift 2
            ;;
        --no-skip)
            SKIP=0
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
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ -z "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="${REPO}/.venv/bin/python"
fi

if [[ ! -f "${REPO}/scripts/build_phase4_gwd30_shard_lists.py" ]]; then
    echo "Missing: ${REPO}/scripts/build_phase4_gwd30_shard_lists.py" >&2
    exit 1
fi
if [[ ! -f "${REPO}/scripts/run_phase4_gwd30_tropical_shard.py" ]]; then
    echo "Missing: ${REPO}/scripts/run_phase4_gwd30_tropical_shard.py" >&2
    exit 1
fi
if [[ ! -f "${REPO}/scripts/reduce_phase4_gwd30_tropical_shards.py" ]]; then
    echo "Missing: ${REPO}/scripts/reduce_phase4_gwd30_tropical_shards.py" >&2
    exit 1
fi
if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Python executable not found or not executable: ${PYTHON_BIN}" >&2
    exit 1
fi
if [[ ! -f "${CONFIG}" ]]; then
    echo "Config not found: ${CONFIG}" >&2
    exit 1
fi

if [[ -n "${YEAR_FILTER_CSV}" ]]; then
    IFS=',' read -r -a YEAR_FILTERS <<< "${YEAR_FILTER_CSV}"
fi

YEARS=()
while IFS= read -r year; do
    [[ -n "${year}" ]] || continue
    YEARS+=("${year}")
done < <(resolve_gwd30_years)
if [[ ${#YEARS[@]} -eq 0 ]]; then
    echo "No GWD30 years resolved from ${CONFIG}" >&2
    exit 1
fi

mkdir -p "${JOBS_BASE}" "${TMP_ROOT}"

echo "=== Phase4 GWD30 tropical sharded submit ==="
echo "Repo:            ${REPO}"
echo "Python:          ${PYTHON_BIN}"
echo "Standardized:    ${STANDARDIZED_DIR}"
echo "Output root:     ${OUTPUT_ROOT}"
echo "Phase36 cache:   ${PHASE36_CACHE_DIR}"
if [[ -n "${PHASE36_MASK_PATH}" ]]; then
    echo "Phase36 mask:    ${PHASE36_MASK_PATH}"
else
    echo "Phase36 mask yr: ${PHASE36_MASK_YEAR}"
fi
echo "Years:           ${YEARS[*]}"
echo "Task lists:      ${TASK_LISTS}"
echo "Task cpus:       ${TASK_CPUS}"
echo "Task time:       ${TASK_TIME}"
echo "Reduce cpus:     ${REDUCE_CPUS}"
echo "Reduce time:     ${REDUCE_TIME}"
echo "Skip existing:   ${SKIP}"
echo

for year in "${YEARS[@]}"; do
    submit_year "${year}"
done
