#!/bin/bash
# Submit per-dataset standardization jobs to SLURM.
#
# Examples:
#   bash scripts/submit_standardize.sh
#   bash scripts/submit_standardize.sh g2017 glwd
#   bash scripts/submit_standardize.sh --dry-run --resolution 1000 gwd30
#   OUTPUT_DIR=/path/out bash scripts/submit_standardize.sh topmodel wad2m

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
SPLIT_YEARS=1
GLOBAL_PARTITION="${PARTITION_OVERRIDE:-}"
GLOBAL_TIME=""
GLOBAL_CPUS=""
YEAR_FILTER_CSV=""
YEAR_FILTERS=()
BBOX_ARGS=()

ALL_DATASETS=(g2017 glwd_v2 gwd30 swamps topmodel wad2m giems_mc berkeley_rwawc)
DATASETS=()

usage() {
    cat <<'EOF'
Usage:
  bash scripts/submit_standardize.sh [options] [dataset...]

Datasets:
  g2017 glwd_v2 gwd30 swamps topmodel wad2m giems_mc berkeley_rwawc
Aliases:
  glwd -> glwd_v2
  giems -> giems_mc
  berkeley -> berkeley_rwawc

Options:
  --dry-run               Print generated job scripts but do not submit
  --resolution METERS     Pass resolution to standardize_datasets.py
  --bbox W S E N          Pass bbox to standardize_datasets.py
  --output-dir PATH       Override output directory
  --config PATH           Override datasets config path
  --repo PATH             Override repo path on HPC
  --python-bin PATH       Override Python executable (default: REPO/.venv/bin/python)
  --tmp-root PATH         Override runtime temp root (default: ~/temp)
  --jobs-base PATH        Override SLURM jobs directory
  --account NAME          Override SLURM account
  --qos NAME              Override SLURM QoS
  --partition NAME        Force one partition for all datasets
  --time MINUTES          Force one walltime for all datasets
  --cpus N                Force one CPU count for all datasets
  --split-years           Split temporal datasets into one job per year (default)
  --no-split-years        Keep one job per dataset
  --years Y1,Y2,...       Only submit the selected calendar years
  --verbose               Pass -v for WA DEBUG logs
  --no-skip-existing      Do not pass --skip-existing
  --quiet                 Do not pass -v
  -h, --help              Show this message
EOF
}

normalize_dataset() {
    local raw="$1"
    case "$raw" in
        berkeley) printf '%s\n' "berkeley_rwawc" ;;
        giems) printf '%s\n' "giems_mc" ;;
        glwd) printf '%s\n' "glwd_v2" ;;
        *) printf '%s\n' "$raw" ;;
    esac
}

is_valid_dataset() {
    local candidate="$1"
    local dataset
    for dataset in "${ALL_DATASETS[@]}"; do
        if [[ "$dataset" == "$candidate" ]]; then
            return 0
        fi
    done
    return 1
}

dataset_profile() {
    local dataset="$1"
    case "$dataset" in
        g2017) printf '%s\n' "120 8 C064M0256G" ;;
        glwd_v2) printf '%s\n' "120 8 C064M0256G" ;;
        gwd30) printf '%s\n' "5760 32 C064M0256G" ;;
        swamps) printf '%s\n' "2880 16 C064M0256G" ;;
        topmodel) printf '%s\n' "240 8 C064M0256G" ;;
        wad2m) printf '%s\n' "240 8 C064M0256G" ;;
        giems_mc) printf '%s\n' "240 8 C064M0256G" ;;
        berkeley_rwawc) printf '%s\n' "1440 16 C064M0256G" ;;
        *) printf '%s\n' "600 16 C064M0256G" ;;
    esac
}

dataset_block() {
    local dataset="$1"
    awk -v dataset="$dataset" '
        BEGIN {capture = 0; in_datasets = 0}
        /^datasets:/ {in_datasets = 1; next}
        in_datasets && /^[^[:space:]]/ {in_datasets = 0}
        in_datasets && $0 ~ "^  " dataset ":" {capture = 1; next}
        capture && $0 ~ "^  [^[:space:]][^:]*:" {exit}
        capture {print}
    ' "${CONFIG}"
}

dataset_years_from_config() {
    local dataset="$1"
    local block
    block="$(dataset_block "${dataset}")"
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

    local start_year=""
    local end_year=""
    start_year="$(printf '%s\n' "${block}" | sed -n "s/^      start: *['\\\"]\\{0,1\\}\\([0-9]\\{4\\}\\).*/\\1/p" | head -n1)"
    end_year="$(printf '%s\n' "${block}" | sed -n "s/^      end: *['\\\"]\\{0,1\\}\\([0-9]\\{4\\}\\).*/\\1/p" | head -n1)"
    if [[ -n "${start_year}" && -n "${end_year}" ]]; then
        seq "${start_year}" "${end_year}"
        return 0
    fi

    if [[ "${dataset}" == "topmodel" ]]; then
        local topmodel_path=""
        topmodel_path="$(printf '%s\n' "${block}" | sed -n "s/^    path: *['\\\"]\\{0,1\\}\\(.*\\)['\\\"]\\{0,1\\}$/\\1/p" | head -n1)"
        if [[ -n "${topmodel_path}" && -d "${topmodel_path}" ]]; then
            find "${topmodel_path}" -type f -name 'fwet_*_reso025_*.nc' -print 2>/dev/null \
                | sed -n 's/.*_\([0-9][0-9][0-9][0-9]\)\.nc$/\1/p' \
                | sort -u
        fi
    fi
}

resolve_dataset_years() {
    local dataset="$1"
    local -a discovered_years=()
    while IFS= read -r year; do
        [[ -n "${year}" ]] || continue
        discovered_years+=("${year}")
    done < <(dataset_years_from_config "${dataset}")

    if [[ ${#discovered_years[@]} -eq 0 ]]; then
        return 0
    fi

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

submit_dataset_task() {
    local dataset="$1"
    local task_year="$2"
    local time_min="$3"
    local cpus="$4"
    local partition="$5"

    local task_label="all"
    local job_name="std-${dataset}-${TIMESTAMP}"
    if [[ -n "${task_year}" ]]; then
        task_label="${task_year}"
        job_name="std-${dataset}-${task_year}-${TIMESTAMP}"
    fi

    local job_dir="${JOBS_BASE}/${job_name}"
    local job_tmp_dir="${TMP_ROOT}/${job_name}"
    local metadata_path="${job_dir}/metadata.json"
    mkdir -p "${job_dir}"
    mkdir -p "${job_tmp_dir}"

    local -a standardize_args=(
        "--datasets" "${dataset}"
        "--output-dir" "${OUTPUT_DIR}"
        "--config" "${CONFIG}"
        "--resolution" "${RESOLUTION}"
        "--metadata-path" "${metadata_path}"
    )
    if [[ -n "${task_year}" ]]; then
        standardize_args+=("--years" "${task_year}")
    fi
    if [[ ${#BBOX_ARGS[@]} -gt 0 ]]; then
        standardize_args+=("--bbox" "${BBOX_ARGS[@]}")
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
        echo "#SBATCH --partition=${partition}"
        echo "#SBATCH --qos=${QOS}"
        echo "#SBATCH -J ${job_name}"
        echo '#SBATCH --nodes=1'
        echo "#SBATCH -c ${cpus}"
        echo "#SBATCH --time=${time_min}"
        echo "#SBATCH --chdir=${job_dir}"
        echo '#SBATCH --output=job.%j.out'
        echo '#SBATCH --error=job.%j.err'
        echo '#SBATCH --get-user-env'
        echo
        echo "mkdir -p ${job_tmp_dir}"
        echo "export TMPDIR=${job_tmp_dir}"
        echo "export TMP=${job_tmp_dir}"
        echo "export TEMP=${job_tmp_dir}"
        echo "export WA_STANDARDIZE_WORKERS=${cpus}"
        echo
        echo "cd ${REPO} || exit 1"
        echo 'echo "Repo: $(pwd)"'
        echo "if [[ ! -f ${REPO}/scripts/standardize_datasets.py ]]; then"
        echo "  echo 'Bad REPO path: ${REPO}' >&2"
        echo "  exit 1"
        echo "fi"
        echo "if [[ ! -x ${PYTHON_BIN} ]]; then"
        echo "  echo 'Bad PYTHON_BIN path: ${PYTHON_BIN}' >&2"
        echo "  exit 1"
        echo "fi"
        echo
        echo "echo \"=== Standardizing ${dataset} (${task_label}) ===\""
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
        echo "[${dataset}:${task_label}] dry-run  (time=${time_min}min, cpus=${cpus}, partition=${partition})"
        echo "  script: ${script}"
        printf "  cmd:    sbatch %q\n" "${script}"
        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
            "${dataset}" "${task_label}" "${job_name}" "dry-run" "${time_min}" "${cpus}" "${partition}" "${script}" \
            >> "${SUMMARY_FILE}"
        return 0
    fi

    local job_id
    job_id="$(sbatch "${script}" 2>&1)"
    echo "[${dataset}:${task_label}] ${job_id}  (time=${time_min}min, cpus=${cpus}, partition=${partition})"
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
        "${dataset}" "${task_label}" "${job_name}" "${job_id}" "${time_min}" "${cpus}" "${partition}" "${script}" \
        >> "${SUMMARY_FILE}"
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
        --partition)
            GLOBAL_PARTITION="$2"
            shift 2
            ;;
        --time)
            GLOBAL_TIME="$2"
            shift 2
            ;;
        --cpus)
            GLOBAL_CPUS="$2"
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
        --quiet)
            VERBOSE=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do
                DATASETS+=("$1")
                shift
            done
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
        *)
            DATASETS+=("$1")
            shift
            ;;
    esac
done

if [[ ${#DATASETS[@]} -eq 0 ]]; then
    DATASETS=("${ALL_DATASETS[@]}")
fi

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

mkdir -p "${TMP_ROOT}"

if [[ ! -f "${REPO}/scripts/standardize_datasets.py" ]]; then
    echo "REPO does not look correct: ${REPO}" >&2
    echo "Missing: ${REPO}/scripts/standardize_datasets.py" >&2
    echo "Pass --repo /lustre/home/2200013429/repos/WA2 (or export REPO=...)." >&2
    exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Python executable not found or not executable: ${PYTHON_BIN}" >&2
    echo "Expected WA2 venv python. Pass --python-bin /lustre/home/2200013429/repos/WA2/.venv/bin/python if needed." >&2
    exit 1
fi

NORMALIZED_DATASETS=()
SEEN_DATASETS=" "
for dataset in "${DATASETS[@]}"; do
    resolved="$(normalize_dataset "$dataset")"
    if ! is_valid_dataset "$resolved"; then
        echo "Invalid dataset: $dataset" >&2
        usage >&2
        exit 1
    fi
    if [[ "$SEEN_DATASETS" != *" ${resolved} "* ]]; then
        NORMALIZED_DATASETS+=("$resolved")
        SEEN_DATASETS+="$(printf '%s ' "$resolved")"
    fi
done

mkdir -p "${JOBS_BASE}"
SUMMARY_FILE="${JOBS_BASE}/standardize-submit-${TIMESTAMP}.tsv"

echo "=== Standardization batch submit ==="
echo "Repo:         ${REPO}"
echo "Python:       ${PYTHON_BIN}"
echo "Output dir:   ${OUTPUT_DIR}"
echo "Config:       ${CONFIG}"
echo "Tmp root:     ${TMP_ROOT}"
echo "Resolution:   ${RESOLUTION}"
if [[ ${#BBOX_ARGS[@]} -gt 0 ]]; then
    echo "BBox:         ${BBOX_ARGS[*]}"
fi
echo "Datasets:     ${NORMALIZED_DATASETS[*]}"
echo "Split years:  ${SPLIT_YEARS}"
if [[ ${#YEAR_FILTERS[@]} -gt 0 ]]; then
    echo "Year filter:  ${YEAR_FILTERS[*]}"
fi
echo "Skip exists:  ${SKIP_EXISTING}"
echo "Verbose:      ${VERBOSE}"
echo "Dry run:      ${DRY_RUN}"
echo "Summary file: ${SUMMARY_FILE}"
echo ""

printf "dataset\ttask\tjob_name\tjob_id_or_action\ttime_min\tcpus\tpartition\tscript\n" > "${SUMMARY_FILE}"

for DS in "${NORMALIZED_DATASETS[@]}"; do
    PROFILE="$(dataset_profile "${DS}")"
    read -r DEFAULT_TIME DEFAULT_CPUS DEFAULT_PARTITION <<< "${PROFILE}"

    TIME_MIN="${GLOBAL_TIME:-$DEFAULT_TIME}"
    CPUS="${GLOBAL_CPUS:-$DEFAULT_CPUS}"
    PARTITION="${GLOBAL_PARTITION:-$DEFAULT_PARTITION}"

    TASK_YEARS=()
    if [[ "${SPLIT_YEARS}" -eq 1 ]]; then
        while IFS= read -r year; do
            [[ -n "${year}" ]] || continue
            TASK_YEARS+=("${year}")
        done < <(resolve_dataset_years "${DS}")
    fi

    if [[ "${SPLIT_YEARS}" -eq 1 && ${#TASK_YEARS[@]} -gt 0 ]]; then
        echo "[${DS}] split into ${#TASK_YEARS[@]} year task(s): ${TASK_YEARS[*]}"
        for TASK_YEAR in "${TASK_YEARS[@]}"; do
            submit_dataset_task "${DS}" "${TASK_YEAR}" "${TIME_MIN}" "${CPUS}" "${PARTITION}"
        done
        continue
    fi

    if [[ ${#YEAR_FILTERS[@]} -gt 0 ]]; then
        echo "[${DS}] no discoverable years matched filter; submitting unsplit task"
    fi
    submit_dataset_task "${DS}" "" "${TIME_MIN}" "${CPUS}" "${PARTITION}"
done

echo ""
echo "Summary written to: ${SUMMARY_FILE}"
echo "Monitor with: squeue -u $(whoami)"
