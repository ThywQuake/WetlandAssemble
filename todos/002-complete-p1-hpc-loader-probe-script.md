---
status: complete
priority: p1
issue_id: "002"
tags: [python, hpc, loaders, diagnostics]
dependencies: ["001"]
---

# HPC Loader Probe Script

Add a script that can be copied to or run on HPC to exercise every in-scope dataset loader and print rich diagnostics for investigation.

## Problem Statement

The new Phase 1 loader layer has synthetic local coverage, but there is no operational script for checking how those loaders behave against the real HPC datasets. Without a dedicated probe tool, every HPC validation run would require ad hoc Python snippets and inconsistent logging.

## Findings

- Loader implementations now exist for all eight documented datasets under `src/WA/loaders/`.
- Large datasets such as GWD30 and SWAMPS must not default to global loads for a smoke test; the script needs safe probing controls.
- The repository has no `scripts/` utilities yet, so the new tool should stay self-contained and avoid introducing runtime dependencies beyond the current stack.
- The user asked for “rich output” intended for information gathering, so the script should report config, path discovery, metadata, dataset structure, timing, and failure details.

## Proposed Solutions

### Option 1: One standalone CLI probe script

**Approach:** Add a Python CLI script that iterates over configured datasets, loads metadata and a controlled subset, optionally computes a tiny sample, and prints structured diagnostics.

**Pros:**
- Easy to run directly on HPC
- Minimal repository change footprint
- Good fit for smoke testing and troubleshooting

**Cons:**
- Script formatting and helper logic still need tests
- Some discovery logic may duplicate loader internals

**Effort:** Short

**Risk:** Low

---

### Option 2: Fold diagnostics into the package API only

**Approach:** Add internal helper functions only, leaving HPC users to write their own runner.

**Pros:**
- Smaller CLI surface
- Less script-specific code

**Cons:**
- Does not solve the actual operational need
- Harder to reuse consistently on HPC

**Effort:** Short

**Risk:** Medium

## Recommended Action

Implement Option 1 with reusable helper functions where sensible. Default the script to safe probing behavior, support filtering by dataset and region/bbox/time, and include an optional “compute small sample” mode for confirming actual data access.

## Technical Details

**Likely targets:**
- `scripts/`
- `tests/`
- `todos/`
- `docs/stashes/`

**Behavior goals:**
- enumerate in-scope datasets from config
- print path and file discovery context
- print metadata and dataset structural summary
- optionally compute a tiny sample for real I/O confirmation
- emit clear failure summaries without stopping the whole run by default

## Resources

- `src/WA/config.py`
- `src/WA/loaders/base.py`
- `src/WA/loaders/registry.py`
- `src/WA/loaders/*.py`
- `config/datasets.yaml`

## Acceptance Criteria

- [x] A runnable HPC-oriented script exists for probing all loaders
- [x] The script prints detailed config, timing, metadata, and dataset-structure diagnostics
- [x] The script supports safe subsetting controls instead of forcing global reads
- [x] Failures are captured per dataset with clear error output
- [x] Local tests cover core helper behavior
- [x] `pytest`, `ruff`, and `mypy` pass
- [x] A stash summary records implementation details and remaining risks

## Work Log

### 2026-03-18 - Todo Creation

**By:** Codex

**Actions:**
- Scoped follow-up work after Phase 1 loader foundation
- Defined the need for an HPC loader verification utility with rich diagnostics
- Chose a standalone CLI script approach over an API-only helper

**Learnings:**
- The biggest operational risk is accidental large reads on HPC, so the script needs safe probing defaults
- Rich diagnostics matter more than elegance here because the primary use case is investigation

### 2026-03-18 - Implementation Complete

**By:** Codex

**Actions:**
- Added `src/WA/loader_probe.py` with CLI argument handling, safe bbox/time-range resolution, discovery diagnostics, dataset summaries, and tiny-sample materialization
- Added `scripts/hpc_probe_loaders.py` as the runnable HPC entrypoint
- Added `tests/test_loader_probe.py` covering bbox resolution, auto time-window logic, and success/failure probe behavior
- Verified the CLI with `uv run python scripts/hpc_probe_loaders.py --dataset giems_mc --metadata-only`
- Re-ran full project checks with `pytest`, `ruff`, and `mypy`

**Learnings:**
- A safe default bbox plus per-dataset one-month probe window is enough to keep the script operationally cautious without making it awkward to use
- Structured JSON-like summaries are more useful for HPC troubleshooting than a minimal pass/fail line

## Notes

- Stay local-only; no remote operations
- Do not modify `config/`
