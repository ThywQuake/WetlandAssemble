#!/bin/bash
# Submit one Phase 4 trend-contract SLURM job per resolved region.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REGIONS_FILE="${SCRIPT_DIR}/../config/priority_regions.yaml"
STANDARDIZED_DIR="${STANDARDIZED_DIR:-$HOME/Wetland_Assemble/data/standardized}"
OUTPUT_ROOT="${OUTPUT_ROOT:-results/phase4}"
TMP_ROOT="${TMP_ROOT:-$HOME/temp}"
JOBS_BASE="${JOBS_BASE:-${TMP_ROOT}/slurm-jobs}"
ACCOUNT="${ACCOUNT:-hpc1506186103}"
QOS="${QOS:-high}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
REPO=""
PYTHON_BIN=""
REGIONS_FILE="${DEFAULT_REGIONS_FILE}"
SUBSET=""
AGGREGATION="annual"
START_YEAR="1990"
END_YEAR="2020"
MIN_OBSERVATIONS="5"
MIN_OVERLAP_YEARS="5"
TOP_HOTSPOTS="10"
CPUS="${PHASE4_TREND_CONTRACT_CPUS:-2}"
TIME_MIN="${PHASE4_TREND_CONTRACT_TIME:-480}"
PARTITION="${PHASE4_TREND_CONTRACT_PARTITION:-C064M0256G}"
PROGRESS=1
VERBOSE=0
DRY_RUN=0
SUMMARY_FILE=""
REGION_FILTERS=()
DATASET_IDS=()
DEFAULT_DATASET_IDS=(gwd30 giems_mc topmodel swamps wad2m)

usage() {
    cat <<'EOF'
Usage:
  bash scripts/submit_phase4_trend_contract.sh [options]

This wrapper always generates one job per region and always passes --no-skip
into run_phase4_trend_contract.py so wide reruns do not silently reuse stale
artifacts.

Required:
  --repo PATH             Repo path on HPC; required so the wrapper never falls back
                          to stale defaults like $HOME/repos/WA2

Selection:
  --subset NAME           canonical | ten (default: ten when --region is omitted)
  --region NAME           Explicit region id override; repeatable; cannot be combined
                          with --subset
  --regions-file PATH     Override priority-region catalog used for fanout

Trend arguments:
  --dataset-id NAME       Participant dataset id; repeat to override the default
                          ordered set (gwd30, giems_mc, topmodel, swamps, wad2m)
  --standardized-dir PATH Override standardized root
  --output-root PATH      Override Phase 4 output root
  --aggregation MODE      annual | seasonal | monthly (default: annual)
  --start-year YEAR       Trend start year (default: 1990)
  --end-year YEAR         Trend end year (default: 2020)
  --min-observations N    Minimum observations per dataset trend (default: 5)
  --min-overlap-years N   Minimum overlap years for agreement (default: 5)
  --top-hotspots N        Maximum trend hotspots per region (default: 10)

Runtime / SLURM:
  --dry-run               Print generated job scripts but do not submit
  --python-bin PATH       Override Python executable (default: REPO/.venv/bin/python)
  --tmp-root PATH         Override runtime temp root
  --jobs-base PATH        Override SLURM jobs directory
  --account NAME          Override SLURM account
  --qos NAME              Override SLURM QoS
  --cpus N                SLURM CPU count
  --time MINUTES          SLURM walltime in minutes
  --partition NAME        SLURM partition
  --no-progress           Disable progress bars in Python job logs
  --verbose               Pass DEBUG logging to Python script
  -h, --help              Show this message
EOF
}

extract_job_id() {
    local submit_output="$1"
    printf '%s\n' "${submit_output}" | awk '{print $NF}'
}

resolve_region_ids() {
    local repo_root="${SCRIPT_DIR}/.."
    local region_csv=""
    if [[ ${#REGION_FILTERS[@]} -gt 0 ]]; then
        region_csv="$(IFS=,; printf '%s' "${REGION_FILTERS[*]}")"
    fi

    python3 - <<'PY' "${repo_root}" "${REGIONS_FILE}" "${SUBSET}" "${region_csv}"
from pathlib import Path
import sys

repo_root = Path(sys.argv[1]).resolve()
regions_file = Path(sys.argv[2]).resolve()
subset = sys.argv[3].strip() or None
region_csv = sys.argv[4].strip()
requested = [item for item in region_csv.split(",") if item] if region_csv else None
sys.path.insert(0, str(repo_root / "src"))
from WA.comparison.evidence_contract import load_phase4_evidence_contract  # noqa: E402

contract = load_phase4_evidence_contract(output_root=repo_root / "results/phase4", regions_file=regions_file)
for region_id in contract.resolve_region_ids(subset=subset, requested_region_ids=requested):
    print(region_id)
PY
}

build_region_script() {
    local region="$1"
    local job_name="phase4-trend-contract-${region}-${TIMESTAMP}"
    local job_dir="${JOBS_BASE}/${job_name}"
    local job_tmp_dir="${TMP_ROOT}/${job_name}"
    local script="${job_dir}/submit.slurm"
    mkdir -p "${job_dir}" "${job_tmp_dir}"

    local -a run_args=(
        "--region" "${region}"
        "--standardized-dir" "${STANDARDIZED_DIR}"
        "--output-root" "${OUTPUT_ROOT}"
        "--aggregation" "${AGGREGATION}"
        "--start-year" "${START_YEAR}"
        "--end-year" "${END_YEAR}"
        "--min-observations" "${MIN_OBSERVATIONS}"
        "--min-overlap-years" "${MIN_OVERLAP_YEARS}"
        "--top-hotspots" "${TOP_HOTSPOTS}"
        "--no-skip"
    )
    if [[ "${PROGRESS}" -eq 0 ]]; then
        run_args+=("--no-progress")
    fi
    if [[ "${VERBOSE}" -eq 1 ]]; then
        run_args+=("--log-level" "DEBUG")
    fi
    local dataset_id
    for dataset_id in "${DATASET_IDS[@]}"; do
        run_args+=("--dataset-id" "${dataset_id}")
    done

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
        echo "if [[ ! -f ${REPO}/scripts/run_phase4_trend_contract.py ]]; then"
        echo "  echo 'Bad REPO path: ${REPO}' >&2"
        echo '  exit 1'
        echo 'fi'
        echo "if [[ ! -x ${PYTHON_BIN} ]]; then"
        echo "  echo 'Bad PYTHON_BIN path: ${PYTHON_BIN}' >&2"
        echo '  exit 1'
        echo 'fi'
        echo
        echo "echo \"=== Phase4 trend contract region=${region} aggregation=${AGGREGATION} years=${START_YEAR}-${END_YEAR} ===\""
        echo 'echo "Start: $(date)"'
        printf '%q scripts/run_phase4_trend_contract.py' "${PYTHON_BIN}"
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
        --regions-file)
            REGIONS_FILE="$2"
            shift 2
            ;;
        --subset)
            SUBSET="$2"
            shift 2
            ;;
        --region)
            REGION_FILTERS+=("$2")
            shift 2
            ;;
        --dataset-id)
            DATASET_IDS+=("$2")
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
        --aggregation)
            AGGREGATION="$2"
            shift 2
            ;;
        --start-year)
            START_YEAR="$2"
            shift 2
            ;;
        --end-year)
            END_YEAR="$2"
            shift 2
            ;;
        --min-observations)
            MIN_OBSERVATIONS="$2"
            shift 2
            ;;
        --min-overlap-years)
            MIN_OVERLAP_YEARS="$2"
            shift 2
            ;;
        --top-hotspots)
            TOP_HOTSPOTS="$2"
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
        -* )
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

if [[ -z "${REPO}" ]]; then
    echo "--repo is required; refusing to fall back to stale defaults like \$HOME/repos/WA2" >&2
    exit 1
fi
if [[ -n "${SUBSET}" && ${#REGION_FILTERS[@]} -gt 0 ]]; then
    echo "Pass either --subset or --region, not both." >&2
    exit 1
fi
if [[ -z "${SUBSET}" && ${#REGION_FILTERS[@]} -eq 0 ]]; then
    SUBSET="ten"
fi
if [[ -z "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="${REPO}/.venv/bin/python"
fi
if [[ ${#DATASET_IDS[@]} -eq 0 ]]; then
    DATASET_IDS=("${DEFAULT_DATASET_IDS[@]}")
fi

case "${AGGREGATION}" in
    annual|seasonal|monthly) ;;
    *)
        echo "Unsupported aggregation: ${AGGREGATION}" >&2
        exit 1
        ;;
esac
if [[ ! -f "${REGIONS_FILE}" ]]; then
    echo "Missing regions file: ${REGIONS_FILE}" >&2
    exit 1
fi
if [[ ! -f "${SCRIPT_DIR}/run_phase4_trend_contract.py" ]]; then
    echo "Missing local runner script: ${SCRIPT_DIR}/run_phase4_trend_contract.py" >&2
    exit 1
fi
if [[ ! -f "${REPO}/scripts/run_phase4_trend_contract.py" ]]; then
    echo "Missing: ${REPO}/scripts/run_phase4_trend_contract.py" >&2
    exit 1
fi
if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Missing executable python: ${PYTHON_BIN}" >&2
    exit 1
fi

mkdir -p "${JOBS_BASE}"
SUMMARY_FILE="${JOBS_BASE}/phase4-trend-contract-${TIMESTAMP}.tsv"
printf 'region\tjob_name\tjob_id\tscript\n' > "${SUMMARY_FILE}"

REGIONS=()
while IFS= read -r region_id; do
    [[ -n "${region_id}" ]] || continue
    REGIONS+=("${region_id}")
done < <(resolve_region_ids)
if [[ ${#REGIONS[@]} -eq 0 ]]; then
    echo "No regions resolved for submission." >&2
    exit 1
fi

region_csv="$(IFS=,; printf '%s' "${REGIONS[*]}")"
dataset_csv="$(IFS=,; printf '%s' "${DATASET_IDS[*]}")"
selector_label="${SUBSET:-explicit-region-list}"
echo "Repo:         ${REPO}"
echo "Python:       ${PYTHON_BIN}"
echo "Regions file: ${REGIONS_FILE}"
echo "Subset:       ${selector_label}"
echo "Regions:      ${region_csv}"
echo "Datasets:     ${dataset_csv}"
echo "Aggregation:  ${AGGREGATION}"
echo "Years:        ${START_YEAR}-${END_YEAR}"
echo "Output root:  ${OUTPUT_ROOT}"
echo "Std dir:      ${STANDARDIZED_DIR}"
echo "Jobs base:    ${JOBS_BASE}"
echo "CPUs:         ${CPUS}"
echo "Time:         ${TIME_MIN}"
echo "Partition:    ${PARTITION}"
echo "Skip mode:    --no-skip"
echo "Progress:     ${PROGRESS}"
echo "Summary TSV:  ${SUMMARY_FILE}"

for region in "${REGIONS[@]}"; do
    IFS=$'\t' read -r job_name script job_dir < <(build_region_script "${region}")
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        echo "[${region}] dry-run  (time=${TIME_MIN}min, cpus=${CPUS}, partition=${PARTITION})"
        echo "  script: ${script}"
        printf '  cmd:    sbatch %q\n' "${script}"
        printf '%s\t%s\tdry-run\t%s\n' "${region}" "${job_name}" "${script}" >> "${SUMMARY_FILE}"
        continue
    fi

    submit_output="$(sbatch "${script}" 2>&1)"
    job_id="$(extract_job_id "${submit_output}")"
    echo "[${region}] ${job_id}  (time=${TIME_MIN}min, cpus=${CPUS}, partition=${PARTITION})"
    printf '%s\t%s\t%s\t%s\n' "${region}" "${job_name}" "${job_id}" "${script}" >> "${SUMMARY_FILE}"
done

echo "Done. Summary written to ${SUMMARY_FILE}"
