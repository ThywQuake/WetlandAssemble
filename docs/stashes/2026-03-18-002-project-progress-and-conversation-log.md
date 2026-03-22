# 2026-03-18 Project Progress And Conversation Log

## Current project state

- Repository is still in planning/setup stage. No `src/WA` implementation files exist yet.
- The canonical implementation plan is `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`.
- The earlier draft `docs/plans/2026-03-18-feat-dataset-loaders-plan.md` is still present but is superseded by the canonical plan.
- Dataset reference docs exist under `docs/datasets/` for 8 documented datasets:
  - Berkeley-RWAWC
  - G2017
  - GIEMS-MC
  - GLWD v2
  - GWD30
  - SWAMPS
  - TOPMODEL
  - WAD2M
- `config/datasets.yaml` also contains `lstm_wetland`, but it is currently out of scope because there is no corresponding dataset documentation or semantic definition.
- `config/gee_config.yaml` already contains a GEE project id, so GEE is treated as part of the intended workflow rather than a new subsystem.

## Conversation record

### 1. Repository constraints were adopted

- User clarified that `CLAUDE.md` and `.claude/*` constraints also apply.
- We read `CLAUDE.md` and the local `.claude/skills/sync-hpc/SKILL.md`.
- Working rules confirmed:
  - do not modify `config/` without approval,
  - do not run sync without approval,
  - write Chinese versions for new or changed plan docs,
  - preserve verification status, risks, and a stash summary.

### 2. Existing planning state was reviewed

- No `docs/brainstorms/` directory exists.
- No `docs/solutions/` directory exists.
- There was one existing plan draft: `docs/plans/2026-03-18-feat-dataset-loaders-plan.md`.
- That draft was reviewed and found to contain useful loader and scientific decisions, but it did not fully cover the GEE validation workflow and was not named according to the `ce:plan` filename convention.

### 3. Local project context was consolidated

- `docs/aim.md` defines the project objective:
  - dataset loaders,
  - dataset documentation,
  - comparison analysis,
  - temporal trend analysis.
- `config/datasets.yaml` defines dataset paths, study regions, spatial metrics, trend tests, and aggregation levels.
- `config/gee_config.yaml` defines a GEE project id.

### 4. User added explicit GEE truth requirements

- User requested a missing GEE-related phase:
  - for Rough comparison, download MODIS imagery over focus AOIs as truth-reference imagery,
  - for Fine-grained comparison, extract Shannon entropy hotspots and download Sentinel-2 imagery for truth-reference review,
  - these downloads must be implemented through GEE.

### 5. Canonical plan was created

- A new canonical plan file was written:
  `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`
- The plan explicitly added:
  - loader architecture,
  - rough binary comparison,
  - fine-grained comparison,
  - Shannon entropy hotspot extraction,
  - GEE MODIS truth workflow,
  - GEE Sentinel-2 truth workflow,
  - manifests, outputs, and review artifacts,
  - Chinese version.

### 6. User identified one missing phase

- User pointed out that `Trend Analysis` was still missing as a first-class phase.
- The canonical plan was updated to add an explicit `Phase 4: Trend Analysis`.

### 7. Trend Analysis was restored as a formal project phase

- The plan now explicitly includes:
  - short-term year-over-year trend analysis,
  - long-term multi-decadal trend analysis,
  - annual / seasonal / monthly aggregations,
  - `Mann-Kendall` significance testing,
  - `Sen's Slope` effect-size estimation,
  - cross-dataset trend agreement outputs,
  - `results/trends/`,
  - `docs/trend-analysis-protocol.md`.

## Confirmed architecture decisions

- The workflow is now split into five layers:
  - loader and normalization,
  - spatial comparison,
  - trend analysis,
  - GEE truth imagery,
  - review artifacts and manifests.
- Rough-scale truth imagery uses MODIS via GEE.
- Fine-grained truth imagery uses Shannon entropy hotspots plus Sentinel-2 via GEE.
- Trend analysis is a distinct phase, not a byproduct of comparison.
- GEE should use the existing `config/gee_config.yaml`; no new `config/` schema changes are assumed at the planning stage.
- `lstm_wetland` remains explicitly out of scope until it is documented.
- MODIS and Sentinel-2 imagery are treated as reference imagery for analyst review, not authoritative field-survey truth.

## Current important files

- Canonical plan:
  `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`
- Superseded draft:
  `docs/plans/2026-03-18-feat-dataset-loaders-plan.md`
- Previous short stash:
  `docs/stashes/2026-03-18-001-feat-wetland-loaders-gee-truth-summary.md`
- This conversation log:
  `docs/stashes/2026-03-18-002-project-progress-and-conversation-log.md`

## Verification status

- Documentation and planning research completed against:
  - `CLAUDE.md`
  - `.claude/skills/sync-hpc/SKILL.md`
  - `docs/aim.md`
  - `config/datasets.yaml`
  - `config/gee_config.yaml`
  - `docs/datasets/*.md`
  - official Google Earth Engine documentation and data catalog pages
- No implementation code was added in this conversation.
- No `pytest`, `ruff`, or `mypy` runs were executed because work was limited to planning and stash documentation.

## Open items and risks

- `docs/plans/2026-03-18-feat-dataset-loaders-plan.md` still exists and may confuse future work if treated as active instead of superseded.
- Implementation still needs a concrete policy for when to use:
  - `ee.Image.getDownloadURL()`
  - `ee.data.computePixels()`
  - `Export.image.*`
- Historical fine-grained hotspots before Sentinel-2 availability must produce explicit unsupported states.
- Trend outputs must distinguish:
  - dataset-native windows,
  - cross-dataset overlap windows.
- Sensor transitions and semantic differences may create false trends if not flagged in the future implementation.

## Recommended next step

- Start implementation from the canonical plan.
- First concrete execution block should probably be:
  - `src/WA/config.py`
  - `src/WA/loaders/base.py`
  - `src/WA/loaders/registry.py`
  - base harmonization and trend scaffolding
- Defer GEE export-mode policy tuning until the AOI size and output format constraints are clearer from implementation.

