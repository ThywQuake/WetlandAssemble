# 2026-03-18 HPC Loader Probe Script

## Architecture decisions

- The new HPC validation flow is implemented as a standalone CLI entrypoint at `scripts/hpc_probe_loaders.py`, backed by reusable helpers in `src/WA/loader_probe.py`.
- The script is intentionally diagnostic-first, not benchmark-first: it prints config, discovery, metadata, structural summaries, sample statistics, elapsed time, and per-dataset failure traces.
- Safe defaults are built in:
  - default probe bbox is a small Amazon window `(-61.0, -5.0, -60.0, -4.0)`,
  - dynamic datasets get an automatic one-month probe window derived from their earliest configured coverage,
  - tiny sample materialization uses a small per-dimension slice instead of full computation.
- Full-domain probing is opt-in through `--unsafe-full-spatial-scan`.
- The probe tool does not modify `config/`; it only reads `config/datasets.yaml` and `config/gee_config.yaml`.

## Modified files and key changes

- `src/WA/loader_probe.py`
  Added CLI-oriented probe helpers:
  - bbox/time parsing,
  - dataset selection,
  - safe default probe resolution,
  - file discovery summaries,
  - lazy dataset summaries,
  - tiny-sample materialization and statistics,
  - human-readable report rendering,
  - optional JSON export.
- `scripts/hpc_probe_loaders.py`
  Added a runnable entrypoint for HPC use.
- `tests/test_loader_probe.py`
  Added tests for safe bbox resolution, auto time-window derivation, and success/failure probe results.
- `todos/002-complete-p1-hpc-loader-probe-script.md`
  Closed the todo with verification notes.

## Verification status

- `uv run python scripts/hpc_probe_loaders.py --dataset giems_mc --metadata-only`: pass
- `uv run pytest -q`: pass (`15 passed`)
- `uv run ruff check .`: pass
- `uv run mypy src tests`: pass

## Open risks, TODOs, rollback notes

- The default Amazon probe window is operationally safe, but not guaranteed to intersect useful data for every future dataset addition. If loader coverage expands, revisit the default probe bbox.
- The script uses loader-private discovery helpers when available (`_candidate_files`, `_discover_tiles`) for richer diagnostics. If loader internals change, the probe script should be updated in step.
- The current CLI prints detailed JSON-like blocks to stdout; if HPC runs become long or multi-user, adding a dedicated log file mode may be useful.
- Existing test warning remains unchanged:
  `numpy.ndarray size changed, may indicate binary incompatibility`
  The suite still passes, but dependency changes should re-check it.
