#!/bin/bash
# Submit one GWD30 stage-array job plus one dependent merge job per year.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$HOME/repos/WA2}"
OUTPUT_DIR="${OUTPUT_DIR:-$HOME/Wetland_Assemble/data/standardized}"
CONFIG="${CONFIG:-}"
TMP_ROOT="${TMP_ROOT:-$HOME/temp}"
JOBS_BASE="${JOBS_BASE:-${TMP_ROOT}/slurm-jobs}"
ACCOUNT="${ACCOUNT:-hpc1506186103}"
QOS="${QOS:-high}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RESOLUTION="${RESOLUTION:-500}"
PYTHON_BIN="${PYTHON_BIN:-}"
SKIP_EXISTING=1
VERBOSE=0
DRY_RUN=0
STAGE_SHARDS="${GWD30_STAGE_SHARDS:-64}"
STAGE_CPUS="${GWD30_STAGE_CPUS:-4}"
STAGE_TIME="${GWD30_STAGE_TIME:-480}"
STAGE_PARTITION="${GWD30_STAGE_PARTITION:-C064M0256G}"
MERGE_CPUS="${GWD30_MERGE_CPUS:-8}"
MERGE_TIME="${GWD30_MERGE_TIME:-2880}"
MERGE_PARTITION="${GWD30_MERGE_PARTITION:-C064M0256G}"
YEAR_FILTER_CSV=""
YEAR_FILTERS=()
BBOX_ARGS=()

usage() {
    cat <<'EOF'
Usage:
  bash scripts/submit_gwd30_sharded.sh [options]

Options:
  --dry-run               Print generated job scripts but do not submit
  --resolution METERS     Pass resolution to GWD30 jobs
  --bbox W S E N          Pass bbox to GWD30 jobs
  --output-dir PATH       Override output directory
  --config PATH           Override datasets config path
  --repo PATH             Override repo path on HPC
  --python-bin PATH       Override Python executable (default: REPO/.venv/bin/python)
  --tmp-root PATH         Override runtime temp root
  --jobs-base PATH        Override SLURM jobs directory
  --account NAME          Override SLURM account
  --qos NAME              Override SLURM QoS
  --years Y1,Y2,...       Only submit the selected calendar years
  --stage-shards N        Number of SLURM array tasks per year (default: 64)
  --stage-cpus N          CPUs per stage array task (default: 4)
  --stage-time MINUTES    Walltime per stage array task (default: 480)
  --stage-partition NAME  Partition for stage array tasks
  --merge-cpus N          CPUs for dependent merge job (default: 8)
  --merge-time MINUTES    Walltime for dependent merge job (default: 2880)
  --merge-partition NAME  Partition for dependent merge job
  --verbose               Pass -v for WA DEBUG logs
  --no-skip-existing      Do not pass --skip-existing
  --quiet                 Do not pass -v
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

write_stage_script() {
    local year="$1"
    local script_path="$2"
    local job_name="$3"
    local job_tmp_dir="$4"
    {
        echo '#!/bin/bash'
        echo "#SBATCH -A ${ACCOUNT}"
        echo "#SBATCH --partition=${STAGE_PARTITION}"
        echo "#SBATCH --qos=${QOS}"
        echo "#SBATCH -J ${job_name}"
        echo '#SBATCH --nodes=1'
        echo "#SBATCH -c ${STAGE_CPUS}"
        echo "#SBATCH --time=${STAGE_TIME}"
        echo "#SBATCH --array=0-$((STAGE_SHARDS - 1))"
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
        echo "export WA_STANDARDIZE_WORKERS=${STAGE_CPUS}"
        echo
        echo "cd ${REPO} || exit 1"
        echo 'echo "Repo: $(pwd)"'
        echo "echo \"=== GWD30 stage shard year=${year} task=\${SLURM_ARRAY_TASK_ID}/${STAGE_SHARDS} ===\""
        echo 'echo "Start: $(date)"'
        printf '%q scripts/run_gwd30_stage_shard.py' "${PYTHON_BIN}"
        printf ' %q' "--year" "${year}"
        printf ' %s' '--shard-index "${SLURM_ARRAY_TASK_ID}"'
        printf ' %q' "--shard-count" "${STAGE_SHARDS}"
        printf ' %q' "--output-dir" "${OUTPUT_DIR}"
        printf ' %q' "--config" "${CONFIG}"
        printf ' %q' "--resolution" "${RESOLUTION}"
        printf ' %q' "--workers" "${STAGE_CPUS}"
        if [[ ${#BBOX_ARGS[@]} -gt 0 ]]; then
            printf ' %q' "--bbox" "${BBOX_ARGS[@]}"
        fi
        if [[ "${SKIP_EXISTING}" -eq 1 ]]; then
            printf ' %q' "--skip-existing"
        fi
        if [[ "${VERBOSE}" -eq 1 ]]; then
            printf ' %q' "-v"
        fi
        printf '\n'
        echo 'echo "End: $(date)"'
    } > "${script_path}"
    chmod +x "${script_path}"
}

write_merge_script() {
    local year="$1"
    local script_path="$2"
    local job_name="$3"
    local job_tmp_dir="$4"
    local metadata_path="$5"
    {
        echo '#!/bin/bash'
        echo "#SBATCH -A ${ACCOUNT}"
        echo "#SBATCH --partition=${MERGE_PARTITION}"
        echo "#SBATCH --qos=${QOS}"
        echo "#SBATCH -J ${job_name}"
        echo '#SBATCH --nodes=1'
        echo "#SBATCH -c ${MERGE_CPUS}"
        echo "#SBATCH --time=${MERGE_TIME}"
        echo "#SBATCH --chdir=$(dirname "${script_path}")"
        echo '#SBATCH --output=job.%j.out'
        echo '#SBATCH --error=job.%j.err'
        echo '#SBATCH --get-user-env'
        echo
        echo "mkdir -p ${job_tmp_dir}"
        echo "export TMPDIR=${job_tmp_dir}"
        echo "export TMP=${job_tmp_dir}"
        echo "export TEMP=${job_tmp_dir}"
        echo "export WA_STANDARDIZE_WORKERS=${MERGE_CPUS}"
        echo
        echo "cd ${REPO} || exit 1"
        echo 'echo "Repo: $(pwd)"'
        echo "echo \"=== GWD30 merge ${year} ===\""
        echo 'echo "Start: $(date)"'
        printf '%q scripts/standardize_datasets.py' "${PYTHON_BIN}"
        printf ' %q' "--datasets" "gwd30"
        printf ' %q' "--years" "${year}"
        printf ' %q' "--output-dir" "${OUTPUT_DIR}"
        printf ' %q' "--config" "${CONFIG}"
        printf ' %q' "--resolution" "${RESOLUTION}"
        printf ' %q' "--metadata-path" "${metadata_path}"
        if [[ ${#BBOX_ARGS[@]} -gt 0 ]]; then
            printf ' %q' "--bbox" "${BBOX_ARGS[@]}"
        fi
        if [[ "${SKIP_EXISTING}" -eq 1 ]]; then
            printf ' %q' "--skip-existing"
        fi
        if [[ "${VERBOSE}" -eq 1 ]]; then
            printf ' %q' "-v"
        fi
        printf '\n'
        echo 'echo "End: $(date)"'
    } > "${script_path}"
    chmod +x "${script_path}"
}

submit_stage_and_merge_for_year() {
    local year="$1"

    local stage_job_name="std-gwd30-stage-${year}-${TIMESTAMP}"
    local stage_job_dir="${JOBS_BASE}/${stage_job_name}"
    local stage_job_tmp_dir="${TMP_ROOT}/${stage_job_name}"
    local stage_script="${stage_job_dir}/submit.slurm"
    mkdir -p "${stage_job_dir}" "${stage_job_tmp_dir}"
    write_stage_script "${year}" "${stage_script}" "${stage_job_name}" "${stage_job_tmp_dir}"

    local stage_submit_cmd="sbatch ${stage_script}"
    local stage_job_id=""
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        echo "[gwd30:${year}:stage] dry-run  (array=${STAGE_SHARDS}, time=${STAGE_TIME}min, cpus=${STAGE_CPUS}, partition=${STAGE_PARTITION})"
        echo "  script: ${stage_script}"
        echo "  cmd:    ${stage_submit_cmd}"
        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
            "gwd30" "${year}:stage" "${stage_job_name}" "dry-run" "${STAGE_TIME}" "${STAGE_CPUS}" "${STAGE_PARTITION}" "${stage_script}" \
            >> "${SUMMARY_FILE}"
        stage_job_id="DRYRUN_STAGE_${year}"
    else
        local stage_submit_output
        stage_submit_output="$(sbatch "${stage_script}")"
        stage_job_id="$(extract_job_id "${stage_submit_output}")"
        echo "[gwd30:${year}:stage] ${stage_submit_output}  (array=${STAGE_SHARDS}, time=${STAGE_TIME}min, cpus=${STAGE_CPUS}, partition=${STAGE_PARTITION})"
        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
            "gwd30" "${year}:stage" "${stage_job_name}" "${stage_submit_output}" "${STAGE_TIME}" "${STAGE_CPUS}" "${STAGE_PARTITION}" "${stage_script}" \
            >> "${SUMMARY_FILE}"
    fi

    local merge_job_name="std-gwd30-merge-${year}-${TIMESTAMP}"
    local merge_job_dir="${JOBS_BASE}/${merge_job_name}"
    local merge_job_tmp_dir="${TMP_ROOT}/${merge_job_name}"
    local merge_script="${merge_job_dir}/submit.slurm"
    local merge_metadata_path="${merge_job_dir}/metadata.json"
    mkdir -p "${merge_job_dir}" "${merge_job_tmp_dir}"
    write_merge_script "${year}" "${merge_script}" "${merge_job_name}" "${merge_job_tmp_dir}" "${merge_metadata_path}"

    local merge_submit_cmd="sbatch --dependency=afterok:${stage_job_id} ${merge_script}"
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        echo "[gwd30:${year}:merge] dry-run  (afterok:${stage_job_id}, time=${MERGE_TIME}min, cpus=${MERGE_CPUS}, partition=${MERGE_PARTITION})"
        echo "  script: ${merge_script}"
        echo "  cmd:    ${merge_submit_cmd}"
        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
            "gwd30" "${year}:merge" "${merge_job_name}" "dry-run" "${MERGE_TIME}" "${MERGE_CPUS}" "${MERGE_PARTITION}" "${merge_script}" \
            >> "${SUMMARY_FILE}"
    else
        local merge_submit_output
        merge_submit_output="$(sbatch --dependency=afterok:${stage_job_id} "${merge_script}")"
        echo "[gwd30:${year}:merge] ${merge_submit_output}  (afterok:${stage_job_id}, time=${MERGE_TIME}min, cpus=${MERGE_CPUS}, partition=${MERGE_PARTITION})"
        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
            "gwd30" "${year}:merge" "${merge_job_name}" "${merge_submit_output}" "${MERGE_TIME}" "${MERGE_CPUS}" "${MERGE_PARTITION}" "${merge_script}" \
            >> "${SUMMARY_FILE}"
    fi
}

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
        --bbox)
            BBOX_ARGS=("$2" "$3" "$4" "$5")
            shift 5
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
        --years)
            YEAR_FILTER_CSV="$2"
            shift 2
            ;;
        --stage-shards)
            STAGE_SHARDS="$2"
            shift 2
            ;;
        --stage-cpus)
            STAGE_CPUS="$2"
            shift 2
            ;;
        --stage-time)
            STAGE_TIME="$2"
            shift 2
            ;;
        --stage-partition)
            STAGE_PARTITION="$2"
            shift 2
            ;;
        --merge-cpus)
            MERGE_CPUS="$2"
            shift 2
            ;;
        --merge-time)
            MERGE_TIME="$2"
            shift 2
            ;;
        --merge-partition)
            MERGE_PARTITION="$2"
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
        --quiet)
            VERBOSE=0
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

if [[ -z "${CONFIG}" ]]; then
    CONFIG="${REPO}/config/datasets.yaml"
fi

if [[ -z "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="${REPO}/.venv/bin/python"
fi

if [[ -n "${YEAR_FILTER_CSV}" ]]; then
    IFS=',' read -r -a YEAR_FILTERS <<< "${YEAR_FILTER_CSV}"
    CLEANED_YEAR_FILTERS=()
    for year in "${YEAR_FILTERS[@]}"; do
        year="${year//[[:space:]]/}"
        [[ -n "${year}" ]] || continue
        CLEANED_YEAR_FILTERS+=("${year}")
    done
    YEAR_FILTERS=("${CLEANED_YEAR_FILTERS[@]}")
fi

if [[ ! -f "${REPO}/scripts/run_gwd30_stage_shard.py" ]]; then
    echo "REPO does not look correct: ${REPO}" >&2
    echo "Missing: ${REPO}/scripts/run_gwd30_stage_shard.py" >&2
    exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Python executable not found or not executable: ${PYTHON_BIN}" >&2
    exit 1
fi

mkdir -p "${TMP_ROOT}" "${JOBS_BASE}"
SUMMARY_FILE="${JOBS_BASE}/gwd30-sharded-submit-${TIMESTAMP}.tsv"
printf "dataset\ttask\tjob_name\tjob_id_or_action\ttime_min\tcpus\tpartition\tscript\n" > "${SUMMARY_FILE}"

TASK_YEARS=()
while IFS= read -r year; do
    [[ -n "${year}" ]] || continue
    TASK_YEARS+=("${year}")
done < <(resolve_gwd30_years)

if [[ ${#TASK_YEARS[@]} -eq 0 ]]; then
    echo "No GWD30 years resolved from ${CONFIG}" >&2
    exit 1
fi

echo "=== GWD30 sharded submit ==="
echo "Repo:            ${REPO}"
echo "Python:          ${PYTHON_BIN}"
echo "Output dir:      ${OUTPUT_DIR}"
echo "Config:          ${CONFIG}"
echo "Tmp root:        ${TMP_ROOT}"
echo "Resolution:      ${RESOLUTION}"
if [[ ${#BBOX_ARGS[@]} -gt 0 ]]; then
    echo "BBox:            ${BBOX_ARGS[*]}"
fi
echo "Years:           ${TASK_YEARS[*]}"
echo "Skip exists:     ${SKIP_EXISTING}"
echo "Verbose:         ${VERBOSE}"
echo "Dry run:         ${DRY_RUN}"
echo "Stage shards:    ${STAGE_SHARDS}"
echo "Stage cpus:      ${STAGE_CPUS}"
echo "Stage time:      ${STAGE_TIME}"
echo "Stage partition: ${STAGE_PARTITION}"
echo "Merge cpus:      ${MERGE_CPUS}"
echo "Merge time:      ${MERGE_TIME}"
echo "Merge partition: ${MERGE_PARTITION}"
echo "Summary file:    ${SUMMARY_FILE}"
echo ""

for year in "${TASK_YEARS[@]}"; do
    submit_stage_and_merge_for_year "${year}"
done

echo ""
echo "Summary written to: ${SUMMARY_FILE}"
echo "Monitor with: squeue -u $(whoami)"
