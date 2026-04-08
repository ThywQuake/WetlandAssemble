---
estimated_steps: 23
estimated_files: 2
skills_used: []
---

# T01: Codify the shared percentage contract and hydro-diverse canonical subset

Retire R101/R106 first by making the region set, canonical subset, artifact semantics, and output naming explicit in code before any producer adapts to it. Keep `config/priority_regions.yaml` read-only; the new contract must load from it rather than annotate it.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `config/priority_regions.yaml` | Fail fast with a validation error naming the missing or unknown region field. | N/A — local file read. | Reject the payload instead of defaulting silently. |

## Load Profile

- **Shared resources**: none beyond one YAML catalog.
- **Per-operation cost**: trivial metadata parsing and JSON-safe dataclass serialization.
- **10x breakpoint**: N/A for the current ten-region catalog; validation logic should still reject duplicates and unknown ids deterministically.

## Negative Tests

- **Malformed inputs**: missing bbox, duplicate canonical region ids, unknown region ids, and non-serializable metadata fields.
- **Error paths**: bad catalog payload raises a readable exception instead of falling back to stale hardcoded defaults.
- **Boundary conditions**: canonical subset order stays deterministic and macro regions do not leak into the proof subset.

## Steps

1. Add `src/WA/comparison/evidence_contract.py` with dataclasses/helpers for contract region records, canonical subset membership, surface/summary/hotspot semantics, and JSON-safe metadata/export helpers.
2. Source the ten-region catalog from `config/priority_regions.yaml` and encode the first canonical subset as `amazon`, `pantanal`, `sudd`, and `borneo` without modifying `config/`.
3. Expose validation helpers that later CLIs can use to resolve `--subset canonical` or explicit `--region` requests and to tag outputs with grid/mask semantics.
4. Add `tests/test_comparison/test_evidence_contract.py` covering catalog validation, canonical subset order, invalid region rejection, and metadata serialization.

## Must-Haves

- [ ] The contract makes region ids, canonical subset membership, and output semantics explicit in one reusable module.
- [ ] Invalid catalog or subset inputs fail loudly; no new hardcoded legacy region defaults are introduced.

## Done when

- The new contract module and test file exist, the canonical subset is queryable without touching `config/priority_regions.yaml`, and the tests prove the contract stays deterministic.

## Inputs

- `config/priority_regions.yaml`
- `src/WA/comparison/phase4_regional.py`
- `.gsd/REQUIREMENTS.md`
- `.gsd/DECISIONS.md`

## Expected Output

- `src/WA/comparison/evidence_contract.py`
- `tests/test_comparison/test_evidence_contract.py`

## Verification

python -m pytest tests/test_comparison/test_evidence_contract.py -q
