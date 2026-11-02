"""Hydraulic evaluation of an hourly schedule on the calibrated meshed Ersatznetz (25 nodes, 31 edges, 7 meshes).

Per hour (vectorised over all hours):
1. Injections [kg/s] from the MILP heat per plant and Q_central with the network enthalpy difference Δh(T_VL, T_RL)
   (measured supply/return of the main plant). Exogenous: west heat-exchanger export (measured flow, sink at HW2),
   partner A's own load at S (measured flow), pump-station gains PS1/PS2 (measured; with ``ps1_control`` PS1 may add
   head up to its pump curve to hold V06, D11), KWK return pressure (pressure holding, measured). Expansion load
   (``D_extra``) is withdrawn at the south nodes with today's south weights. The remaining consumer flow is distributed with the calibrated load weights.
2. Control: the KWK is the pressure holder (also in summer, where it holds ≈ 1.8 bar at ≈ zero net flow, see docs).
   Its Δp is set to the smallest value that keeps V06 ≥ 1.2 bar and the city-centre stations ≥ 1.0 bar.
3. Plant Δp at MVA, GT, Bio-KWK, HW1: model value, anchored to the measured 2025 value of the same hour
   (measured + model(schedule) − model(measured dispatch)); without a valid measurement: model + median bias.
4. Limits (hard): KWK Δp ≤ KWK pump curve; plant Δp ≤ plant pump curve (generic centrifugal curve, head scaled so that
   the measured 2025 envelope is feasible – reported); plant return pressure ≥ shutdown pressure (plants.yaml); plant
   supply pressure ≤ min(shutdown pressure, PN25). Soft (reported): KWK 4.0 bar, east plants 7.5 bar.
5. Outputs: flows per edge, flow direction, required KWK Δp and binding station, plant Δp/pressures, margins, pump
   power per feed-in, saturation margin.

Absolute pressures: return pressure at a plant = KWK return pressure + a_g − (Δp_g − Δp_KWK)/2. The symmetric split of
the combined edge resistance into supply and return line reproduces the measured MVA return pressure with R² = 0.97
(slope 1.02); a_g (elevation and sensor offset) is fitted per plant on the 2025 data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import daten, hydraulik
from .. import netzmodell as nm
from ..run_netzmodell import KALIBRIERUNG_REPO, MINDEST_MITTE, lade_kalibrierung
from . import milp
from .milp import EXISTING, PLANTS


def node_of(spec: str) -> str:
    """Node of the Ersatznetz: either a node id or ``station:<Vxx>`` (node of a transfer station)."""
    return nm.STATIONEN[spec.split(":", 1)[1]] if str(spec).startswith("station:") else spec

G = 9.81
PLANT_KEY = {"KWK": "gas_CHP", "MVA": "waste_incineration", "GT": "gas_turbine", "BIO": "biomass_CHP",
             "HW1": "boiler_plant_1"}
NODE = {"MVA": "MVA", "GT": "GT", "BIO": "BIO", "HW1": "HW1"}
DP_COL = {"KWK": ("gas_CHP_p_supply", "gas_CHP_p_return"), "MVA": ("waste_incineration_p_supply", "waste_incineration_p_return"),
          "GT": "gas_turbine_dp", "BIO": "biomass_CHP_dp", "HW1": "boiler_plant_1_dp"}
PRET_COL = {"MVA": "waste_incineration_p_return", "GT": "gas_turbine_p_return", "BIO": "biomass_CHP_p_return",
            "HW1": "boiler_plant_1_p_return"}
S_INTERNAL_DP_BAR = 0.5          # assumed internal loss of the feed-in station at S (pump power only)


def _installed_flow_kg_s(spec: str) -> float:
    tot = 0.0
    for part in spec.split("+"):
        n, q = part.strip().split("x")
        val = float(re.findall(r"[\d.]+", q)[0])
        if "m3" in q:
            val *= daten.rho_w(60.0) / 1000.0
        tot += int(n) * val
    return tot / 3.6


@dataclass
class PumpCurve:
    """Generic centrifugal curve of the parallel pump set: H(Q) = H_n·(r − (r − 1)·(Q/Q_n)²), scaled by ``k`` so that the
    measured 2025 envelope is feasible; outlet Δp = ρ g H / 1e5 − Δp_int·(Q/Q_ref)²."""
    Qn: float
    Hn: float
    ratio: float
    dp_int: float
    Q_ref: float
    k: float = 1.0

    def head_bar(self, q, t_c):
        h = self.Hn * (self.ratio - (self.ratio - 1.0) * (np.asarray(q, float) / self.Qn) ** 2)
        return self.k * daten.rho_w(t_c) * G * np.maximum(h, 0.0) / 1e5

    def internal(self, q):
        return self.dp_int * (np.asarray(q, float) / self.Q_ref) ** 2

    def dp_max(self, q, t_c):
        return self.head_bar(q, t_c) - self.internal(q)


class Hydro:
    """Hydraulic evaluator for one calibration variant."""

    def __init__(self, cfg: dict, x: pd.DataFrame, variant: str = "A"):
        self.cfg, self.x, self.variant = cfg, x, variant
        hc = cfg["hydraulics"]
        self.nz = nm.netz()
        self.kal = lade_kalibrierung(KALIBRIERUNG_REPO / variant, self.nz)
        self.K = np.array(self.kal["K"], float)
        rf = hc.get("reinforce") or {}
        for e in rf.get("edges", []):                 # pipe reinforcement (parallel pipe of equal DN: K × 0.25)
            self.K[self.nz.kanten_ids.index(e)] *= float(rf.get("K_factor", 0.25))
        self.versatz = self.kal["versatz"].to_dict()
        m = daten.lade_messdaten().reindex(x.index)
        self.m = m
        self.dh = np.asarray(daten.dh(x["T_VL"], x["T_RL"]), float)            # kJ/kg
        self.rho_r = daten.rho_w(x["T_RL"].to_numpy())
        self.hx = (m["boiler_plant_2_hx_flow"] / 3.6).interpolate(limit_direction="both").fillna(0.0).to_numpy()
        g = (m["V22_flow"] / 3.6).to_numpy()
        self.gk_meas = np.isfinite(g)
        self.gk = np.nan_to_num(g)
        E = len(self.nz.kanten)
        self.gain = np.zeros((len(x), E))
        for kid, ps in nm.PUMPEN.items():
            v = (m[f"{ps}_dp_supply_after_pump"] - m[f"{ps}_dp_supply_before_pump"])
            self.gain[:, self.nz.kanten_ids.index(kid)] = v.fillna(v.median()).to_numpy()
        self.p_ret_kwk = m["gas_CHP_p_return"].interpolate(limit_direction="both").fillna(8.4).to_numpy()
        self.mindest = {"V06": hc["control"]["setpoints"]["V06"],
                        **{z: hc["control"]["setpoints"].get("Mitte", MINDEST_MITTE) for z in hc["control"]["mitte_stations"]}}
        self.plants_yaml = daten.lade_anlagen()["plants"]
        la = nm.lastanteile()
        sud = [k for k in nm.LASTGRUPPEN["Süd"]]
        self.south_w = {k: float(la[k] / la[sud].sum()) for k in sud}
        self._obs_dp()
        self.ref = self._model(self._sched_measured(), with_extra=False)     # today's measured operation (anchor)
        self._curves()
        # PS1 towards the south: one pump 429 m³/h @ 40 m (no parallel operation, plan A), generic curve
        self.ps1_curve = PumpCurve(Qn=429 * daten.rho_w(100.0) / 3600, Hn=40.0,
                                   ratio=cfg["hydraulics"]["pump_curve"]["shutoff_ratio"], dp_int=0.0, Q_ref=1.0)
        self._pret_offsets()

    # ------------------------------------------------------------------ inputs
    def _obs_dp(self):
        m = self.m
        self.dp_obs = {}
        for g, c in DP_COL.items():
            self.dp_obs[g] = (m[c[0]] - m[c[1]]).to_numpy() if isinstance(c, tuple) else m[c].to_numpy()
        ms = hydraulik.massenstroeme(m, daten.erzeugung(m))
        self.q_obs = {"KWK": ms.KWK.to_numpy(), "MVA": ms.MVA.to_numpy(), "GT": ms.GT.to_numpy(), "BIO": ms.Bio.to_numpy(),
                      "HW1": ms.HW1.to_numpy()}
        self.running_obs = {g: np.nan_to_num(self.q_obs[g]) > 5.0 for g in self.q_obs}

    def _sched_measured(self) -> pd.DataFrame:
        s = pd.DataFrame({f"Q_{g}": self.x[f"Q_meas_{g}"] for g in EXISTING}, index=self.x.index)
        s = s.fillna(0.0)
        s["Q_NEW"] = 0.0
        # KWK closes the measured balance of today's demand (it is the slack in the network model as well)
        s["Q_KWK"] = np.maximum(self.x["D_base"] - s[[f"Q_{g}" for g in EXISTING if g != "KWK"]].sum(axis=1), 0.0)
        s["Q_central"] = 0.0
        s["Q_tes_ext"] = 0.0
        return s

    def injections(self, sched: pd.DataFrame, with_extra: bool = True) -> np.ndarray:
        nz = self.nz
        mf = 1e3 / self.dh                                         # kg/s per MW
        B = len(sched)
        b = np.zeros((B, len(nz.knoten)))
        for g in ("MVA", "GT", "BIO", "HW1"):
            b[:, nz.idx[NODE[g]]] += sched[f"Q_{g}"].to_numpy() * mf
        q_new = sched["Q_NEW"].to_numpy() if "Q_NEW" in sched else np.zeros(B)
        q_tx = sched["Q_tes_ext"].to_numpy() if "Q_tes_ext" in sched else np.zeros(B)
        if milp.unserved_mode(self.cfg):            # unserved heat of the new customers: their withdrawal shrinks
            for k, wk in self.south_w.items():
                b[:, nz.idx[k]] += q_new * mf * wk
        else:
            b[:, nz.idx[node_of(self.cfg.get("new_boiler", {}).get("node", "station:V06"))]] += q_new * mf
        b[:, nz.idx[node_of(self.cfg["tes"].get("node", "S"))]] += q_tx * mf
        b[:, nz.idx["HW2"]] -= self.hx
        b[:, nz.idx["S"]] += sched["Q_central"].to_numpy() * mf
        cons = (sched[[f"Q_{g}" for g in EXISTING]].sum(axis=1).to_numpy() + q_new + q_tx + sched["Q_central"].to_numpy()) * mf - self.hx
        # new customers of the expansion area (south nodes, weighted with today's connected load)
        extra = self.x["D_extra"].to_numpy() * mf if ("D_extra" in self.x and with_extra) else np.zeros(B)
        if extra.any():
            w = self.south_w
            for k, wk in w.items():
                b[:, nz.idx[k]] -= extra * wk
            cons = cons - extra
        b[self.gk_meas, nz.idx["S"]] -= self.gk[self.gk_meas]
        rest = np.where(self.gk_meas, cons - self.gk, cons)
        b -= nm.verteilung(nz, np.maximum(rest, 0.0), self.gk_meas, self.kal["gewichte"], self.kal["grundlast"])
        return b

    # ------------------------------------------------------------------ core model
    def _model(self, sched: pd.DataFrame, sel: np.ndarray | None = None, with_extra: bool = True) -> dict:
        nz = self.nz
        sel = np.arange(len(sched)) if sel is None else sel
        b = self.injections(sched, with_extra)[sel] if len(sched) == len(self.x) else self.injections_subset(sched, sel)
        gain = self.gain[sel]
        flows = nz.loese(b, self.K, gain)
        req, need = nm.erforderliche_kwk_dp(nz, self.K, b, gain, self.mindest, self.versatz)
        ps1_used = np.zeros(len(sel))
        if self.cfg["hydraulics"].get("ps1_control", False) and with_extra:
            # PS1 (radial south branch, edge L4c) may raise its head up to its pump curve: lowers only the V06 need
            e = nz.kanten_ids.index("L4c")
            q = np.maximum(flows[:, e], 0.0)
            room = np.maximum(self.ps1_curve.dp_max(q, self.x["T_VL"].to_numpy()[sel]) - gain[:, e], 0.0)
            nv = need["V06"].to_numpy()
            others = need.drop(columns="V06").max(axis=1).to_numpy()
            ps1_used = np.clip(nv - others, 0.0, room)
            need = need.assign(V06=nv - ps1_used)
            req = need.max(axis=1).to_numpy()
            gain = gain.copy()
            gain[:, e] += ps1_used
        dp = nz.dp_knoten(flows, self.K, req, gain)
        return {"b": b, "m": flows, "req": req, "bind": need.idxmax(axis=1).to_numpy(), "dp": dp, "sel": sel,
                "ps1_extra": ps1_used, "gain": gain}

    def injections_subset(self, sched: pd.DataFrame, sel: np.ndarray) -> np.ndarray:
        """Injections for a schedule that covers only the hours ``sel`` (same row order)."""
        full = pd.DataFrame(0.0, index=self.x.index, columns=sched.columns)
        full.iloc[sel] = sched.to_numpy()
        return self.injections(full)[sel]

    # ------------------------------------------------------------------ limits
    def _curves(self):
        r = self.cfg["hydraulics"]["pump_curve"]["shutoff_ratio"]
        self.curves = {}
        for g, key in PLANT_KEY.items():
            p = self.plants_yaml[key]
            mm = p["m_max_t_h"]
            qref = (mm["transition"] if isinstance(mm, dict) else mm) / 3.6
            self.curves[g] = PumpCurve(Qn=_installed_flow_kg_s(p["pumps"]["installed"]), Hn=p["pumps"]["head_m"], ratio=r,
                                       dp_int=p["dp_internal_bar"], Q_ref=qref)
        self.curve_scale = {}
        t = self.x["T_RL"].to_numpy()
        i_kwk = self.nz.kanten_ids.index("KWKi")
        q_ref = {"KWK": self.ref["m"][:, i_kwk], **{g: self.ref["b"][:, self.nz.idx[NODE[g]]] for g in NODE}}
        for g, c in self.curves.items():
            # flows as converted in this evaluator (network Δh), measured Δp; only hours with the plant running
            q, d = np.where(self.running_obs[g], q_ref[g], np.nan), self.dp_obs[g]
            ok = np.isfinite(q) & np.isfinite(d) & (q > 5)
            need = (d[ok] + c.internal(q[ok])) / c.head_bar(q[ok], t[ok])
            k = max(1.0, float(np.max(need))) if ok.any() else 1.0
            self.curve_scale[g] = {"k": k, "viol_nominal_h": int((need > 1.0).sum()),
                                   "max_excess_nominal_bar": float(np.max(d[ok] - c.dp_max(q[ok], t[ok]))) if ok.any() else np.nan}
            if self.cfg["hydraulics"]["pump_curve"].get("anchor", "envelope") == "envelope":
                c.k = k

    def _pret_offsets(self):
        """a_g in p_ret,g = p_ret,KWK + a_g − (Δp_g − Δp_KWK)/2, fitted on 2025 (median of residual)."""
        self.a_ret = {}
        dk = self.dp_obs["KWK"]
        for g, col in PRET_COL.items():
            pr = self.m[col].to_numpy()
            res = pr - self.m["gas_CHP_p_return"].to_numpy() + (self.dp_obs[g] - dk) / 2
            ok = np.isfinite(res) & self.running_obs[g]
            self.a_ret[g] = float(np.median(res[ok])) if ok.any() else 0.0

    # ------------------------------------------------------------------ evaluation
    def evaluate(self, sched: pd.DataFrame, sel: np.ndarray | None = None, keep_flows: bool = False) -> pd.DataFrame:
        """Per-hour hydraulic state and limit check for ``sched`` (full year or the subset ``sel``)."""
        r = self._model(sched, sel)
        sel = r["sel"]
        nz = self.nz
        idx = self.x.index[sel]
        t_rl, t_vl = self.x["T_RL"].to_numpy()[sel], self.x["T_VL"].to_numpy()[sel]
        out = pd.DataFrame(index=idx)
        out["dp_KWK"] = r["req"]
        out["bind"] = r["bind"]
        i_kwk = nz.kanten_ids.index("KWKi")
        out["m_KWK"] = r["m"][:, i_kwk]
        out["m_S"] = r["b"][:, nz.idx["S"]]                                     # net node injection (incl. partner A's own load)
        out["m_central"] = out["m_S"] + np.where(self.gk_meas[sel], self.gk[sel], 0.0)   # flow in the new link only
        out["dp_S"] = r["dp"][:, nz.idx["S"]]
        ref_dp = {g: self.ref["dp"][sel, nz.idx[NODE[g]]] for g in NODE}
        viol = np.zeros(len(sel), bool)
        hard = {}
        for g in ("MVA", "GT", "BIO", "HW1"):
            q = r["b"][:, nz.idx[NODE[g]]]
            dpm = r["dp"][:, nz.idx[NODE[g]]]
            obs, run = self.dp_obs[g][sel], self.running_obs[g][sel]
            anchored = run & np.isfinite(obs)
            bias = np.nanmedian((self.dp_obs[g] - self.ref["dp"][:, nz.idx[NODE[g]]])[self.running_obs[g]])
            dp = np.where(anchored, obs + dpm - ref_dp[g], dpm + bias)
            on = q > 1.0
            dp = np.where(on, dp, np.nan)
            lim = self.curves[g].dp_max(np.maximum(q, 0.0), t_rl)
            out[f"m_{g}"], out[f"dp_{g}"], out[f"dp_max_{g}"] = q, dp, lim
            pret = self.p_ret_kwk[sel] + self.a_ret[g] - (dp - r["req"]) / 2
            out[f"p_ret_{g}"] = pret
            sd = self.plants_yaml[PLANT_KEY[g]].get("shutdown_bar", {})
            pr_min = sd.get("p_return_below", -np.inf)
            ps_max = min(sd.get("p_supply_above", np.inf), 25.0)
            hard[f"pump_{g}"] = np.nan_to_num(dp - lim, nan=-np.inf)
            hard[f"pret_{g}"] = np.nan_to_num(pr_min - pret, nan=-np.inf)
            hard[f"psup_{g}"] = np.nan_to_num(pret + dp - ps_max, nan=-np.inf)
        lim_k = self.curves["KWK"].dp_max(np.maximum(out["m_KWK"].to_numpy(), 0.0), t_rl)
        out["dp_max_KWK"] = lim_k
        hard["pump_KWK"] = r["req"] - lim_k
        hard["kwk_reverse"] = self.cfg["hydraulics"]["kwk_min_flow_kg_s"] - out["m_KWK"].to_numpy()
        if self.cfg["hydraulics"].get("kwk_experience_value_hard", False):      # exploratory: KWK 4.0 bar as hard limit
            hard["kwk_4bar"] = r["req"] - self.cfg["hydraulics"]["soft_limits_bar"]["KWK"]
        for k, v in hard.items():
            out[f"x_{k}"] = v                          # > 0: violation magnitude [bar] (kg/s for kwk_reverse)
            viol |= v > 1e-6
        out["violation"] = viol
        xs = out[[c for c in out if c.startswith("x_")]]
        out["violated_limit"] = np.where(viol, xs.idxmax(axis=1).str[2:], "")
        out["violation_bar"] = np.where(viol, xs.max(axis=1), 0.0)
        soft = self.cfg["hydraulics"]["soft_limits_bar"]
        out["soft_KWK"] = r["req"] > soft["KWK"]
        for g in ("MVA", "GT", "BIO"):
            out[f"soft_{g}"] = out[f"dp_{g}"] > soft[g]
        # saturation margin: lowest supply pressure among plant nodes (p_ret + Δp) vs saturation at T_VL (gauge)
        psat = _p_sat_bar_g(t_vl)
        p_sup = np.column_stack([out[f"p_ret_{g}"] + out[f"dp_{g}"] for g in ("MVA", "GT", "BIO", "HW1")] +
                                [self.p_ret_kwk[sel] + r["req"]])
        out["sat_margin_bar"] = np.nanmin(p_sup, axis=1) - psat
        # pump electricity [MW]
        eta = self.cfg["hydraulics"]["pump_efficiency"]
        rho = self.rho_r[sel]
        pw = (np.maximum(out["m_KWK"], 0) / rho * (r["req"] + self.curves["KWK"].internal(np.maximum(out["m_KWK"], 0))) * 1e5 / eta / 1e6)
        out["P_pump_KWK"] = pw
        for g in ("MVA", "GT", "BIO", "HW1"):
            q = np.maximum(out[f"m_{g}"], 0)
            out[f"P_pump_{g}"] = np.nan_to_num(q / rho * (out[f"dp_{g}"] + self.curves[g].internal(q)) * 1e5 / eta / 1e6)
        ms = np.maximum(out["m_S"] + np.where(self.gk_meas[sel], self.gk[sel], 0.0), 0.0)
        out["P_pump_S"] = ms / rho * (np.maximum(out["dp_S"], 0) + S_INTERNAL_DP_BAR) * 1e5 / eta / 1e6
        kn = node_of(self.cfg.get("new_boiler", {}).get("node", "station:V06"))
        out["dp_NEW_node"] = r["dp"][:, nz.idx[kn]]
        mn = (np.maximum(sched["Q_NEW"].to_numpy()[sel] * 1e3 / self.dh[sel], 0.0)
              if ("Q_NEW" in sched and not milp.unserved_mode(self.cfg)) else 0.0)
        out["P_pump_NEW"] = mn / rho * (np.maximum(out["dp_NEW_node"], 0) + S_INTERNAL_DP_BAR) * 1e5 / eta / 1e6
        out["dp_V06"] = r["dp"][:, nz.idx[node_of("station:V06")]] + self.versatz.get("V06", 0.0)
        out["PS1_extra_gain_bar"] = r["ps1_extra"]
        e4 = nz.kanten_ids.index("L4c")
        out["P_pump_PS1"] = np.maximum(r["m"][:, e4], 0) / rho * np.maximum(r["gain"][:, e4], 0) * 1e5 / eta / 1e6
        if keep_flows:
            out.attrs["flows"] = r["m"]
            out.attrs["b"] = r["b"]
        return out


def _p_sat_bar_g(t_c) -> np.ndarray:
    """Saturation pressure of water [bar gauge] (Antoine, 1–200 °C)."""
    t = np.asarray(t_c, float)
    p_mmhg = 10 ** (8.14019 - 1810.94 / (244.485 + t))
    return p_mmhg * 133.322 / 1e5 - 1.01325


def flow_reversals(nz: nm.Netz, flows: np.ndarray, flows_ref: np.ndarray, tol: float = 1.0) -> pd.Series:
    """Hours per edge with a flow direction opposite to the reference (|Δṁ| > tol kg/s)."""
    w = (np.sign(np.round(flows, 0)) != np.sign(np.round(flows_ref, 0))) & (np.abs(flows - flows_ref) > tol)
    return pd.Series(w.sum(axis=0), index=nz.kanten_ids)
