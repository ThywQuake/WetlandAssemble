---
estimated_steps: 22
estimated_files: 3
skills_used:
  - brainstorming
---

# T01: Extend the shared evidence contract with classification artifact families

Define the naming/layout contract before adding any new orchestration so the classification line cannot drift into a second filename grammar.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/evidence_contract.py`, existing trend artifact semantics, and the real priority-region catalog | Fail before any downstream writer work starts, with the missing artifact kind or region/metadata collision called out explicitly. | N/A for the pure contract layer; keep the naming API deterministic so later retries do not depend on hidden state. | Reject unknown artifact kinds, non-JSON-safe metadata, and any accidental collision with the established percentage/trend stem structure. |

## Load Profile

- **Shared resources**: in-memory contract metadata and the stable relpath namespace under the Phase 4 output root.
- **Per-operation cost**: trivial path/metadata generation plus focused test assertions.
- **10x breakpoint**: namespace drift, not runtime load — the real failure mode is semantic collision once more artifact families are added.

## Negative Tests

- **Malformed inputs**: unknown classification artifact kind, non-serializable extra metadata, and bad participant-set-like dataset ids.
- **Error paths**: missing required artifact semantics should fail contract construction instead of silently omitting a family.
- **Boundary conditions**: classification stems must stay distinct from the existing percentage/trend stems while still following the same `<dataset_or_key>__<region>__<suffix>` grammar.

## Steps

1. Extend `src/WA/comparison/evidence_contract.py` so `ArtifactKind`, contract validation, and `default_artifact_semantics()` include dedicated classification families for region-scoped surfaces, summaries, and hotspot manifests.
2. Keep the classification file-stem grammar aligned with the trend-agreement convention: the participant-set key lives in the dataset slot, while `__` remains reserved for the outer stem separator.
3. Extend `tests/test_comparison/test_evidence_contract.py` so the new relpaths, metadata payloads, and participant-set naming are locked before any adapter code is added.

## Must-Haves

- [ ] Classification artifact families exist without renaming or destabilizing the S01/S02 percentage/trend families.
- [ ] The contract tests prove deterministic classification relpaths and JSON-safe metadata for the shared `participant_set_key` convention.

## Done when

- `EvidenceContract` can describe the classification surface/summary/hotspot families and focused contract tests pin the exact relpaths/metadata that later tasks will consume.

## Inputs

- `src/WA/comparison/evidence_contract.py`
- `tests/test_comparison/test_evidence_contract.py`
- `src/WA/comparison/trend_contract.py`

## Expected Output

- `src/WA/comparison/evidence_contract.py`
- `tests/test_comparison/test_evidence_contract.py`

## Verification

ruff check src/WA/comparison/evidence_contract.py tests/test_comparison/test_evidence_contract.py
python -m pytest tests/test_comparison/test_evidence_contract.py -q
