# P12 — Stadtbach onboarding and discovery

**Depends on:** P0 · **Blocks:** P1, P4, P7
**Output:** `revision/audit/P12_stadtbach.md`, `data/Stadtbach/derived/*.csv`

Three unknowns block all Stadtbach work. The author does not have the answers;
you are to determine them from the repo, the DXF plans and the measurement data,
and to report what cannot be determined.

---

## Unknown 1 — Network geometry, and the 6 km vs 54 km discrepancy

The config header comment at `j_hkw` calls Stadtbach "a ~6 km network," but the
`pipes:` block sums to roughly **54 km**. Total pipe length is about to become a
published predictor variable, so this must be resolved, not guessed.

Likely explanation: network *extent* (longest path / service radius) versus total
installed pipe length. Confirm or refute it.

**Tasks:**
1. Sum `length_m` over all pipes; report total, trunk-only total, and the longest
   source-to-consumer path.
2. **Parse the DXF plans** (swa WV640 Bl.3, WV650 Netz-Mitte, WV660 Netz-West, or
   whatever is in the repo). Use `ezdxf`. Extract: pipe polyline lengths, node
   coordinates, DN annotations, and layer structure. Report which layers carry
   which information.
3. Cross-check DXF-derived lengths against the config's `length_m` values,
   pipe by pipe. Report a table of config vs DXF with the discrepancy, and flag
   anything above 10 %. The config notes "air-line × 1.3" for some entries —
   determine which are true traces and which are estimates.
4. Report both quantities separately and unambiguously: **total pipe length** and
   **network extent**. State which the header comment meant.
5. **Elevations.** Extract Z coordinates or elevation annotations from the DXF if
   present. Augsburg is not flat; static head between two shafts can be
   comparable to friction loss, so a Δp comparison without elevation is
   meaningless. If elevations are absent from the DXF, say so clearly — it
   becomes a data request to swa and a blocker for part of P1.

Also do the equivalent DXF cross-check for **Memmingen** if plans exist
(`Lageplan_Memmingen_drawio.pdf` is in the project) — the same class of error
(header comment vs actual config) was already found there once.

---

## Unknown 2 — Shaft inventory and measurement channels

The author reports that Stadtbach is measured at aggregated points ("Schächte")
with temperature and pressure in VL and RL plus flow, but is not certain how many
shafts there are or whether all carry all four channels.

**Tasks:**
1. Open `data/Stadtbach/stadtbach_acron_combined_cleaned.xlsx` and inventory
   **every** column: name, unit, non-null fraction, time coverage, sampling
   interval, and inferred channel type (T_VL / T_RL / pressure_VL / pressure_RL /
   flow / power / energy / quality flag).
2. Group columns by physical location. Produce a **shaft inventory table**:
   shaft id, channels present, coverage %, first/last timestamp.
3. Distinguish clearly:
   - **measured** consumers (the config says 7)
   - **zone-estimated** consumers (the config says 17, reconstructed by
     `clean_stadtbach_west.py` via energy balance)
   Never use estimated series as validation targets. Flag any that are.
4. Report data quality per channel: gaps > 2 h, outliers beyond ±3σ, physically
   impossible values (T_VL < T_RL, negative flow, pressure_RL > pressure_VL).
5. State plainly what resolution Stadtbach can be validated at. Expectation is
   **zone (T1)** resolution, in contrast to Memmingen's node (T2) resolution —
   this asymmetry is a deliberate argument in the paper (see
   `04_NOVELTY_STATEMENT.md` §4), so characterise it precisely rather than
   apologising for it.

---

## Unknown 3 — Shaft-to-pipe-segment mapping

Pressure sensors read absolute pressure. What can be compared against the model
is **Δp between two shafts on a common flow path with known pipe segments between
them**. That mapping does not currently exist.

**Tasks:**
1. Build a mapping from each shaft to the nearest network node in the config
   topology. Use DXF coordinates if available; otherwise use naming conventions
   and the branch structure, and mark every inferred mapping as inferred.
2. Enumerate all **valid shaft pairs**: pairs on a common path, with the ordered
   list of pipe segments between them and their cumulative length, DN and ΣU·L.
3. For each pair, state whether elevation difference is known. Where unknown, the
   pair can still be used if the residual is treated as a fitted constant offset —
   but that must be reported, not hidden.
4. Write `data/Stadtbach/derived/shaft_pairs.csv`:
   `pair_id, shaft_a, shaft_b, node_a, node_b, segments, length_m, dn_mm,
   elevation_delta_m, elevation_source, n_valid_hours, mapping_confidence`
5. Rank pairs by usefulness for hydraulic validation (long path, high DN
   confidence, good coverage, known elevation). P1 will use the top pairs.

---

## Deliverables

- `revision/audit/P12_stadtbach.md` — findings, with an explicit **"cannot be
  determined from available data"** section listing what must be requested from swa
- `data/Stadtbach/derived/shaft_inventory.csv`
- `data/Stadtbach/derived/shaft_pairs.csv`
- `data/Stadtbach/derived/pipe_length_reconciliation.csv` (config vs DXF)
- A one-paragraph, publication-ready description of the Stadtbach measurement
  setup and its resolution, for `GAP:STADTBACH-DATA`

## Rules

- **NDA.** Stadtbach raw data must not be committed, exported to Zenodo, or
  reproduced in figures at identifying resolution. Derived aggregates only, and
  check this before writing any file.
- Where a mapping is inferred rather than documented, label it. A wrong shaft
  mapping produces a confident, wrong hydraulic validation — worse than none.
- Report unknowns as unknowns. Do not fill gaps with plausible assumptions.
