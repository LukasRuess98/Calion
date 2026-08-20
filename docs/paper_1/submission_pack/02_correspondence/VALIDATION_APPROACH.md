# Validation: recommended approach
**No re-solves.** Everything below is post-processing of outputs already on disk.
The dispatch results are not in question — what needs fixing is what we measure the
temperature field against, and how we report it.

---

## The problem in one line

The temperature gates were designed for a network metered at its junctions. Memmingen is
metered at consumer substations **downstream of three-way mixing valves**. Those gates
cannot be met by any model of this network, and reporting a bare pass/fail against them
tells the reader nothing about whether the model is right.

---

## First: put the goalposts back

v1's `tab_val_targets` set the return-temperature gate at **2.5 K**, citing Kus et al.
The current table sets it at **1.0 °C**. The measured value is unchanged at 2.08 °C and
flips from pass to fail on the threshold alone.

A gate described as fixed *ex ante* cannot be changed between submissions — that is what
"ex ante" means, and a reviewer who compares the two tables will see it. Restore the
original values. Under them the picture is cleaner and still honest:

| Metric | Value | v1 gate | Verdict |
|---|---|---|---|
| Annual delivered energy | 1.23 % | ≤2 % | pass |
| Return-temp MAE at source | 2.08 °C | <2.5 °C | pass |
| Far-end supply-temp MAE | 9.21 °C | <1.5 °C | **fail** |
| Trunk temp-drop MAE | 9.09 °C | <1.0 °C | **fail** |

One clean pass on the decision-relevant quantity, one pass on return temperature, and two
failures with a physical explanation. That is a defensible table. If a tighter gate is
wanted, add it as a second column labelled as a post-hoc standard — never overwrite the
pre-registered one.

---

## Then: decompose the temperature error into offset and scatter

This is the highest-value analysis available and it needs no new runs.

The far-end supply-temperature residuals are **entirely one-signed**: `MAE = 9.2079` and
`bias = 9.2079` are equal to four decimal places in `validation_kpis.json`. That is not a
model that is wrong — it is a model that is *displaced*. Splitting the error into its two
components turns an uninformative failure into two informative numbers:

| Component | Far-end supply | Return at source |
|---|---|---|
| Systematic offset (bias) | **+9.21 °C** | −0.31 °C |
| Residual scatter (√(RMSE²−bias²)) | **≈6.6 °C** | **≈2.85 °C** |

Read this way the metering explanation stops being an assertion and becomes an
observation: the far-end error is a pure offset of the size a mixing valve produces
(5–15 °C), while the return temperature — measured at the source, upstream of any mixing
valve — is essentially **unbiased** at −0.31 °C. The one sensor not behind a valve agrees
with the model. That is the argument, and it is currently sitting unused in the data.

**Deliverable:** add `bias_C` and `scatter_C` columns to the validation table for every
temperature metric, and state the mixing-valve offset range from the literature so the
reader can see that +9.21 °C falls inside it.

---

## Report the held-out node split you already promised

The response letter tells R2.4: *"we split the spatial validation into fitted and held-out
node sets."* The figures exist — `spatial_profile_train.pdf`, `spatial_profile_test.pdf`,
`spatial_profile_full.pdf`. **The numbers appear nowhere in `validation_kpis.json` or
`tab_validation`.**

This matters more than it looks. v1's headline 1.32 °C was computed on a six-node subset
after excluding four calibration nodes — i.e. partly in-sample. A clean train/test split is
the direct remedy, it is the thing R2.4 asked for, and the figures suggest it has already
been run. Extract and report: per-node MAE on fitted nodes, on held-out nodes, and the gap
between them. If held-out degrades relative to fitted, say by how much; that is a result,
and an honest one.

---

## Add one metric the metering can actually support

Everything above tests the *level* of the temperature field, which a valve offset makes
untestable. What the metering can support is whether the model tracks the *variation*.

Compute the MAE of first differences — does a change in source temperature produce the
right change downstream — or equivalently the correlation of detrended series. A constant
valve offset cancels exactly. If the model tracks dynamics well while sitting 9 °C low,
that is a specific, checkable claim: the transport physics is right and the absolute level
is unobservable. If it tracks dynamics badly, we need to know that before a referee does.

Either outcome is worth having. This is the metric I would add if only one thing gets done.

---

## What not to do

- **Do not re-solve anything.** The dispatch and the decomposition are not implicated;
  this is entirely a measurement-comparison question.
- **Do not re-introduce a calibration multiplier to close the gap.** v1's BCM cross-check
  reached 1.56 °C using a global trunk U-multiplier of ×1.330. All U values are now 1.0,
  and that multiplier is precisely what R2.4 objected to. Fitting the offset away would
  trade a defensible failure for an indefensible pass.
- **Do not quietly drop the failing rows.** They are the evidence for the
  validation-resolution argument that runs through the whole paper.

---

## Priority

1. Restore the ex-ante gates. *(edit, minutes)*
2. Bias/scatter decomposition in the validation table. *(post-processing, small)*
3. Held-out node split numbers. *(extraction — likely already computed)*
4. First-difference dynamic metric. *(post-processing, small)*

Together these convert §3.1 from "we fail most gates, here is why that is acceptable" into
"here is exactly what this metering can and cannot test, here is the model's performance on
each, and here is the one sensor unaffected by the valve — which the model matches without
bias." That is a stronger answer to R2.4 than any additional solve could produce.
