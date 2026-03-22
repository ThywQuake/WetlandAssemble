## Agent Task: Wetland Dataset Comparison & Analysis

### Context

You are working with **8 geospatial wetland datasets** stored on an HPC cluster. Direct inspection is difficult due to scale, mixed formats, projections, and coordinate systems. Satellite imagery datasets are especially large and cannot be analyzed locally.

**Study Area:** Tropical & Subtropical regions — with focus on Brazil, Indonesia, Southeast Asia, and Africa.

**Objective:** Systematically characterize, compare, and evaluate all 8 datasets to determine their suitability for wetland mapping. If feasible, identify candidates for merging into a unified, higher-quality dataset for the study area.

---

### Required Deliverables

#### 1. Dataset Loaders
For each of the 8 datasets, implement a **dedicated loader** that:
- Reads the raw data in its native format
- Converts it to a **common format** suitable for cross-dataset analysis
- Handles any format-specific edge cases (e.g., tiled rasters, irregular projections)

#### 2. Dataset Documentation
Produce **per-dataset documentation** covering:
- File format and structure
- Coordinate reference system (CRS) and projection
- Spatial resolution and coverage
- Temporal range and update frequency
- Known limitations or preprocessing requirements
- Notes on relevance to the study area

#### 3. Comparison Analysis

**Categorical Comparison**
- **Rough (all datasets):** Binary classification — `wetland` vs. `non-wetland`
- **Fine-grained (classification datasets only):** Map and compare all shared/common category labels across datasets

**Quantitative Metrics**
- Shannon entropy (label diversity per dataset)
- Error / confusion matrix (where ground truth or cross-reference is available)
- Any additional relevant accuracy or agreement metrics

**Temporal Trend Analysis**
- **Short-term:** Year-over-year wetland change within the study area
- **Long-term:** Multi-decadal wetland change trends within the study area

---

### Success Criteria
- All 8 datasets can be loaded and converted without manual intervention
- Documentation is complete and consistent across all datasets
- Comparison analysis clearly identifies which datasets are best suited for wetland mapping in the target regions
- If viable, a merge strategy is proposed (or executed) to produce a more comprehensive combined dataset