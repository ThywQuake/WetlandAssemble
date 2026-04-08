# Project Contract

## Build And Test

- Install: `uv add`
- Test: `pytest`
- Typecheck: `mypy`

## Architecture Boundaries

- Dataset infos: `docs/datasets`
- Brainstorms: `docs/brainstorms`
- Plans: `docs/plans`
- TODOs: `docs/todos`
- Phase Stashes: `docs/stashes`
- Rollback Notes: `docs/rollbacks`
- Code: `src/WA`

## Coding Conventions

- Follow PEP8 and project linting rules
- Write clear, concise commit messages
- Document code with docstrings and comments where necessary
- Add enough `print` statements or logging at key steps so execution progress can be checked easily

## NEVER

- Modify `config/` without approval
- Commit without running tests
- Run sync without approval
- Silently suppress errors
- Silently reuse cache without making it visible in logs

## ALWAYS

- Show diff before committing
- Update CHANGELOG for user-facing changes
- Use `sync-hpc` skill for HPC code sync
- Write a Chinese version in docs if create a new plan or modify an existing one
- Prefer cache, checkpoints, or intermediate-result persistence for data processing when practical
- Design data pipelines so interrupted runs can resume instead of recomputing from scratch
- Give me specific commands to run on HPC after code changes.

## Verification

- Backend changes: `pytest` + `ruff`
- Plan changes: check `docs/datasets` and `docs/plans`

## Compact Instructions

Preserve:

1. Architecture decisions (NEVER summarize)
2. Modified files and key changes
3. Current verification status (pass/fail commands)
4. Open risks, TODOs, rollback notes
5. Generate a brief summary file in `docs/stashes` for quick reference

## HPC Workflow

- User syncs code to HPC via `rsync`, NOT git. Never suggest git push/pull for HPC deployment.
- HPC is headless: no browser-based OAuth or GUI tools available.
- When generating HPC commands, use `--no-skip` not `--skip-existing` for CLI args.

## Project Defaults

- Default target year is 2016, NOT 2019.
- Wetland datasets: GWD30 has extra band dimension that must be squeezed. WAD2M loaders must return DataArray, not Dataset.

## Working Style

- Be direct and action-oriented. When asked 'what to do next', give a specific next step, not a generic phase plan.
- Minimize codebase exploration before delivering results. Start with targeted reads, not broad scans.
- Always run all tests after code changes: `python -m pytest tests/`
- Always put a loading bar for loops when processing GWD30 dataset or downloading data from GEE.
- Prefer visible progress reporting over silent long-running execution.

## Error Handling

- On HPC parallel processing, always catch broad Exception (not just BrokenProcessPool) and fall back to serial.
- Always log errors.
- For long-running data processing tasks, prefer checkpointing or caching so partial progress can be recovered after interruption.