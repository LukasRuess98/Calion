# Hydraulic model — calibration and validation summary (for the methods section)

Source: `docs/dhn_storage_study/Netzmodell.md` (sections 3–4; German) and `scripts/dhn_study/netzmodell.py`.
Anonymised station codes; Δp in bar unless stated.

* Model: meshed equivalent network of DHN-A with 25 nodes, 31 edges and 7 meshes; quadratic pressure-loss law per edge
  (calibrated resistance), pump stations PS1/PS2 and plant pumps; KWK as pressure holder.
* Calibration: multi-start parameter fit on 2025 measurements; three near-equivalent optima (A reference, C +0.1 %,
  B +1.6 % calibration cost) are carried through the study as variants A, C, B.
* Holdout validation at high load (top load decile, 241 h), variant A:

| target | RMSE | bias | r | RMSE without calibration |
|---|---|---|---|---|
| city stations V03, V10, V24 | 0.18–0.23 | −0.11…−0.08 | 0.89–0.95 | 0.13–0.18 |
| V12, V23 | 0.21 | +0.01 / −0.10 | 0.91–0.92 | 0.24–0.51 |
| V15, V19 | 0.13–0.21 | −0.13…−0.06 | 0.98 | 0.10–0.23 |
| V22 (site S), V07, V08, V11, V18 (east) | 0.17–0.25 | −0.20…−0.07 | 0.98–1.00 | 0.35–1.75 |
| V06 (south control point) | 0.32 | +0.07 | 0.18 | 0.45 |
| MVA / GT / Bio-KWK | 0.37 / 0.43 / 0.22 | −0.33 / −0.37 / +0.16 | ≥ 0.99 | 2.9 / 1.9 / 2.3 |
| HW1 / PS1 / PS2 / west transfer | 0.41 / 0.37 / 0.22 / 0.29 | +0.28 / +0.30 / −0.09 / −0.11 | 0.43–0.89 | 0.24–0.65 |
| trunk flows L1 / L2 / L3 / L4 [kg/s] | 20 / 7 / 22 / 23 | +7 / −4 / −22 / +18 | 0.74–0.97 | 11–37 |

* Variants C and B: station RMSE 0.10–0.24 bar (V06 0.32–0.33 bar); trunk flows 10–24 kg/s.
* Use in the study: plant Δp is anchored to the measured value of the same hour (model difference added), so the
  calibration error enters as a difference between scenarios rather than as an absolute level.
* Independent numerical cross-check: pandapipes (closed loop) reproduces the model's nodal Δp within 0.055 bar
  (same friction law) and 0.32 bar (Reynolds-dependent friction), see figure 6.
