# L5 Validation Quick Start
## One-Page Reference Guide

**Document**: See detailed strategy in `docs/L5_OPERATIONAL_VALIDATION_STRATEGY.md`  
**Status**: Proposal (No paper changes required)

---

## The Idea in 3 Sentences

You have operational heating grid data (BHKW, HP, P2H, heat exchanger specs). Instead of just using it to validate the L3 model once, you can conduct a **3-year validation study** that systematically tests whether CALION's predictions hold true on real equipment. This becomes a second journal paper (2029) that validates the E4 gap currently left open in your 2026 paper.

---

## What You're Validating (4 Components)

| Component | What L3 Assumes | What You'll Measure | Expected Result |
|-----------|---|---|---|
| **BHKW COP** | Fixed η_thermal = 87% | Hourly efficiency vs. part-load | Update L3 if >±5% dev. |
| **Heat Pump** | LMTD formula: COP[t] = η×T/(ΔT) | Real COP from (T_source, T_sink) logs | Validate η_rel = 0.60 ± 0.05 |
| **Network Losses** | U = 0.15 W/(m·K) globally | Measure ΔT on long pipes → infer U | Confirm ±20% accuracy |
| **Storage Losses** | PWL with 8 segments | Tank cooling rates | Verify <±15% MAPE |

---

## 3-Year Roadmap

```
YEAR 1: Extract & Calibrate
├─ Month 1–3:  Extract BHKW/HP/P2H curves from your logs
├─ Month 4–6:  Calibrate network loss model (measure pipe U-values)
├─ Month 7–9:  Storage model validation
└─ Month 10–12: Run L3 on 2024 data → compare to actual. Target: MAPE < 25%

YEAR 2: Deploy & Refine
├─ Month 13–15: Advisory deployment (operators see L3 recommendations)
├─ Month 16–20: Collect feedback, improve instrumentation
└─ Month 21–24: Update L3 parameters. Target: MAPE improves to ~12%

YEAR 3: Validate & Publish
├─ Month 25–27: Full L3 hindcast vs. Year 3 actuals
├─ Month 28–33: Detailed error analysis, study report
└─ Month 34–36: Write journal paper. Target: MAPE < ±5% validated ✅
```

---

## Publication Strategy

### Timeline

```
April 2026: Submit current paper (Sections 1–7, E4 gap acknowledged)
├─ Paper says: "Real validation is future work (2+ years)"

August 2026: Current paper accepted/published
└─ No validation data yet (that's OK—not a requirement)

Sept 2026–Aug 2029: Conduct your 3-year L5 validation study
├─ Parallel effort (doesn't delay current paper)
└─ Generates own dataset & manuscript

Sept 2029: Submit follow-up paper "Operational Validation of [Framework]"
├─ 8,000–10,000 words
├─ Addresses E4 gap (now validated)
└─ Same journal (ECaM) for coherence

March 2030: Validation paper published
└─ Two complementary papers published 3 years apart
```

### Two Publication Options

**Option A (Recommended): Separate Journal Paper**
- Title: "Operational Validation of Joint Investment-Operation MILP: A 3-Year Heating Grid Case Study"
- Target: Energy Conversion & Management (same venue)
- Timeline: Write 2029, publish 2030
- Benefit: Full focus on validation, clear scientific narrative

**Option B (Less Ideal): Conference Presentation + Practitioner Venue**
- Format: 20-minute talk + 3,000-word case study
- Target: DHC+ conference, Euroheat & Power magazine
- Timeline: 2029–2030
- Benefit: Reaches utilities/operators faster (practical impact)

**Option C (Not Recommended): Extension to Current Paper**
- Delays current paper by 3 years (unacceptable for journal pressure)
- Skip this.

---

## Starting Point: Phase 0 (Next 1–2 Months)

**DO THIS NOW** while submitting current paper:

1. **Inventory your data** (1 hour)
   - List all sensors: What do you have? (BHKW power, HP in/out temps, etc.)
   - How much historical data? (need ≥1 year)
   - Resolution: Hourly? 15-min? Sub-minute?

2. **Sketch asset extraction** (2 hours)
   - Can you get BHKW efficiency curve from logs?
   - Can you extract HP COP matrix (2D table)?
   - Can you derive network losses from energy balance?

3. **Identify critical gaps** (1 hour)
   - What data is missing? (e.g., node temperatures for loss calc?)
   - Do you need new sensors? (cost/timeline?)

4. **Create prep checklist** (1 hour)
   - List 10–15 tasks for months 1–3 of Year 1
   - Estimate effort for your team

**Decision**: After this Phase 0 assessment (April 2026):
- ✅ Go ahead → Start data extraction in May 2026
- ⏳ Defer → Postpone validation study until 2027 (after current paper published)
- ❌ Not feasible → Document why (data gaps, staffing, etc.)

---

## Key Questions for Your Team

Answer these to make Phase 0 actionable:

1. **How many years of operational logs do you have?** (need ≥1)
2. **What's your logging resolution?** (hourly? 15-min?)
3. **Can you extract BHKW part-load efficiency from your data?**
4. **Do you have HP inlet/outlet temperatures?** (needed for COP validation)
5. **Can you calculate network-wide heat losses?** (from energy balance or measured temps?)
6. **Do you have a thermal storage tank?** (separate validation track if yes)
7. **Budget for additional instrumentation?** (e.g., if missing node temps)
8. **Staff availability?** (how many person-months for 3-year effort?)

---

## Validation Acceptance Criteria

### If Study Achieves These → Success ✅

| Metric | Year 1 | Year 2 | Year 3 | Meaning |
|--------|--------|--------|--------|---------|
| **COP MAPE** | <±8% | <±6% | <±4% | HP model improving |
| **Dispatch MAPE** | <±20% | <±15% | <±10% | Operational similarity |
| **Cost prediction** | ±15% | ±12% | ±8% | Economic feasibility |
| **Network loss error** | ±20% | ±15% | ±10% | Loss model valid |

**Publication gate**: If Year 3 achieves <±5% MAPE → Journal quality validation ✅

---

## Typical Errors Discovered (Real Examples)

### What usually goes wrong (and gets discovered in L5)

| Issue | Impact | Example |
|-------|--------|---------|
| **COP optimism** | Overestimates savings | Real HP COP 2.8 vs. model 3.2 (10% prediction error) |
| **Sensor accuracy** | Measurement noise | Temperature sensors ±0.5°C → COP calc ±3% error |
| **Part-load efficiency** | BHKW underperforms | Part-load η drops to 80% vs. model 87% |
| **Network aging** | U-value increases | Pipes degraded → U shifts from 0.15 to 0.22 W/(m·K) |
| **Storage stratification** | Model oversimplifies | Tank losses ±25% PWL model (needs refinement) |
| **Operator deviations** | Real dispatch suboptimal | Operators follow daily schedules, ignore L3 (rational: habitual/risk-averse) |

**Good news**: All of these are discoverable with Year 1 data and addressable with Year 2 model updates.

---

## What Happens to Current Paper?

### Zero Impact

✅ Paper remains unchanged (Sections 1–7 complete, scientifically sound)  
✅ E4 gap remains acknowledged (you're not claiming validation yet)  
✅ Submit to ECaM in April 2026 on schedule  
✅ Validation study is independent follow-up (not a blocker)  

**How to frame it in current paper**: 
- Section 6.4 Limitations: "Real operational validation requires 2+ year deployment" ← Keep this
- Section 7: Future Work: "Recommended: Deploy on 2–3 real systems" ← This is what you're doing
- No changes needed.

---

## ROI for Your Organization

### Why Do This?

1. **Scientific rigor**: Rare to see 3-year validation in energy optimization literature
2. **Practitioner credibility**: Utilities see L3 works IRL, not just on paper
3. **Publication impact**: Two papers better than one; shows long-term commitment
4. **Operational insights**: Discover unexpected challenges, operational limits
5. **IP/tech leadership**: Position your organization as validation expert in DH optimization

### Cost-Benefit

**Year 1 effort**: ~5 person-months (data extraction, calibration)  
**Year 2 effort**: ~3 person-months (advisory deployment, monitoring)  
**Year 3 effort**: ~4 person-months (analysis, manuscript writing)  
**Total**: ~12 person-months (~1 FTE/year for 3 years)

**Benefit**: 
- 2 journal papers (same author, same venue = career boost)
- Real grid data (valuable for marketing/consulting)
- Operational guidelines (utility case study)
- Model improvements (3-year refinement cycle)

---

## Next Action

**THIS WEEK**: Answer the 7 questions above about your data.

**NEXT MONTH**: Complete Phase 0 checklist (inventory + plan).

**BY APRIL 2026**: 
- Current paper submitted to ECaM ✅
- Phase 0 assessment complete ✅
- Decision made: Go ahead with L5 or defer? ✅

**IF GO AHEAD**: 
- Start data extraction May 2026
- First hindcast results expected December 2026
- Decision point Jan 2027: Continue to Phase 2 (advisory deploy)?

---

**Full documentation**: See `docs/L5_OPERATIONAL_VALIDATION_STRATEGY.md`  
**Questions?**: Review Part 9 (Implementation Checklist) for specific guidance
