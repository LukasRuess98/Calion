# Case Study Requirements for Applied Energy Paper

**Document Version:** 1.0
**Date:** 2025-11-18
**Status:** PREPARATION PHASE

---

## Overview

This document outlines the requirements, data needs, and execution plan for the case studies to be included in the Applied Energy manuscript. The case studies are critical for validating EnerGIS and demonstrating its practical applicability.

---

## Case Studies Overview

### Primary Case Study: Municipal District Heating Network

**Name:** Stadtbach District Heating Network (anonymized)
**Type:** Real-world validation
**Priority:** CRITICAL
**Status:** Partial data available, needs expansion

#### Objectives
1. Validate EnerGIS against real operational data
2. Demonstrate practical applicability for municipal heat networks
3. Compare planning (PF) vs. operations (RH) optimization
4. Quantify economic and environmental benefits

#### Requirements

##### Data Requirements

| Data Type | Required | Status | Notes |
|-----------|----------|--------|-------|
| Hourly heat demand (1 year) | ✅ Critical | Partial | Need full 8760h dataset |
| Hourly electricity prices (1 year) | ✅ Critical | Available | EPEX Spot data |
| Grid CO₂ intensity (1 year) | ✅ Critical | Available | Grid operator data |
| Waste heat sources (profiles) | ⚠️ Important | Partial | Need detailed characterization |
| Existing component capacities | ✅ Critical | Available | From network operator |
| Historical operational data | ⚠️ Important | TBD | For validation |
| Technology costs | ✅ Critical | Available | From tech catalog |

##### Deliverables

**For Main Manuscript:**
1. System description (1-2 paragraphs)
2. Annual optimization results table (capacities, costs, emissions)
3. Typical week dispatch visualization (Figure 4)
4. Cost breakdown comparison (Figure 3)
5. Summary statistics (NPV, LCOE, CO₂ reduction)

**For Supplementary Material:**
1. Complete parameter table (all components)
2. Full-year operational time series (selected variables)
3. Sensitivity analysis results (CO₂ price, electricity price, etc.)
4. Validation against historical data (if available)

---

### Secondary Case Study: Benchmark Comparison

**Name:** Simplified Test System (EnerGIS vs. oemof)
**Type:** Methodological validation
**Priority:** HIGH
**Status:** Framework ready, needs execution

#### Objectives
1. Demonstrate parity with established framework (oemof-solph)
2. Compare computational performance
3. Validate MILP formulation correctness

#### Requirements

##### Test Scenarios

| Scenario | Horizon | Components | Purpose |
|----------|---------|------------|---------|
| Parity Check | 24h | 3 | Verify identical results |
| Small System | 168h (1 week) | 5 | Performance baseline |
| Medium System | 720h (1 month) | 8 | Scalability test |
| Large System | 8760h (full year) | 10 | Production scale |

##### Comparison Metrics

1. **Solution Quality**
   - Objective function value (€/year)
   - Optimal capacities (MW)
   - Operational dispatch profiles

2. **Computational Performance**
   - Model build time (seconds)
   - Solver runtime (seconds)
   - Peak memory usage (MB)
   - Scalability factor (runtime vs. problem size)

3. **Usability** (qualitative)
   - Lines of code required
   - Configuration complexity
   - Documentation quality
   - Learning curve

##### Deliverables

**For Main Manuscript:**
1. Benchmark comparison table (Table 2)
2. Runtime vs. problem size plot (Figure 5a)
3. Runtime vs. components plot (Figure 5b)
4. Brief discussion of differences

**For Supplementary Material:**
1. Complete benchmark results (all scenarios)
2. oemof implementation code for reproducibility
3. Parameter mapping documentation

---

### Tertiary Case Study: Sensitivity Analysis

**Name:** CO₂ Price and Technology Cost Sensitivities
**Type:** Policy analysis
**Priority:** MEDIUM
**Status:** Framework ready

#### Objectives
1. Demonstrate framework's utility for policy analysis
2. Show technology selection response to economic parameters
3. Provide insights for heat network planners

#### Sensitivity Parameters

| Parameter | Base Case | Range | Steps | Metric |
|-----------|-----------|-------|-------|--------|
| CO₂ Price | 100 €/t | 0 - 200 €/t | 8 | Technology mix, emissions |
| Electricity Price | 60 €/MWh | ±50% | 5 | HP capacity, grid usage |
| HP Investment Cost | 800 €/kW | ±25% | 5 | HP capacity, total cost |
| RH Window Size | 168h | 24 - 720h | 6 | Solution quality, runtime |

#### Deliverables

**For Main Manuscript:**
1. CO₂ price sensitivity (Figure 6)
2. RH window sensitivity (Table 3)
3. Brief policy implications discussion

**For Supplementary Material:**
1. All sensitivity analysis results
2. Contour plots for multi-parameter analysis
3. Detailed data tables

---

## Data Collection and Preparation

### Required Actions

#### Immediate (Week 1-2)

1. **Contact Network Operator**
   - [ ] Request full-year historical data (2023)
   - [ ] Clarify data sharing agreement / anonymization requirements
   - [ ] Obtain waste heat source characterization

2. **Download Public Data**
   - [ ] EPEX Spot day-ahead prices (2023)
   - [ ] National grid CO₂ intensity data (2023)
   - [ ] Verify data completeness and quality

3. **Prepare Synthetic Dataset**
   - [ ] Create comprehensive synthetic example (full year)
   - [ ] Document generation methodology
   - [ ] Validate synthetic data realism

#### Short-term (Week 3-4)

4. **Data Cleaning and Validation**
   - [ ] Handle missing values
   - [ ] Verify timestamp alignment
   - [ ] Check for outliers and anomalies
   - [ ] Create data quality report

5. **Data Documentation**
   - [ ] Create data dictionary
   - [ ] Document all preprocessing steps
   - [ ] Prepare anonymized dataset for sharing (if possible)

---

## Execution Plan

### Phase 1: Data Preparation (2 weeks)

**Tasks:**
- Collect all required data
- Clean and validate
- Create reproducible preprocessing scripts
- Document data sources

**Deliverable:** Complete, validated input datasets

### Phase 2: Primary Case Study Execution (2 weeks)

**Tasks:**
- Run Planning Framework (full year)
- Run Rolling Horizon (full year with 168h windows)
- Extract all results
- Create all figures and tables
- Write case study description

**Deliverable:** Primary case study section for manuscript + supplementary data

### Phase 3: Benchmark Comparison (1 week)

**Tasks:**
- Implement equivalent model in oemof
- Run all benchmark scenarios
- Analyze performance differences
- Create comparison figures

**Deliverable:** Benchmark section for manuscript

### Phase 4: Sensitivity Analysis (1 week)

**Tasks:**
- Run all sensitivity scenarios
- Analyze results
- Create sensitivity figures
- Write policy implications

**Deliverable:** Sensitivity analysis section + figures

### Phase 5: Validation (1 week, if data available)

**Tasks:**
- Compare EnerGIS results with historical operations
- Quantify prediction accuracy
- Discuss discrepancies

**Deliverable:** Validation results (or explanation of limitations)

---

## Data Availability Statement (Draft)

For Applied Energy submission:

> **Data Availability**
>
> The EnerGIS framework source code and all configuration files are available as open-source software under the MIT License at https://github.com/LukasRuess98/Planing-Framework-for-Heat (DOI: [to be assigned via Zenodo]).
>
> Publicly available data used in this study:
> - Day-ahead electricity prices: EPEX Spot (https://www.epexspot.com)
> - Grid CO₂ intensity: [National grid operator] (https://...)
>
> Operational data from the Stadtbach district heating network are subject to confidentiality agreements with the network operator and cannot be publicly shared. Anonymized aggregated results are provided in Supplementary Material S3. Researchers interested in accessing the data for validation purposes should contact the corresponding author and the network operator.
>
> A comprehensive synthetic dataset representative of municipal district heating networks is provided in the repository (data/synthetic_site/) to enable full reproducibility of the methodology.

---

## Checklist for Case Study Completion

### Data
- [ ] Full year heat demand (8760 hours)
- [ ] Full year electricity prices (8760 hours)
- [ ] Full year CO₂ intensity (8760 hours)
- [ ] Waste heat source characterization (3+ sources)
- [ ] All component parameters validated
- [ ] Historical operational data (for validation, if possible)

### Execution
- [ ] Planning Framework run completed (full year)
- [ ] Rolling Horizon run completed (full year, 168h windows)
- [ ] Benchmark comparison completed (4 scenarios)
- [ ] Sensitivity analysis completed (4 parameters)
- [ ] Validation analysis completed (if data available)

### Results
- [ ] All tables formatted for manuscript
- [ ] All figures created in publication quality (300 DPI)
- [ ] Supplementary data files prepared
- [ ] Data availability statement finalized
- [ ] Code repository tagged with paper version

### Documentation
- [ ] Case study description written (1000 words)
- [ ] Results section written (1500 words)
- [ ] Discussion written (1200 words)
- [ ] Supplementary material complete
- [ ] All references added to bibliography

---

## Success Criteria

### Must Have (Critical for Publication)

1. **At least one complete real-world case study**
   - Full-year optimization
   - Validated results
   - Clear economic and environmental benefits

2. **Benchmark comparison with oemof**
   - Parity check passed (< 1% difference)
   - Performance comparison documented

3. **Reproducibility**
   - All code and configurations public
   - Data (or synthetic equivalent) available
   - Clear documentation

### Should Have (Strengthens Manuscript)

1. **Validation against historical operations**
2. **Multiple sensitivity analyses**
3. **Policy implications discussion**

### Nice to Have (Additional Value)

1. **Multiple case studies (different network types)**
2. **Comparison with commercial tools**
3. **Uncertainty quantification**

---

## Risk Assessment and Mitigation

| Risk | Probability | Impact | Mitigation Strategy |
|------|-------------|--------|---------------------|
| Real data not available | Medium | High | Use comprehensive synthetic dataset, emphasize methodology |
| Historical validation not possible | High | Medium | Validate against Stadtbach reference, focus on benchmarking |
| oemof comparison shows large differences | Low | High | Investigate causes, document explicitly, check formulation |
| Solver runtime too long for full year | Low | Medium | Use time series aggregation, document computational limits |
| Data confidentiality issues | Medium | Medium | Anonymize thoroughly, provide aggregated results only |

---

## Timeline Summary

**Total Estimated Time:** 7 weeks

- Weeks 1-2: Data preparation
- Weeks 3-4: Primary case study
- Week 5: Benchmarking
- Week 6: Sensitivity analysis
- Week 7: Validation and finalization

**Critical Path:** Data collection → Primary case study → Manuscript writing

**Buffer:** 1-2 weeks for revisions and unexpected issues

---

## Next Actions

**Immediate Priority:**

1. Contact network operator for full-year data (TODAY)
2. Download public data (EPEX, grid CO₂) (THIS WEEK)
3. Begin implementing oemof comparison model (THIS WEEK)
4. Create detailed parameter tables (WEEK 2)

**Questions to Resolve:**

1. Can we obtain and share anonymized operational data?
2. What level of anonymization is required?
3. Are there any restrictions on publishing results?
4. Can we get validation data from network operator?

---

## Contact Information

**Network Operator Contact:** [TBD]
**Data Request Status:** [TBD]
**Confidentiality Agreement:** [TBD]

---

**Document Prepared By:** EnerGIS Team
**For:** Applied Energy Submission
**Next Review:** Upon data availability confirmation
