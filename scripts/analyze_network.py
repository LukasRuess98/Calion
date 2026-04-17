"""
================================================================================
NETZWERK-ANALYSE-SKRIPT v4.0 - WISSENSCHAFTLICHE NETZANALYSE
================================================================================
Neu in v4.0:
  · pipe_hydraulics_table: Parametertabelle aller Rohrsegmente (farbkodiert)
  · network_kpi_summary:   Dauerlinie, KPI-Cards, Boxplots, Textbefunde
  · _plot_single_pipe:     Dauerlinien VL/RL (Row 5)
  · _plot_single_node:     Knotenfluss-Schema mit annotierten ṁ-Pfeilen (Row 4)
================================================================================
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.colors import LinearSegmentedColormap
from pathlib import Path
from datetime import datetime

# ==============================================================================
# MODERNES STYLING
# ==============================================================================
plt.style.use('seaborn-v0_8-whitegrid')

COLORS = {
    'primary': '#2563EB',
    'secondary': '#7C3AED',
    'success': '#10B981',
    'warning': '#F59E0B',
    'danger': '#EF4444',
    'info': '#06B6D4',
    'dark': '#1F2937',
    'light': '#F3F4F6',
    'vorlauf': '#DC2626',
    'ruecklauf': '#2563EB',
}

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Segoe UI', 'Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 10, 'axes.titlesize': 12, 'axes.titleweight': 'bold',
    'axes.labelsize': 10, 'axes.labelweight': 'medium',
    'xtick.labelsize': 9, 'ytick.labelsize': 9, 'legend.fontsize': 9,
    'figure.titlesize': 16, 'figure.titleweight': 'bold',
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'grid.alpha': 0.3, 'grid.linestyle': '--',
    'axes.facecolor': '#FAFAFA', 'figure.facecolor': 'white',
    'axes.edgecolor': '#E5E7EB', 'axes.linewidth': 1.2,
})

# ==============================================================================
# KONFIGURATION
# ==============================================================================
CONFIG = {
    "paths": {
        "results_dir": "../output/results/thermal_network",
        "output_dir": "../output/results/plots",
        "pipes_file": "pipes/pipes_timeseries.csv",
        "nodes_file": "nodes/nodes_timeseries.csv",
    },
    "data_format": {"csv_separator": ";"},
    "selection": {
        "max_items_overview": 15,
        "detail_pipes": [
            "E1_to_V1", "E1_to_V2", "j1_to_j2", "j1_to_j5",
            "j2_to_j3", "j3_to_j4", "j5_to_V17", "V17_to_V18",
            "V18_to_j6", "j6_to_j7", "j7_to_V27",
        ],
        "detail_nodes": [
            "E_1", "j_1", "j_5", "j_7", "V_1", "V_2",
            "V_14", "V_17", "V_18", "V_27",
        ],
    },
    "limits": {
        "velocity_min_m_s": 0.3, "velocity_max_m_s": 2.5,
        "pressure_min_bar": 0.5, "temp_supply_c": 100,
        "temp_return_c": 40, "delta_T_c": 60, "cp_kJ_kgK": 4.18,
    },
    "plots": {
        "pipe_bundle_overview": True, "pipe_bundle_detail": True,
        "node_overview": True, "node_detail": True,
        "system_flow": True, "dashboard": True,
        "pipe_with_nodes": True, "mass_flow_overview": True,
        "pipe_hydraulics_table": True, "network_kpi_summary": True,
    },
    "plot_settings": {"dpi": 200, "show_plots": False},
    "scenario": {
        "name": "Memmingen L3 - Independent Zone Demands",
        "description": "27-node network with independent per-zone demand profiles",
        "period": "Januar 2025",
    },
}

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def add_fancy_title(fig, title, subtitle=None):
    fig.suptitle(title, fontsize=18, fontweight='bold', color=COLORS['dark'], y=0.98)
    if subtitle:
        fig.text(0.5, 0.94, subtitle, ha='center', fontsize=11, color='#6B7280', style='italic')


def style_axis(ax, title=None, xlabel=None, ylabel=None):
    if title:
        ax.set_title(title, pad=15, fontsize=12, fontweight='bold', color=COLORS['dark'])
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10, color='#4B5563')
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10, color='#4B5563')
    ax.grid(True, alpha=0.3, linestyle='--', color='#D1D5DB')
    ax.tick_params(colors='#6B7280')


def cb(ax):
    ax.set_facecolor('#F9FAFB')


def ml(ax, loc='upper right'):
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        leg = ax.legend(loc=loc, framealpha=0.95, edgecolor='#E5E7EB',
                        fancybox=True, shadow=False, borderpad=1)
        leg.get_frame().set_linewidth(0.5)


def stat_box(ax, text, color='#E5E7EB', x=0.98, y=0.98):
    ax.text(x, y, text, transform=ax.transAxes, ha='right', va='top',
            fontsize=9, family='monospace',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                      edgecolor=color, alpha=0.95))


# ==============================================================================
# HAUPTKLASSE
# ==============================================================================
class NetworkAnalyzer:

    def __init__(self, config):
        self.config = config
        self.df_pipes = self.df_nodes = None
        self.pipe_names, self.node_names = [], []
        self.node_types, self.network_topology = {}, {}
        self.output_path = None

    # ── VL/RL SPLIT ── Neuer Helper fuer getrennten Massenstrom ──────────
    def _get_mdot(self, pipe, which='supply'):
        """Liefert VL- (supply) oder RL- (return) Massenstrom.
        Fallback auf gemeinsame _m_dot-Spalte wenn keine getrennten vorhanden."""
        if self.df_pipes is None:
            return None
        for col_name in [f"{pipe}_m_dot_{which}", f"{pipe}_m_dot"]:
            if col_name in self.df_pipes.columns:
                return self.df_pipes[col_name]
        return None

    def _has_separate_mdot(self):
        """Prueft ob getrennte VL/RL-Massenstrom-Spalten vorhanden sind."""
        for p in self.pipe_names:
            if f"{p}_m_dot_supply" in self.df_pipes.columns:
                return True
        return False
    # ─────────────────────────────────────────────────────────────────────

    def run(self):
        self._print_header()
        self._setup_paths()
        self._load_data()
        self._extract_topology()
        self._create_all_plots()
        self._export_results()
        self._print_summary()

    def _print_header(self):
        print("\n" + "=" * 70)
        print("  NETZWERK-ANALYSE v4.0 - WISSENSCHAFTLICHE NETZANALYSE")
        print("=" * 70)
        print(f"  Szenario: {self.config['scenario']['name']}")
        print(f"  Zeitraum: {self.config['scenario']['period']}")
        print("=" * 70 + "\n")

    def _setup_paths(self):
        base = Path(__file__).parent
        self.results_dir = base / self.config["paths"]["results_dir"]
        self.output_path = base / self.config["paths"]["output_dir"]
        self.output_path.mkdir(parents=True, exist_ok=True)

    def _load_data(self):
        print("[1] DATEN LADEN")
        sep = self.config["data_format"]["csv_separator"]
        pf = self.results_dir / self.config["paths"]["pipes_file"]
        if pf.exists():
            self.df_pipes = pd.read_csv(pf, sep=sep, index_col=0)
            print(f"   Pipes: {self.df_pipes.shape}")
        nf = self.results_dir / self.config["paths"]["nodes_file"]
        if nf.exists():
            self.df_nodes = pd.read_csv(nf, sep=sep, index_col=0)
            if self.df_nodes.shape[1] == 0:
                self.df_nodes = pd.read_csv(nf, sep=",", index_col=0)
            print(f"   Nodes: {self.df_nodes.shape}")

    # ── VL/RL SPLIT ── Erkennung auch fuer _m_dot_supply / _m_dot_return ─
    def _extract_topology(self):
        print("\n[2] TOPOLOGIE EXTRAHIEREN")
        if self.df_pipes is not None:
            seen_pipes = set()
            for col in self.df_pipes.columns:
                pipe = None
                if col.endswith("_m_dot"):
                    pipe = col.replace("_m_dot", "")
                elif col.endswith("_m_dot_supply"):
                    pipe = col.replace("_m_dot_supply", "")
                elif col.endswith("_m_dot_return"):
                    pipe = col.replace("_m_dot_return", "")
                if pipe and pipe not in seen_pipes:
                    seen_pipes.add(pipe)
                    self.pipe_names.append(pipe)
                    if "_to_" in pipe:
                        parts = pipe.split("_to_")
                        if len(parts) == 2:
                            fn, tn = parts
                            if fn[0].isalpha() and len(fn) > 1 and fn[1].isdigit():
                                fn = fn[0] + "_" + fn[1:]
                            if tn[0].isalpha() and len(tn) > 1 and tn[1].isdigit():
                                tn = tn[0] + "_" + tn[1:]
                            self.network_topology[pipe] = {"from": fn, "to": tn}
        print(f"   {len(self.pipe_names)} Pipes")
        sep_info = " (getrennte VL/RL-Spalten)" if self._has_separate_mdot() else " (gemeinsame m_dot-Spalte)"
        print(f"   Massenstrom-Format:{sep_info}")

        if self.df_nodes is not None:
            seen = set()
            for col in self.df_nodes.columns:
                if "_T_supply" in col:
                    node = col.replace("_T_supply", "")
                    if node not in seen:
                        seen.add(node)
                        self.node_names.append(node)
                        if node.startswith("E_"):
                            self.node_types[node] = "producer"
                        elif node.startswith("j_"):
                            self.node_types[node] = "junction"
                        elif node.startswith("V_"):
                            self.node_types[node] = "consumer"
                        else:
                            self.node_types[node] = "unknown"
        p = sum(1 for t in self.node_types.values() if t == 'producer')
        j = sum(1 for t in self.node_types.values() if t == 'junction')
        c = sum(1 for t in self.node_types.values() if t == 'consumer')
        print(f"   {len(self.node_names)} Nodes (P:{p} J:{j} C:{c})")
    # ─────────────────────────────────────────────────────────────────────

    def _create_all_plots(self):
        print("\n[3] PLOTS ERSTELLEN")
        pl = self.config["plots"]
        if pl.get("pipe_bundle_overview"):
            self._plot_pipe_bundle_overview()
        if pl.get("pipe_bundle_detail"):
            self._plot_pipe_bundle_details()
        if pl.get("node_overview"):
            self._plot_node_overview()
        if pl.get("node_detail"):
            self._plot_node_details()
        if pl.get("system_flow"):
            self._plot_system_flow()
        if pl.get("pipe_with_nodes"):
            self._plot_pipe_with_nodes()
        if pl.get("mass_flow_overview"):
            self._plot_mass_flow_overview()
        if pl.get("dashboard"):
            self._plot_dashboard()
        if pl.get("pipe_hydraulics_table"):
            self._plot_pipe_hydraulics_table()
        if pl.get("network_kpi_summary"):
            self._plot_network_kpi_summary()

    def _save_plot(self, fig, filename):
        fig.savefig(self.output_path / filename,
                    dpi=self.config["plot_settings"]["dpi"], bbox_inches='tight')
        print(f"      {filename}")
        plt.close(fig)

    # ================================================================
    # PIPE OVERVIEW  ── VL/RL SPLIT ──
    # ================================================================
    def _plot_pipe_bundle_overview(self):
        print("   Pipe-Uebersicht...")
        mx = self.config["selection"]["max_items_overview"]
        pf = sorted(
            [(p, self._get_mdot(p, 'supply').max()
              if self._get_mdot(p, 'supply') is not None else 0)
             for p in self.pipe_names],
            key=lambda x: x[1], reverse=True)
        top = [p[0] for p in pf[:mx]]
        pc = plt.cm.viridis(np.linspace(0.2, 0.8, len(top)))

        fig = plt.figure(figsize=(20, 18))
        add_fancy_title(fig, "ROHRBUENDEL-UEBERSICHT",
                        "Vorlauf & Ruecklauf – Massenstrom getrennt")
        gs = fig.add_gridspec(4, 2, hspace=0.35, wspace=0.25,
                              top=0.90, bottom=0.06, left=0.08, right=0.95)

        # ── Row 0: VL / RL Massenstrom nebeneinander ────────────────
        for col_idx, (which, title) in enumerate([
            ('supply', 'VL Massenstrom'),
            ('return', 'RL Massenstrom'),
        ]):
            ax = fig.add_subplot(gs[0, col_idx]); cb(ax)
            for i, p in enumerate(top[:8]):
                m = self._get_mdot(p, which)
                if m is not None:
                    ax.plot(m, label=p, alpha=0.85, lw=1.8, color=pc[i])
            style_axis(ax, title, "Stunde", "kg/s"); ml(ax)

        # ── Row 1: Geschwindigkeit + Druckverlust ───────────────────
        ax = fig.add_subplot(gs[1, 0]); cb(ax)
        for i, p in enumerate(top[:8]):
            c = f"{p}_velocity"
            if c in self.df_pipes.columns:
                ax.plot(self.df_pipes[c], label=p, alpha=0.85, lw=1.8, color=pc[i])
        lim = self.config["limits"]
        ax.axhspan(0, lim["velocity_min_m_s"], alpha=0.15, color=COLORS['danger'])
        ax.axhline(y=lim["velocity_min_m_s"], color=COLORS['danger'],
                   ls='--', lw=2, alpha=0.7)
        ax.axhline(y=lim["velocity_max_m_s"], color=COLORS['warning'],
                   ls='--', lw=2, alpha=0.7)
        style_axis(ax, "Stroemungsgeschwindigkeit", "Stunde", "m/s"); ml(ax)

        ax = fig.add_subplot(gs[1, 1]); cb(ax)
        dvl, drl, dlb = [], [], []
        for p in top[:10]:
            cs = f"{p}_delta_p_supply"
            if cs in self.df_pipes.columns:
                dvl.append(self.df_pipes[cs].mean() * 1000)
                cr = f"{p}_delta_p_return"
                drl.append(self.df_pipes[cr].mean() * 1000
                           if cr in self.df_pipes.columns else 0)
                dlb.append(p)
        if dlb:
            x = np.arange(len(dlb)); w = 0.35
            ax.bar(x - w / 2, dvl, w, label='VL', color=COLORS['vorlauf'], alpha=0.8)
            ax.bar(x + w / 2, drl, w, label='RL', color=COLORS['ruecklauf'], alpha=0.8)
            ax.set_xticks(x)
            ax.set_xticklabels(dlb, rotation=45, ha='right', fontsize=8)
        style_axis(ax, "Mittlerer Druckverlust", "", "mbar"); ml(ax)

        # ── Row 2: VL / RL Temperatur ───────────────────────────────
        ax = fig.add_subplot(gs[2, 0]); cb(ax)
        for p in top[:6]:
            ci, co = f"{p}_T_supply_in", f"{p}_T_supply_out"
            if ci in self.df_pipes.columns:
                ln, = ax.plot(self.df_pipes[ci], lw=2, alpha=0.9, label=p)
                if co in self.df_pipes.columns:
                    ax.fill_between(range(len(self.df_pipes)),
                                    self.df_pipes[ci], self.df_pipes[co],
                                    alpha=0.2, color=ln.get_color())
        style_axis(ax, "VORLAUF Temperatur", "Stunde", "°C"); ml(ax)

        ax = fig.add_subplot(gs[2, 1]); cb(ax)
        for p in top[:6]:
            ci, co = f"{p}_T_return_in", f"{p}_T_return_out"
            if ci in self.df_pipes.columns:
                ln, = ax.plot(self.df_pipes[ci], lw=2, alpha=0.9, label=p)
                if co in self.df_pipes.columns:
                    ax.fill_between(range(len(self.df_pipes)),
                                    self.df_pipes[ci], self.df_pipes[co],
                                    alpha=0.2, color=ln.get_color())
        style_axis(ax, "RUECKLAUF Temperatur", "Stunde", "°C"); ml(ax)

        # ── Row 3: Waermeverluste VL / RL ────────────────────────────
        for col_idx, (suffix, title) in enumerate([
            ('Q_loss_supply', 'Waermeverluste (VL)'),
            ('Q_loss_return', 'Waermeverluste (RL)'),
        ]):
            ax = fig.add_subplot(gs[3, col_idx]); cb(ax)
            vl, lb = [], []
            for p in top[:6]:
                c = f"{p}_{suffix}"
                if c in self.df_pipes.columns:
                    vl.append(self.df_pipes[c].values * 1000); lb.append(p)
            if vl:
                ax.stackplot(range(len(self.df_pipes)), *vl, labels=lb, alpha=0.7)
            style_axis(ax, title, "Stunde", "kW"); ml(ax, 'upper left')

        self._save_plot(fig, "pipe_bundle_overview.png")

    # ================================================================
    # PIPE DETAILS  ── VL/RL SPLIT ──
    # ================================================================
    def _plot_pipe_bundle_details(self):
        print("   Pipe-Details...")
        sel = [p for p in self.config["selection"]["detail_pipes"]
               if p in self.pipe_names]
        if not sel:
            pm = sorted(
                [(p, self._get_mdot(p, 'supply').max()
                  if self._get_mdot(p, 'supply') is not None else 0)
                 for p in self.pipe_names],
                key=lambda x: x[1], reverse=True)
            sel = [p[0] for p in pm[:4]]
        for pipe in sel:
            self._plot_single_pipe(pipe)

    def _plot_single_pipe(self, pipe):
        fig = plt.figure(figsize=(18, 20))
        fig.text(0.5, 0.98, f"ROHRBUENDEL: {pipe}", ha='center', fontsize=20,
                 fontweight='bold', color=COLORS['dark'])
        fig.text(0.5, 0.955, "Vorlauf (rot) / Ruecklauf (blau) – Massenstrom getrennt",
                 ha='center', fontsize=12, color='#6B7280')
        gs = fig.add_gridspec(6, 2, hspace=0.35, wspace=0.25,
                              top=0.93, bottom=0.03, left=0.08, right=0.95)

        # ── Row 0: VL / RL Massenstrom nebeneinander ────────────────
        for col_idx, (which, title, clr) in enumerate([
            ('supply', 'VL Massenstrom', COLORS['vorlauf']),
            ('return', 'RL Massenstrom', COLORS['ruecklauf']),
        ]):
            ax = fig.add_subplot(gs[0, col_idx]); cb(ax)
            m = self._get_mdot(pipe, which)
            if m is not None:
                ax.fill_between(range(len(m)), m, alpha=0.3, color=clr)
                ax.plot(m, color=clr, lw=2.5)
                stat_box(ax,
                         f"Max: {m.max():.2f}\nMean: {m.mean():.2f}\nMin: {m.min():.2f}",
                         color=clr)
            style_axis(ax, title, "Stunde", "kg/s")

        # ── Row 1: Geschwindigkeit + VL-vs-RL-Vergleich ─────────────
        ax = fig.add_subplot(gs[1, 0]); cb(ax)
        c = f"{pipe}_velocity"
        if c in self.df_pipes.columns:
            v = self.df_pipes[c]; lim = self.config["limits"]
            ax.axhspan(0, lim["velocity_min_m_s"], alpha=0.2,
                       color=COLORS['danger'], label='Niedrig')
            ax.axhspan(lim["velocity_min_m_s"], lim["velocity_max_m_s"],
                       alpha=0.1, color=COLORS['success'], label='OK')
            ax.axhspan(lim["velocity_max_m_s"],
                       max(v.max() * 1.1, lim["velocity_max_m_s"] + 0.1),
                       alpha=0.2, color=COLORS['warning'], label='Hoch')
            ax.plot(v, color=COLORS['secondary'], lw=2.5)
            bp = (v < lim["velocity_min_m_s"]).sum() / len(v) * 100
            sc = (COLORS['success'] if bp < 10
                  else COLORS['warning'] if bp < 50
                  else COLORS['danger'])
            ax.text(0.02, 0.98, f"{bp:.0f}% unter Min",
                    transform=ax.transAxes, fontsize=10, fontweight='bold',
                    color=sc, va='top')
        style_axis(ax, "Geschwindigkeit", "Stunde", "m/s"); ml(ax)

        # VL vs RL Scatter
        ax = fig.add_subplot(gs[1, 1]); cb(ax)
        m_vl = self._get_mdot(pipe, 'supply')
        m_rl = self._get_mdot(pipe, 'return')
        if m_vl is not None and m_rl is not None:
            ax.scatter(m_vl, m_rl, alpha=0.5, s=12, color=COLORS['secondary'],
                       edgecolors='white', lw=0.3)
            max_val = max(m_vl.max(), m_rl.max()) * 1.1
            if max_val > 0:
                ax.plot([0, max_val], [0, max_val], 'k--', lw=1, alpha=0.4,
                        label='1:1 Linie')
            if m_vl.std() > 0 and m_rl.std() > 0:
                corr = np.corrcoef(m_vl, m_rl)[0, 1]
                ax.text(0.05, 0.92, f"r = {corr:.4f}",
                        transform=ax.transAxes, fontsize=11,
                        fontweight='bold', color=COLORS['primary'])
            ml(ax, 'lower right')
        else:
            ax.text(0.5, 0.5, "Keine getrennten\nDaten verfuegbar",
                    transform=ax.transAxes, ha='center', va='center',
                    fontsize=13, color='#9CA3AF')
        style_axis(ax, "VL vs RL Massenstrom", "VL (kg/s)", "RL (kg/s)")

        # ── Row 2: VL / RL Temperatur ───────────────────────────────
        ax = fig.add_subplot(gs[2, 0]); cb(ax)
        ci, co = f"{pipe}_T_supply_in", f"{pipe}_T_supply_out"
        if ci in self.df_pipes.columns:
            ax.plot(self.df_pipes[ci], color=COLORS['vorlauf'], lw=2.5,
                    label='Eintritt')
            if co in self.df_pipes.columns:
                ax.plot(self.df_pipes[co], color=COLORS['vorlauf'], lw=2,
                        ls='--', alpha=0.7, label='Austritt')
                ax.fill_between(range(len(self.df_pipes)),
                                self.df_pipes[ci], self.df_pipes[co],
                                alpha=0.2, color=COLORS['vorlauf'])
                dT = (self.df_pipes[ci] - self.df_pipes[co]).mean()
                ax.text(0.98, 0.02, f"ΔT={dT:.2f} °C", transform=ax.transAxes,
                        ha='right', fontsize=11, fontweight='bold',
                        color=COLORS['vorlauf'])
        style_axis(ax, "VORLAUF Temperatur", "Stunde", "°C"); ml(ax)

        ax = fig.add_subplot(gs[2, 1]); cb(ax)
        ci, co = f"{pipe}_T_return_in", f"{pipe}_T_return_out"
        if ci in self.df_pipes.columns:
            ax.plot(self.df_pipes[ci], color=COLORS['ruecklauf'], lw=2.5,
                    label='Eintritt')
            if co in self.df_pipes.columns:
                ax.plot(self.df_pipes[co], color=COLORS['ruecklauf'], lw=2,
                        ls='--', alpha=0.7, label='Austritt')
                ax.fill_between(range(len(self.df_pipes)),
                                self.df_pipes[ci], self.df_pipes[co],
                                alpha=0.2, color=COLORS['ruecklauf'])
        style_axis(ax, "RUECKLAUF Temperatur", "Stunde", "°C"); ml(ax)

        # ── Row 3: VL / RL Druckverlust ─────────────────────────────
        ax = fig.add_subplot(gs[3, 0]); cb(ax)
        c = f"{pipe}_delta_p_supply"
        if c in self.df_pipes.columns:
            dp = self.df_pipes[c] * 1000
            ax.fill_between(range(len(dp)), dp, alpha=0.4, color=COLORS['vorlauf'])
            ax.plot(dp, color=COLORS['vorlauf'], lw=2)
            stat_box(ax, f"Max: {dp.max():.2f} mbar")
        style_axis(ax, "VL Druckverlust", "Stunde", "mbar")

        ax = fig.add_subplot(gs[3, 1]); cb(ax)
        c = f"{pipe}_delta_p_return"
        if c in self.df_pipes.columns:
            dp = self.df_pipes[c] * 1000
            ax.fill_between(range(len(dp)), dp, alpha=0.4, color=COLORS['ruecklauf'])
            ax.plot(dp, color=COLORS['ruecklauf'], lw=2)
            stat_box(ax, f"Max: {dp.max():.2f} mbar")
        style_axis(ax, "RL Druckverlust", "Stunde", "mbar")

        # ── Row 4: Waermeverluste + Waermeabgabe ────────────────────
        ax = fig.add_subplot(gs[4, 0]); cb(ax)
        tl = 0
        cs, cr = f"{pipe}_Q_loss_supply", f"{pipe}_Q_loss_return"
        if cs in self.df_pipes.columns:
            q = self.df_pipes[cs] * 1000
            ax.fill_between(range(len(q)), q, alpha=0.5,
                            color=COLORS['vorlauf'], label='VL')
            ax.plot(q, color=COLORS['vorlauf'], lw=2)
            tl += self.df_pipes[cs].sum()
        if cr in self.df_pipes.columns:
            q = self.df_pipes[cr] * 1000
            ax.fill_between(range(len(q)), q, alpha=0.5,
                            color=COLORS['ruecklauf'], label='RL')
            ax.plot(q, color=COLORS['ruecklauf'], lw=2)
            tl += self.df_pipes[cr].sum()
        stat_box(ax, f"Sum={tl:.1f} MWh", color=COLORS['danger'])
        style_axis(ax, "Waermeverluste", "Stunde", "kW"); ml(ax)

        ax = fig.add_subplot(gs[4, 1]); cb(ax)
        c = f"{pipe}_Q_consumer"
        if c in self.df_pipes.columns:
            Q = self.df_pipes[c]
            ax.fill_between(range(len(Q)), Q, alpha=0.5, color=COLORS['success'])
            ax.plot(Q, color=COLORS['success'], lw=2.5)
            stat_box(ax, f"Sum={Q.sum():.0f} MWh", color=COLORS['success'])
        else:
            ax.text(0.5, 0.5, "Keine Waermeabgabe", transform=ax.transAxes,
                    ha='center', va='center', fontsize=14, color='#9CA3AF')
        style_axis(ax, "Waermeabgabe", "Stunde", "MW")

        # ── Row 5: Dauerlinien VL / RL + KPI-Box ────────────────────
        ax = fig.add_subplot(gs[5, 0]); cb(ax)
        m_vl = self._get_mdot(pipe, 'supply')
        m_rl = self._get_mdot(pipe, 'return')
        if m_vl is not None:
            sv = np.sort(m_vl.values)[::-1]
            ax.fill_between(np.arange(len(sv)), sv, alpha=0.35,
                            color=COLORS['vorlauf'])
            ax.plot(sv, color=COLORS['vorlauf'], lw=2.5, label='VL')
        if m_rl is not None:
            sr = np.sort(m_rl.values)[::-1]
            ax.fill_between(np.arange(len(sr)), sr, alpha=0.35,
                            color=COLORS['ruecklauf'])
            ax.plot(sr, color=COLORS['ruecklauf'], lw=2.5, ls='--', label='RL')
        ml(ax)
        style_axis(ax, "Massenstrom-Dauerlinie (sortiert)", "Stunden [h]", "ṁ [kg/s]")

        ax = fig.add_subplot(gs[5, 1]); cb(ax); ax.axis('off')
        # Scientific KPI summary box
        lines = [f"{'KENNGRÖSSEN':^42}", "─" * 42]
        if m_vl is not None:
            lines += [
                f"  ṁ_VL   max  : {m_vl.max():>9.4f} kg/s",
                f"  ṁ_VL   mean : {m_vl.mean():>9.4f} kg/s",
                f"  ṁ_VL   min  : {m_vl.min():>9.4f} kg/s",
                f"  ṁ_VL   std  : {m_vl.std():>9.4f} kg/s",
            ]
        if m_rl is not None:
            lines += [
                f"  ṁ_RL   mean : {m_rl.mean():>9.4f} kg/s",
            ]
        cv = f"{pipe}_velocity"
        if cv in self.df_pipes.columns:
            v = self.df_pipes[cv]
            lim = self.config["limits"]
            lines += ["─" * 42,
                      f"  v      max  : {v.max():>9.4f} m/s",
                      f"  v      mean : {v.mean():>9.4f} m/s",
                      f"  v<{lim['velocity_min_m_s']} m/s: {(v < lim['velocity_min_m_s']).mean()*100:>8.1f} %"]
        cs_dp = f"{pipe}_delta_p_supply"; cr_dp = f"{pipe}_delta_p_return"
        if cs_dp in self.df_pipes.columns:
            lines += ["─" * 42,
                      f"  Δp_VL  mean : {self.df_pipes[cs_dp].mean()*1000:>9.2f} mbar",
                      f"  Δp_VL  max  : {self.df_pipes[cs_dp].max()*1000:>9.2f} mbar"]
        if cr_dp in self.df_pipes.columns:
            lines.append(f"  Δp_RL  mean : {self.df_pipes[cr_dp].mean()*1000:>9.2f} mbar")
        ci_s = f"{pipe}_T_supply_in"; co_s = f"{pipe}_T_supply_out"
        if ci_s in self.df_pipes.columns and co_s in self.df_pipes.columns:
            dT_vl = (self.df_pipes[ci_s] - self.df_pipes[co_s]).mean()
            lines += ["─" * 42,
                      f"  ΔT_VL  mean : {dT_vl:>9.4f} K"]
        ci_r = f"{pipe}_T_return_in"; co_r = f"{pipe}_T_return_out"
        if ci_r in self.df_pipes.columns and co_r in self.df_pipes.columns:
            dT_rl = (self.df_pipes[ci_r] - self.df_pipes[co_r]).mean()
            lines.append(f"  ΔT_RL  mean : {dT_rl:>9.4f} K")
        ql = 0
        if f"{pipe}_Q_loss_supply" in self.df_pipes.columns:
            ql += self.df_pipes[f"{pipe}_Q_loss_supply"].sum()
        if f"{pipe}_Q_loss_return" in self.df_pipes.columns:
            ql += self.df_pipes[f"{pipe}_Q_loss_return"].sum()
        lines += ["─" * 42, f"  Q_loss total: {ql:>9.4f} MWh"]
        ax.text(0.04, 0.97, "\n".join(lines), transform=ax.transAxes,
                fontsize=8.5, va='top', family='monospace',
                bbox=dict(boxstyle='round,pad=0.6', facecolor='#F0F9FF',
                          edgecolor=COLORS['primary'], alpha=0.97, lw=1.5))
        ax.set_title("Hydraulisch-thermische Kennzahlen", fontsize=11,
                     fontweight='bold', color=COLORS['dark'], pad=10)

        self._save_plot(fig, f"pipe_bundle_{pipe}.png")

    # ================================================================
    # NODE OVERVIEW  (unveraendert – kein direkter Massenstrom)
    # ================================================================
    def _plot_node_overview(self):
        print("   Node-Uebersicht...")
        if self.df_nodes is None or not self.node_names:
            return

        fig = plt.figure(figsize=(20, 16))
        add_fancy_title(fig, "KNOTEN-UEBERSICHT", "Temperaturen & Waermebedarf")
        gs = fig.add_gridspec(3, 2, hspace=0.30, wspace=0.20,
                              top=0.90, bottom=0.06, left=0.08, right=0.95)

        prod = [n for n, t in self.node_types.items() if t == "producer"]
        junc = [n for n, t in self.node_types.items() if t == "junction"]
        cons = [n for n, t in self.node_types.items() if t == "consumer"]

        ax = fig.add_subplot(gs[0, 0]); cb(ax)
        for n in prod:
            cv, cr = f"{n}_T_supply", f"{n}_T_return"
            if cv in self.df_nodes.columns:
                ax.plot(self.df_nodes[cv], color=COLORS['vorlauf'], lw=2.5,
                        label=f'{n} VL')
            if cr in self.df_nodes.columns:
                ax.plot(self.df_nodes[cr], color=COLORS['ruecklauf'], lw=2.5,
                        ls='--', label=f'{n} RL')
        style_axis(ax, "ERZEUGER Temperaturen", "Stunde", "°C"); ml(ax)

        ax = fig.add_subplot(gs[0, 1]); cb(ax)
        cc = plt.cm.cool(np.linspace(0.2, 0.8, len(junc[:7])))
        for i, n in enumerate(junc[:7]):
            c = f"{n}_T_supply"
            if c in self.df_nodes.columns:
                ax.plot(self.df_nodes[c], label=n, alpha=0.85, lw=2, color=cc[i])
        style_axis(ax, "JUNCTIONS VL-Temperatur", "Stunde", "°C"); ml(ax)

        ax = fig.add_subplot(gs[1, 0]); cb(ax)
        cc = plt.cm.Reds(np.linspace(0.3, 0.9, len(cons[:10])))
        for i, n in enumerate(cons[:10]):
            c = f"{n}_T_supply"
            if c in self.df_nodes.columns:
                ax.plot(self.df_nodes[c], label=n, alpha=0.8, lw=1.8, color=cc[i])
        style_axis(ax, "VERBRAUCHER VL-Temperatur", "Stunde", "°C")
        ml(ax, 'lower left')

        ax = fig.add_subplot(gs[1, 1]); cb(ax)
        cc = plt.cm.Blues(np.linspace(0.3, 0.9, len(cons[:10])))
        for i, n in enumerate(cons[:10]):
            c = f"{n}_T_return"
            if c in self.df_nodes.columns:
                ax.plot(self.df_nodes[c], label=n, alpha=0.8, lw=1.8, color=cc[i])
        style_axis(ax, "VERBRAUCHER RL-Temperatur", "Stunde", "°C"); ml(ax)

        ax = fig.add_subplot(gs[2, 0]); cb(ax)
        dd, dl = [], []
        for n in cons[:8]:
            c = f"{n}_Q_demand"
            if c in self.df_nodes.columns:
                dd.append(self.df_nodes[c].values); dl.append(n)
        if dd:
            cc = plt.cm.Greens(np.linspace(0.3, 0.9, len(dd)))
            ax.stackplot(range(len(self.df_nodes)), *dd, labels=dl,
                         colors=cc, alpha=0.8)
        style_axis(ax, "Waermebedarf (gestapelt)", "Stunde", "MW")
        ml(ax, 'upper left')

        ax = fig.add_subplot(gs[2, 1]); cb(ax)
        dt = sorted(
            [(n, self.df_nodes[f"{n}_Q_demand"].sum())
             for n in cons if f"{n}_Q_demand" in self.df_nodes.columns],
            key=lambda x: x[1], reverse=True)
        if dt:
            nn, vv = zip(*dt[:15])
            yp = np.arange(len(nn))
            cc = plt.cm.YlOrRd(np.linspace(0.3, 0.9, len(nn)))
            bars = ax.barh(yp, vv, color=cc, edgecolor='white', lw=0.5)
            ax.set_yticks(yp); ax.set_yticklabels(nn, fontsize=9)
            ax.invert_yaxis()
            for b, v in zip(bars, vv):
                ax.text(v + max(vv) * 0.01, b.get_y() + b.get_height() / 2,
                        f'{v:.0f}', va='center', fontsize=8, color='#4B5563')
        style_axis(ax, "Waermebedarf pro Verbraucher", "MWh", "")

        self._save_plot(fig, "node_overview.png")

    # ================================================================
    # NODE DETAILS  ── VL/RL SPLIT fuer Ein-/Ausgehende Massenstroeme ──
    # ================================================================
    def _plot_node_details(self):
        print("   Node-Details...")
        if self.df_nodes is None or not self.node_names:
            return
        sel = [n for n in self.config["selection"]["detail_nodes"]
               if n in self.node_names]
        if not sel:
            sel = self.node_names[:5]
        for node in sel:
            self._plot_single_node(node)

    def _plot_single_node(self, node):
        nt = self.node_types.get(node, "unknown")

        fig = plt.figure(figsize=(18, 18))
        fig.text(0.5, 0.98, f"KNOTEN: {node} ({nt.upper()})", ha='center',
                 fontsize=20, fontweight='bold', color=COLORS['dark'])
        fig.text(0.5, 0.955,
                 "VL/RL Massenstroeme getrennt dargestellt",
                 ha='center', fontsize=12, color='#6B7280')
        gs = fig.add_gridspec(5, 2, hspace=0.32, wspace=0.25,
                              top=0.93, bottom=0.03, left=0.08, right=0.95)

        # ── Row 0: Temperaturen + Spreizung (unveraendert) ──────────
        ax = fig.add_subplot(gs[0, 0]); cb(ax)
        cv, cr = f"{node}_T_supply", f"{node}_T_return"
        if cv in self.df_nodes.columns:
            ax.plot(self.df_nodes[cv], color=COLORS['vorlauf'], lw=2.5,
                    label='VL')
            ax.fill_between(range(len(self.df_nodes)), self.df_nodes[cv],
                            alpha=0.2, color=COLORS['vorlauf'])
        if cr in self.df_nodes.columns:
            ax.plot(self.df_nodes[cr], color=COLORS['ruecklauf'], lw=2.5,
                    ls='--', label='RL')
        style_axis(ax, "Temperaturen", "Stunde", "°C"); ml(ax)

        ax = fig.add_subplot(gs[0, 1]); cb(ax)
        if cv in self.df_nodes.columns and cr in self.df_nodes.columns:
            dT = self.df_nodes[cv] - self.df_nodes[cr]
            ax.fill_between(range(len(dT)), dT, alpha=0.5, color=COLORS['warning'])
            ax.plot(dT, color=COLORS['warning'], lw=2.5)
            ax.axhline(y=self.config["limits"]["delta_T_c"], color=COLORS['success'],
                       ls='--', lw=2,
                       label=f'Soll: {self.config["limits"]["delta_T_c"]} °C')
            ax.axhline(y=dT.mean(), color=COLORS['danger'], ls=':', lw=2,
                       label=f'Ist: {dT.mean():.1f} °C')
            ml(ax)
        else:
            ax.text(0.5, 0.5, "Keine RL-Daten", transform=ax.transAxes,
                    ha='center', va='center', fontsize=14, color='#9CA3AF')
        style_axis(ax, "Temperaturspreizung", "Stunde", "°C")

        # ── Row 1: Waermebedarf + Massenbilanz ──────────────────────
        ax = fig.add_subplot(gs[1, 0]); cb(ax)
        cq = f"{node}_Q_demand"
        if cq in self.df_nodes.columns:
            Q = self.df_nodes[cq]
            ax.fill_between(range(len(Q)), Q, alpha=0.5, color=COLORS['success'])
            ax.plot(Q, color=COLORS['success'], lw=2.5)
            stat_box(ax,
                     f"Sum={Q.sum():.0f} MWh\nMax={Q.max():.2f} MW\n"
                     f"Mean={Q.mean():.2f} MW",
                     color=COLORS['success'])
        else:
            ax.text(0.5, 0.5, f"Kein Bedarf ({nt})", transform=ax.transAxes,
                    ha='center', va='center', fontsize=14, color='#9CA3AF')
        style_axis(ax, "Waermebedarf", "Stunde", "MW")

        # Massenbilanz (gesamt)
        inp = [p for p, t in self.network_topology.items()
               if t.get('to') == node]
        outp = [p for p, t in self.network_topology.items()
                if t.get('from') == node]

        ax = fig.add_subplot(gs[1, 1]); cb(ax)
        ti_vl = ti_rl = to_vl = to_rl = None
        for p in inp:
            m_s = self._get_mdot(p, 'supply')
            m_r = self._get_mdot(p, 'return')
            if m_s is not None:
                ti_vl = m_s if ti_vl is None else ti_vl + m_s
            if m_r is not None:
                ti_rl = m_r if ti_rl is None else ti_rl + m_r
        for p in outp:
            m_s = self._get_mdot(p, 'supply')
            m_r = self._get_mdot(p, 'return')
            if m_s is not None:
                to_vl = m_s if to_vl is None else to_vl + m_s
            if m_r is not None:
                to_rl = m_r if to_rl is None else to_rl + m_r
        # VL Bilanz
        if ti_vl is not None and to_vl is not None:
            bal_vl = ti_vl - to_vl
            ax.fill_between(range(len(bal_vl)), bal_vl, 0,
                            where=bal_vl >= 0, alpha=0.4,
                            color=COLORS['vorlauf'], label='VL +')
            ax.fill_between(range(len(bal_vl)), bal_vl, 0,
                            where=bal_vl < 0, alpha=0.4,
                            color=COLORS['vorlauf'])
            ax.plot(bal_vl, color=COLORS['vorlauf'], lw=2, label='VL Bilanz')
        # RL Bilanz
        if ti_rl is not None and to_rl is not None:
            bal_rl = ti_rl - to_rl
            ax.plot(bal_rl, color=COLORS['ruecklauf'], lw=2, ls='--',
                    label='RL Bilanz')
        ax.axhline(y=0, color=COLORS['dark'], ls='-', lw=1)
        ml(ax)
        style_axis(ax, "Massenbilanz (Ein−Aus)", "Stunde", "kg/s")

        # ── Row 2: Eingehend VL / RL nebeneinander ──────────────────
        for col_idx, (which, title, cmap_name) in enumerate([
            ('supply', f'Eingehend VL ({len(inp)} Pipes)', 'Oranges'),
            ('return', f'Eingehend RL ({len(inp)} Pipes)', 'Blues'),
        ]):
            ax = fig.add_subplot(gs[2, col_idx]); cb(ax)
            cc = plt.colormaps[cmap_name](
                np.linspace(0.4, 0.9, max(len(inp), 1)))
            total = None
            for i, p in enumerate(inp):
                m = self._get_mdot(p, which)
                if m is not None:
                    ax.plot(m, label=p, alpha=0.8, lw=1.5, color=cc[i])
                    total = m if total is None else total + m
            if total is not None:
                ax.plot(total, color=COLORS['dark'], lw=2.5, ls=':',
                        label='Summe')
            if inp:
                ml(ax)
            else:
                ax.text(0.5, 0.5, "Keine Eingaenge", transform=ax.transAxes,
                        ha='center', va='center', fontsize=14, color='#9CA3AF')
            style_axis(ax, title, "Stunde", "kg/s")

        # ── Row 3: Ausgehend VL / RL nebeneinander ──────────────────
        for col_idx, (which, title, cmap_name) in enumerate([
            ('supply', f'Ausgehend VL ({len(outp)} Pipes)', 'Reds'),
            ('return', f'Ausgehend RL ({len(outp)} Pipes)', 'Purples'),
        ]):
            ax = fig.add_subplot(gs[3, col_idx]); cb(ax)
            cc = plt.colormaps[cmap_name](
                np.linspace(0.4, 0.9, max(len(outp), 1)))
            total = None
            for i, p in enumerate(outp):
                m = self._get_mdot(p, which)
                if m is not None:
                    ax.plot(m, label=p, alpha=0.8, lw=1.5, color=cc[i])
                    total = m if total is None else total + m
            if total is not None:
                ax.plot(total, color=COLORS['dark'], lw=2.5, ls=':',
                        label='Summe')
            if outp:
                ml(ax)
            else:
                ax.text(0.5, 0.5, "Keine Ausgaenge", transform=ax.transAxes,
                        ha='center', va='center', fontsize=14, color='#9CA3AF')
            style_axis(ax, title, "Stunde", "kg/s")

        # ── Row 4: Knotenfluss-Schema (volle Breite) ─────────────────
        ax = fig.add_subplot(gs[4, :]); cb(ax)
        self._plot_node_flow_schematic(ax, node, nt)

        self._save_plot(fig, f"node_detail_{node}.png")

    # ================================================================
    # SYSTEM FLOW  ── VL/RL SPLIT ──
    # ================================================================
    def _plot_system_flow(self):
        print("   Systemfluss...")
        fig = plt.figure(figsize=(20, 18))
        add_fancy_title(fig, "SYSTEMFLUSS",
                        "Energie- und Massenbilanz – VL/RL getrennt")
        gs = fig.add_gridspec(3, 2, hspace=0.30, wspace=0.25,
                              top=0.88, bottom=0.06, left=0.08, right=0.95)

        # ── Row 0: VL / RL Gesamtmassenstrom nebeneinander ──────────
        for col_idx, (which, title, clr) in enumerate([
            ('supply', 'Gesamter VL Massenstrom', COLORS['vorlauf']),
            ('return', 'Gesamter RL Massenstrom', COLORS['ruecklauf']),
        ]):
            ax = fig.add_subplot(gs[0, col_idx]); cb(ax)
            tm = None
            for p in self.pipe_names:
                m = self._get_mdot(p, which)
                if m is not None:
                    tm = m if tm is None else tm + m
            if tm is not None:
                ax.fill_between(range(len(tm)), tm, alpha=0.4, color=clr)
                ax.plot(tm, color=clr, lw=2)
                stat_box(ax, f"Max: {tm.max():.1f}\nMean: {tm.mean():.1f}",
                         color=clr)
            style_axis(ax, title, "Stunde", "kg/s")

        # ── Row 1: Waermebedarf + Verluste ──────────────────────────
        ax = fig.add_subplot(gs[1, 0]); cb(ax)
        tq = None
        for n in self.node_names:
            c = f"{n}_Q_demand"
            if c in self.df_nodes.columns:
                tq = self.df_nodes[c] if tq is None else tq + self.df_nodes[c]
        if tq is not None:
            ax.fill_between(range(len(tq)), tq, alpha=0.4,
                            color=COLORS['success'])
            ax.plot(tq, color=COLORS['success'], lw=2)
            stat_box(ax, f"Sum={tq.sum():.0f} MWh", color=COLORS['success'])
        style_axis(ax, "Gesamter Waermebedarf", "Stunde", "MW")

        ax = fig.add_subplot(gs[1, 1]); cb(ax)
        tl = None
        for p in self.pipe_names:
            cs = f"{p}_Q_loss_supply"
            if cs in self.df_pipes.columns:
                l = self.df_pipes[cs]
                cr = f"{p}_Q_loss_return"
                if cr in self.df_pipes.columns:
                    l = l + self.df_pipes[cr]
                tl = l if tl is None else tl + l
        if tl is not None:
            ax.fill_between(range(len(tl)), tl * 1000, alpha=0.4,
                            color=COLORS['danger'])
            ax.plot(tl * 1000, color=COLORS['danger'], lw=2)
            stat_box(ax, f"Sum={tl.sum():.1f} MWh", color=COLORS['danger'])
        style_axis(ax, "Gesamte Verluste", "Stunde", "kW")

        # ── Row 2: Energiebilanz (volle Breite) ─────────────────────
        ax = fig.add_subplot(gs[2, :]); cb(ax)
        qd = tq.sum() if tq is not None else 0
        ql = tl.sum() if tl is not None else 0
        qi = qd + ql
        cats = ['Erzeugung', 'Verbraucher', 'Verluste']
        vals = [qi, qd, ql]
        cols = [COLORS['warning'], COLORS['success'], COLORS['danger']]
        bars = ax.bar(cats, vals, color=cols, alpha=0.85, edgecolor='white',
                      lw=2, width=0.5)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2,
                    b.get_height() + max(vals) * 0.02,
                    f'{v:.0f} MWh', ha='center', va='bottom',
                    fontsize=12, fontweight='bold')
        if qi > 0:
            eff = qd / qi * 100
            ec = (COLORS['success'] if eff > 95
                  else COLORS['warning'] if eff > 90
                  else COLORS['danger'])
            stat_box(ax, f"Effizienz: {eff:.1f}%", color=ec)
        style_axis(ax, "Energiebilanz", "", "MWh")

        self._save_plot(fig, "system_flow.png")

    # ================================================================
    # PIPE-NODE KOMBINATION  ── VL/RL SPLIT ──
    # ================================================================
    def _plot_pipe_with_nodes(self):
        print("   Pipe-Node-Kombinationen...")
        pwc = [p for p, t in self.network_topology.items()
               if t.get('to', '').startswith('V_')]
        if not pwc:
            pf = sorted(
                [(p, self._get_mdot(p, 'supply').max()
                  if self._get_mdot(p, 'supply') is not None else 0)
                 for p in self.pipe_names],
                key=lambda x: x[1], reverse=True)
            pwc = [p[0] for p in pf[:6]]
        else:
            pwc = pwc[:6]
        for pipe in pwc:
            self._plot_single_pipe_with_nodes(pipe)

    def _plot_single_pipe_with_nodes(self, pipe):
        topo = self.network_topology.get(pipe, {})
        fn, tn = topo.get('from', '?'), topo.get('to', '?')
        ft = self.node_types.get(fn, 'unknown')
        tt = self.node_types.get(tn, 'unknown')
        tc = {'producer': COLORS['warning'], 'junction': COLORS['info'],
              'consumer': COLORS['success'], 'unknown': '#9CA3AF'}

        fig = plt.figure(figsize=(20, 18))
        fig.text(0.5, 0.98, f"{fn}  →  [{pipe}]  →  {tn}", ha='center',
                 fontsize=18, fontweight='bold', color=COLORS['dark'])
        fig.text(0.5, 0.955, "Energiefluss – VL/RL Massenstrom getrennt",
                 ha='center', fontsize=12, color='#6B7280')
        gs = fig.add_gridspec(4, 3, hspace=0.35, wspace=0.30,
                              top=0.93, bottom=0.05, left=0.08, right=0.95)

        # ── Row 0: Schema + VL mdot + RL mdot ───────────────────────
        ax = fig.add_subplot(gs[0, 0])
        ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis('off')
        ax.set_facecolor('#F9FAFB')
        ax.add_patch(plt.Circle((2, 3.5), 1, color=tc[ft], ec='white',
                                lw=3, alpha=0.9))
        ax.text(2, 3.5, fn, ha='center', va='center', fontsize=10,
                fontweight='bold', color='white')
        ax.text(2, 1.8, ft, ha='center', fontsize=8, color='#6B7280')
        ax.annotate('', xy=(6.5, 3.5), xytext=(3.5, 3.5),
                    arrowprops=dict(arrowstyle='->', color=COLORS['dark'],
                                    lw=3))
        ax.text(5, 4.3, pipe, ha='center', fontsize=9, fontweight='bold',
                color=COLORS['dark'], style='italic')
        ax.add_patch(plt.Circle((8, 3.5), 1, color=tc[tt], ec='white',
                                lw=3, alpha=0.9))
        ax.text(8, 3.5, tn, ha='center', va='center', fontsize=10,
                fontweight='bold', color='white')
        ax.text(8, 1.8, tt, ha='center', fontsize=8, color='#6B7280')
        ax.set_title("Schema", fontsize=11, fontweight='bold',
                     color=COLORS['dark'])

        # VL Massenstrom
        ax = fig.add_subplot(gs[0, 1]); cb(ax)
        m_vl = self._get_mdot(pipe, 'supply')
        if m_vl is not None:
            ax.fill_between(range(len(m_vl)), m_vl, alpha=0.3,
                            color=COLORS['vorlauf'])
            ax.plot(m_vl, color=COLORS['vorlauf'], lw=2.5)
            stat_box(ax, f"Max:{m_vl.max():.2f}\nMean:{m_vl.mean():.2f}",
                     color=COLORS['vorlauf'])
        style_axis(ax, f"VL Massenstrom [{pipe}]", "Stunde", "kg/s")

        # RL Massenstrom
        ax = fig.add_subplot(gs[0, 2]); cb(ax)
        m_rl = self._get_mdot(pipe, 'return')
        if m_rl is not None:
            ax.fill_between(range(len(m_rl)), m_rl, alpha=0.3,
                            color=COLORS['ruecklauf'])
            ax.plot(m_rl, color=COLORS['ruecklauf'], lw=2.5)
            stat_box(ax, f"Max:{m_rl.max():.2f}\nMean:{m_rl.mean():.2f}",
                     color=COLORS['ruecklauf'])
        style_axis(ax, f"RL Massenstrom [{pipe}]", "Stunde", "kg/s")

        # ── Row 1: VL-Temperaturverlauf (volle Breite) ──────────────
        ax = fig.add_subplot(gs[1, :]); cb(ax)
        c1 = f"{fn}_T_supply"
        Tf = self.df_nodes[c1] if c1 in self.df_nodes.columns else None
        c2 = f"{pipe}_T_supply_in"
        Ti = self.df_pipes[c2] if c2 in self.df_pipes.columns else None
        c3 = f"{pipe}_T_supply_out"
        To = self.df_pipes[c3] if c3 in self.df_pipes.columns else None
        c4 = f"{tn}_T_supply"
        Tt = self.df_nodes[c4] if c4 in self.df_nodes.columns else None
        if Tf is not None:
            ax.plot(Tf, color=COLORS['vorlauf'], lw=2.5, label=f'{fn} VL')
        if Ti is not None:
            ax.plot(Ti, color=COLORS['vorlauf'], lw=2, ls='--', alpha=0.7,
                    label='Pipe ein')
        if To is not None:
            ax.plot(To, color=COLORS['vorlauf'], lw=2, ls=':', alpha=0.7,
                    label='Pipe aus')
        if Tt is not None:
            ax.plot(Tt, color='#991B1B', lw=2.5, label=f'{tn} VL')
        if Ti is not None and To is not None:
            ax.fill_between(range(len(Ti)), Ti, To, alpha=0.15,
                            color=COLORS['vorlauf'])
            dT = (Ti - To).mean()
            ax.text(0.02, 0.02, f'ΔT Pipe: {dT:.2f} °C',
                    transform=ax.transAxes, fontsize=11, fontweight='bold',
                    color=COLORS['vorlauf'],
                    bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                              alpha=0.9))
        style_axis(ax, f"VL-Temperatur: {fn} → {tn}", "Stunde", "°C")
        ml(ax)

        # ── Row 2: Bedarf + Verluste + Waermeabgabe ─────────────────
        ax = fig.add_subplot(gs[2, 0]); cb(ax)
        c = f"{tn}_Q_demand"
        if c in self.df_nodes.columns:
            Q = self.df_nodes[c]
            ax.fill_between(range(len(Q)), Q, alpha=0.5,
                            color=COLORS['success'])
            ax.plot(Q, color=COLORS['success'], lw=2)
            stat_box(ax, f"Sum={Q.sum():.0f} MWh", color=COLORS['success'])
        else:
            ax.text(0.5, 0.5, "Kein Bedarf", transform=ax.transAxes,
                    ha='center', va='center', fontsize=14, color='#9CA3AF')
        style_axis(ax, f"Bedarf {tn}", "Stunde", "MW")

        ax = fig.add_subplot(gs[2, 1]); cb(ax)
        tl = 0
        cs_c, cr_c = f"{pipe}_Q_loss_supply", f"{pipe}_Q_loss_return"
        if cs_c in self.df_pipes.columns:
            ax.fill_between(range(len(self.df_pipes)),
                            self.df_pipes[cs_c] * 1000, alpha=0.5,
                            color=COLORS['vorlauf'], label='VL')
            tl += self.df_pipes[cs_c].sum()
        if cr_c in self.df_pipes.columns:
            ax.fill_between(range(len(self.df_pipes)),
                            self.df_pipes[cr_c] * 1000, alpha=0.5,
                            color=COLORS['ruecklauf'], label='RL')
            tl += self.df_pipes[cr_c].sum()
        stat_box(ax, f"Sum={tl:.2f} MWh", color=COLORS['danger'])
        style_axis(ax, f"Verluste [{pipe}]", "Stunde", "kW"); ml(ax)

        ax = fig.add_subplot(gs[2, 2]); cb(ax)
        c = f"{pipe}_Q_consumer"
        if c in self.df_pipes.columns:
            Q = self.df_pipes[c]
            ax.fill_between(range(len(Q)), Q, alpha=0.5,
                            color=COLORS['warning'])
            ax.plot(Q, color=COLORS['warning'], lw=2)
            stat_box(ax, f"Sum={Q.sum():.0f} MWh")
        else:
            ax.text(0.5, 0.5, "Keine Abgabe", transform=ax.transAxes,
                    ha='center', va='center', fontsize=14, color='#9CA3AF')
        style_axis(ax, "Waermeabgabe", "Stunde", "MW")

        # ── Row 3: Energiebilanz (volle Breite) ─────────────────────
        ax = fig.add_subplot(gs[3, :]); cb(ax)
        md_vl = m_vl if m_vl is not None else pd.Series(
            [0] * len(self.df_pipes))
        c = f"{tn}_Q_demand"
        Qd = (self.df_nodes[c] if c in self.df_nodes.columns
              else pd.Series([0] * len(self.df_nodes)))
        cs_c = f"{pipe}_Q_loss_supply"
        cr_c = f"{pipe}_Q_loss_return"
        Qs = (self.df_pipes[cs_c] if cs_c in self.df_pipes.columns
              else pd.Series([0] * len(self.df_pipes)))
        Qr = (self.df_pipes[cr_c] if cr_c in self.df_pipes.columns
              else pd.Series([0] * len(self.df_pipes)))
        Ql = Qs + Qr
        ax.fill_between(range(len(Qd)), Qd, alpha=0.3, color=COLORS['primary'])
        ax.plot(Qd, color=COLORS['primary'], lw=2.5,
                label=f'Bedarf {tn} (MW)')
        ax.plot(md_vl * 10, color=COLORS['vorlauf'], lw=2, ls='--',
                alpha=0.8, label='VL ṁ ×10')
        md_rl = m_rl if m_rl is not None else md_vl
        ax.plot(md_rl * 10, color=COLORS['ruecklauf'], lw=2, ls=':',
                alpha=0.8, label='RL ṁ ×10')
        ax.plot(Ql * 1000, color=COLORS['danger'], lw=1.5, alpha=0.7,
                label='Verluste (kW)')
        qs, ls_ = Qd.sum(), Ql.sum()
        tot = qs + ls_
        eff = qs / tot * 100 if tot > 0 else 0
        ax.text(0.02, 0.98,
                f"Bedarf: {qs:.0f} MWh | Verluste: {ls_:.2f} MWh | "
                f"Eff: {eff:.1f}%",
                transform=ax.transAxes, fontsize=10, va='top',
                fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                          edgecolor='#E5E7EB', alpha=0.95))
        style_axis(ax, "Energiebilanz", "Stunde", "Versch. Einheiten")
        ml(ax)

        self._save_plot(fig, f"pipe_node_{pipe}.png")

    # ================================================================
    # MASSENSTROM-UEBERSICHT  ── VL/RL SPLIT ──
    # ================================================================
    def _plot_mass_flow_overview(self):
        print("   Massenstrom-Uebersicht...")
        fig = plt.figure(figsize=(20, 22))
        add_fancy_title(fig, "MASSENSTROEME & WAERMEENTNAHME",
                        "VL / RL getrennt – Systemweite Analyse")
        gs = fig.add_gridspec(5, 3, hspace=0.35, wspace=0.30,
                              top=0.90, bottom=0.04, left=0.08, right=0.95)

        pf = sorted(
            [(p,
              self._get_mdot(p, 'supply').mean()
              if self._get_mdot(p, 'supply') is not None else 0,
              self._get_mdot(p, 'supply').max()
              if self._get_mdot(p, 'supply') is not None else 0)
             for p in self.pipe_names],
            key=lambda x: x[2], reverse=True)

        # ── Row 0: VL Barplot + RL Barplot + VL vs RL Scatter ────────
        for col_idx, (which, title, clr) in enumerate([
            ('supply', 'VL Massenstrom pro Pipe', COLORS['vorlauf']),
            ('return', 'RL Massenstrom pro Pipe', COLORS['ruecklauf']),
        ]):
            ax = fig.add_subplot(gs[0, col_idx]); cb(ax)
            pdata = []
            for p, _, _ in pf[:15]:
                m = self._get_mdot(p, which)
                if m is not None:
                    pdata.append((p, m.mean(), m.max()))
            if pdata:
                pp, mm, mx = zip(*pdata)
                yp = np.arange(len(pp))
                ax.barh(yp, mx, alpha=0.3, color=clr, label='Max')
                ax.barh(yp, mm, alpha=0.8, color=clr, label='Mittel')
                ax.set_yticks(yp)
                ax.set_yticklabels(pp, fontsize=7)
                ax.invert_yaxis(); ml(ax)
            style_axis(ax, title, "kg/s", "")

        ax = fig.add_subplot(gs[0, 2]); cb(ax)
        for i, (p, _, _) in enumerate(pf[:10]):
            m_vl = self._get_mdot(p, 'supply')
            m_rl = self._get_mdot(p, 'return')
            if m_vl is not None and m_rl is not None:
                ax.scatter(m_vl.mean(), m_rl.mean(), s=60, alpha=0.8,
                           edgecolors='white', lw=0.5, zorder=3)
                ax.annotate(p, (m_vl.mean(), m_rl.mean()), fontsize=6,
                            xytext=(3, 3), textcoords='offset points')
        max_all = max(
            (self._get_mdot(p, 'supply').mean()
             for p, _, _ in pf[:10]
             if self._get_mdot(p, 'supply') is not None),
            default=1) * 1.2
        ax.plot([0, max_all], [0, max_all], 'k--', lw=1, alpha=0.4,
                label='1:1')
        ml(ax, 'lower right')
        style_axis(ax, "VL vs RL (Mittelwerte)", "VL (kg/s)", "RL (kg/s)")

        # ── Row 1: Top 5 VL + Top 5 RL Zeitverlaeufe ────────────────
        for col_span, (which, title, clr_base) in [
            (slice(0, 2), ('supply', 'Top 5 VL Zeitverlaeufe', 'Reds')),
            (slice(1, 3), ('return', 'Top 5 RL Zeitverlaeufe', 'Blues')),
        ]:
            pass  # handled below

        ax = fig.add_subplot(gs[1, :2]); cb(ax)
        cc = plt.cm.Reds(np.linspace(0.3, 0.9, 5))
        for i, (p, _, _) in enumerate(pf[:5]):
            m = self._get_mdot(p, 'supply')
            if m is not None:
                ax.plot(m, label=p, lw=2, alpha=0.85, color=cc[i])
        style_axis(ax, "Top 5 VL Zeitverlaeufe", "Stunde", "kg/s"); ml(ax)

        ax = fig.add_subplot(gs[1, 2]); cb(ax)
        cc = plt.cm.Blues(np.linspace(0.3, 0.9, 5))
        for i, (p, _, _) in enumerate(pf[:5]):
            m = self._get_mdot(p, 'return')
            if m is not None:
                ax.plot(m, label=p, lw=2, alpha=0.85, color=cc[i])
        style_axis(ax, "Top 5 RL Zeitverlaeufe", "Stunde", "kg/s"); ml(ax)

        # ── Row 2: Korrelation + Stacked Demand ─────────────────────
        ax = fig.add_subplot(gs[2, 0]); cb(ax)
        tq, tm_ = None, None
        for n in self.node_names:
            c = f"{n}_Q_demand"
            if c in self.df_nodes.columns:
                tq = (self.df_nodes[c] if tq is None
                      else tq + self.df_nodes[c])
        for p in self.pipe_names:
            m = self._get_mdot(p, 'supply')
            if m is not None:
                tm_ = m if tm_ is None else tm_ + m
        if tq is not None and tm_ is not None:
            ax.scatter(tm_, tq, alpha=0.6, s=15, c=range(len(tm_)),
                       cmap='viridis', edgecolors='white', lw=0.5)
            if tm_.std() > 0 and tq.std() > 0:
                corr = np.corrcoef(tm_, tq)[0, 1]
            else:
                corr = 0.0
            ax.text(0.02, 0.98, f"r = {corr:.3f}", transform=ax.transAxes,
                    fontsize=12, fontweight='bold', va='top',
                    color=COLORS['primary'])
        style_axis(ax, "Korrelation VL ṁ ↔ Q", "Σ ṁ_VL (kg/s)",
                   "Σ Q (MW)")

        ax = fig.add_subplot(gs[2, 1:]); cb(ax)
        cons = [n for n, t in self.node_types.items() if t == 'consumer']
        cd = sorted(
            [(c, self.df_nodes[f"{c}_Q_demand"].sum())
             for c in cons if f"{c}_Q_demand" in self.df_nodes.columns],
            key=lambda x: x[1], reverse=True)
        Qd, lb = [], []
        for c, _ in cd[:8]:
            col_n = f"{c}_Q_demand"
            if col_n in self.df_nodes.columns:
                Qd.append(self.df_nodes[col_n].values); lb.append(c)
        if Qd:
            cc = plt.cm.Spectral(np.linspace(0.2, 0.8, len(Qd)))
            ax.stackplot(range(len(Qd[0])), *Qd, labels=lb, colors=cc,
                         alpha=0.8)
            ml(ax, 'upper left')
        style_axis(ax, "Waermeentnahme (Top 8)", "Stunde", "MW")

        # ── Row 3: Temperaturabfall + Temp-vs-Bedarf ─────────────────
        ax = fig.add_subplot(gs[3, :2]); cb(ax)
        td = []
        for p in self.pipe_names:
            ci, co = f"{p}_T_supply_in", f"{p}_T_supply_out"
            if ci in self.df_pipes.columns and co in self.df_pipes.columns:
                td.append((p,
                           (self.df_pipes[ci] - self.df_pipes[co]).mean(),
                           self.df_pipes[ci].mean()))
        if td:
            td.sort(key=lambda x: x[2], reverse=True)
            pp, dr, ti = zip(*td[:20])
            cc = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(pp)))
            xp = np.arange(len(pp))
            ax.bar(xp, dr, color=cc, alpha=0.85, edgecolor='white', lw=0.5)
            ax.set_xticks(xp)
            ax.set_xticklabels(pp, rotation=45, ha='right', fontsize=7)
            ax2 = ax.twinx()
            ax2.plot(xp, ti, 'ko-', ms=4, lw=1.5, alpha=0.7)
            ax2.set_ylabel("T_in (°C)", fontsize=10, color='#4B5563')
        style_axis(ax, "VL-Temperaturabfall pro Pipe", "", "ΔT (°C)")

        ax = fig.add_subplot(gs[3, 2]); cb(ax)
        Tc, Qc, nm = [], [], []
        for n in cons:
            ct, cq = f"{n}_T_supply", f"{n}_Q_demand"
            if ct in self.df_nodes.columns and cq in self.df_nodes.columns:
                Tc.append(self.df_nodes[ct].mean())
                Qc.append(self.df_nodes[cq].sum())
                nm.append(n)
        if Tc:
            ax.scatter(Tc, Qc, c=range(len(nm)), cmap='viridis', s=80,
                       alpha=0.8, edgecolors='white', lw=1)
            for i, n in enumerate(nm):
                ax.annotate(n, (Tc[i], Qc[i]), fontsize=7, xytext=(3, 3),
                            textcoords='offset points')
        style_axis(ax, "Temp vs Bedarf", "VL-Temp (°C)", "Bedarf (MWh)")

        # ── Row 4: Energiefluss-Schema ───────────────────────────────
        ax = fig.add_subplot(gs[4, :])
        ax.set_xlim(0, 10); ax.set_ylim(0, 4); ax.axis('off')
        ax.set_facecolor('#F9FAFB')
        qdt = tq.sum() if tq is not None else 0
        qlv = sum(self.df_pipes[f"{p}_Q_loss_supply"].sum()
                  for p in self.pipe_names
                  if f"{p}_Q_loss_supply" in self.df_pipes.columns)
        qlr = sum(self.df_pipes[f"{p}_Q_loss_return"].sum()
                  for p in self.pipe_names
                  if f"{p}_Q_loss_return" in self.df_pipes.columns)
        qlt = qlv + qlr
        qi = qdt + qlt
        eff = qdt / qi * 100 if qi > 0 else 0
        lp = qlt / qi * 100 if qi > 0 else 0

        for x, w, col, txt in [
            (0.3, 1.8, COLORS['warning'],
             f"ERZEUGUNG\n{qi:.0f} MWh"),
            (3.5, 2.5, '#E5E7EB',
             f"WAERMENETZ\nEff: {eff:.1f}%"),
            (7.2, 2.2, COLORS['success'],
             f"VERBRAUCHER\n{qdt:.0f} MWh"),
        ]:
            bx = FancyBboxPatch((x, 1), w, 2, boxstyle="round,pad=0.2",
                                facecolor=col, alpha=0.7, edgecolor='white',
                                lw=2)
            ax.add_patch(bx)
            ax.text(x + w / 2, 2, txt, ha='center', va='center',
                    fontsize=11, fontweight='bold')

        bx = FancyBboxPatch((3.8, 0), 1.9, 0.8, boxstyle="round,pad=0.1",
                            facecolor=COLORS['danger'], alpha=0.6,
                            edgecolor='white', lw=2)
        ax.add_patch(bx)
        ax.text(4.75, 0.4,
                f"VERLUSTE\n{qlt:.1f} MWh ({lp:.1f}%)",
                ha='center', va='center', fontsize=9, fontweight='bold')

        ax.annotate('', xy=(3.3, 2), xytext=(2.3, 2),
                    arrowprops=dict(arrowstyle='->', color=COLORS['warning'],
                                    lw=3))
        ax.annotate('', xy=(7.0, 2), xytext=(6.2, 2),
                    arrowprops=dict(arrowstyle='->', color=COLORS['success'],
                                    lw=3))
        ax.annotate('', xy=(4.75, 0.9), xytext=(4.75, 1.0),
                    arrowprops=dict(arrowstyle='->', color=COLORS['danger'],
                                    lw=2))
        ax.set_title("ENERGIEFLUSS", fontsize=14, fontweight='bold',
                     color=COLORS['dark'], pad=10)

        self._save_plot(fig, "mass_flow_system_overview.png")

    # ================================================================
    # DASHBOARD  ── VL/RL SPLIT ──
    # ================================================================
    def _plot_dashboard(self):
        print("   Dashboard...")
        fig = plt.figure(figsize=(24, 22))
        sc = self.config["scenario"]
        fig.text(0.5, 0.98, "NETZWERK-DASHBOARD", ha='center',
                 fontsize=22, fontweight='bold', color=COLORS['dark'])
        fig.text(0.5, 0.96,
                 f"{sc['name']}  |  {sc['period']}  |  VL/RL getrennt",
                 ha='center', fontsize=13, color='#6B7280')
        gs = fig.add_gridspec(5, 4, hspace=0.35, wspace=0.30,
                              top=0.94, bottom=0.04, left=0.06, right=0.96)

        # ── Row 0: VL mdot, RL mdot, v-Verteilung, Q + Verluste ────
        for col_idx, (which, title, clr) in enumerate([
            ('supply', 'VL Σ ṁ', COLORS['vorlauf']),
            ('return', 'RL Σ ṁ', COLORS['ruecklauf']),
        ]):
            ax = fig.add_subplot(gs[0, col_idx]); cb(ax)
            tm = None
            for p in self.pipe_names:
                m = self._get_mdot(p, which)
                if m is not None:
                    tm = m if tm is None else tm + m
            if tm is not None:
                ax.fill_between(range(len(tm)), tm, alpha=0.4, color=clr)
                ax.plot(tm, color=clr, lw=2)
            style_axis(ax, title, "h", "kg/s")

        ax = fig.add_subplot(gs[0, 2]); cb(ax)
        av = [self.df_pipes[f"{p}_velocity"].values
              for p in self.pipe_names
              if f"{p}_velocity" in self.df_pipes.columns]
        if av:
            ax.hist(np.concatenate(av), bins=50, color=COLORS['success'],
                    alpha=0.7, edgecolor='white')
            ax.axvline(x=self.config["limits"]["velocity_min_m_s"],
                       color=COLORS['danger'], ls='--', lw=2)
        style_axis(ax, "v-Verteilung", "m/s", "n")

        ax = fig.add_subplot(gs[0, 3]); cb(ax)
        tq = None
        for n in self.node_names:
            c = f"{n}_Q_demand"
            if c in self.df_nodes.columns:
                tq = (self.df_nodes[c] if tq is None
                      else tq + self.df_nodes[c])
        tl = None
        for p in self.pipe_names:
            cs_c = f"{p}_Q_loss_supply"
            if cs_c in self.df_pipes.columns:
                l = self.df_pipes[cs_c].copy()
                cr_c = f"{p}_Q_loss_return"
                if cr_c in self.df_pipes.columns:
                    l = l + self.df_pipes[cr_c]
                tl = l if tl is None else tl + l
        if tl is None:
            tl = pd.Series([0] * len(self.df_pipes))
        if tq is not None:
            ax.fill_between(range(len(tq)), tq, alpha=0.3,
                            color=COLORS['success'])
            ax.plot(tq, color=COLORS['success'], lw=2,
                    label=f'Q ({tq.sum():.0f} MWh)')
        ax2 = ax.twinx()
        ax2.plot(tl * 1000, color=COLORS['danger'], lw=1.5, alpha=0.7,
                 label=f'Loss ({tl.sum():.1f} MWh)')
        ax2.set_ylabel("Verluste (kW)", fontsize=8, color=COLORS['danger'])
        style_axis(ax, "Q + Verluste", "h", "MW")
        # Combine legends
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, loc='upper right', fontsize=7,
                  framealpha=0.9)

        # ── Row 1: VL Heatmap + RL Heatmap ──────────────────────────
        for col_span, (which, title, cmap_name) in [
            (slice(0, 2), ('supply', 'VL Massenstrom-Heatmap', 'Reds')),
            (slice(2, 4), ('return', 'RL Massenstrom-Heatmap', 'Blues')),
        ]:
            ax = fig.add_subplot(gs[1, col_span])
            md = []
            pipe_labels = []
            for p in self.pipe_names:
                m = self._get_mdot(p, which)
                if m is not None:
                    md.append(m.values)
                    pipe_labels.append(p)
            if md:
                im = ax.imshow(np.array(md), aspect='auto', cmap=cmap_name,
                               interpolation='nearest')
                ax.set_yticks(range(len(pipe_labels)))
                ax.set_yticklabels(pipe_labels, fontsize=5)
                plt.colorbar(im, ax=ax, label='kg/s', shrink=0.8, pad=0.02)
            style_axis(ax, title, "Stunde", "")

        # ── Row 2: Q-Heatmap + Temp-Profil ──────────────────────────
        ax = fig.add_subplot(gs[2, :2])
        qd, qn = [], []
        for n in self.node_names:
            c = f"{n}_Q_demand"
            if c in self.df_nodes.columns and self.df_nodes[c].max() > 0:
                qd.append(self.df_nodes[c].values); qn.append(n)
        if qd:
            im = ax.imshow(np.array(qd), aspect='auto', cmap='YlOrRd',
                           interpolation='nearest')
            ax.set_yticks(range(len(qn)))
            ax.set_yticklabels(qn, fontsize=7)
            plt.colorbar(im, ax=ax, label='MW', shrink=0.8, pad=0.02)
        style_axis(ax, "Waermebedarf-Heatmap", "Stunde", "")

        ax = fig.add_subplot(gs[2, 2:]); cb(ax)
        td = []
        for n in self.node_names:
            cv, cr = f"{n}_T_supply", f"{n}_T_return"
            if cv in self.df_nodes.columns:
                td.append({
                    'n': n,
                    'vl': self.df_nodes[cv].iloc[0],
                    'rl': (self.df_nodes[cr].iloc[0]
                           if cr in self.df_nodes.columns else np.nan),
                })
        if td:
            df = pd.DataFrame(td)
            x = np.arange(len(df)); w = 0.35
            ax.bar(x - w / 2, df['vl'], w, label='VL',
                   color=COLORS['vorlauf'], alpha=0.8)
            ax.bar(x + w / 2, df['rl'].fillna(0), w, label='RL',
                   color=COLORS['ruecklauf'], alpha=0.8)
            ax.set_xticks(x)
            ax.set_xticklabels(df['n'], rotation=45, ha='right', fontsize=6)
            ml(ax)
        style_axis(ax, "Temperaturprofil (t=0)", "", "°C")

        # ── Row 3: Top Q bar + Energieeffizienz ─────────────────────
        ax = fig.add_subplot(gs[3, :2]); cb(ax)
        dt = sorted(
            [(n, self.df_nodes[f"{n}_Q_demand"].sum())
             for n in self.node_names
             if f"{n}_Q_demand" in self.df_nodes.columns],
            key=lambda x: x[1], reverse=True)[:12]
        if dt:
            nn, vv = zip(*dt)
            ax.barh(range(len(nn)), vv, color=COLORS['success'], alpha=0.7)
            ax.set_yticks(range(len(nn)))
            ax.set_yticklabels(nn, fontsize=8)
            ax.invert_yaxis()
        style_axis(ax, "Top Waermebedarf", "MWh", "")

        ax = fig.add_subplot(gs[3, 2:]); cb(ax)
        Qd_total = tq.sum() if tq is not None else 0
        Ql_total = tl.sum()
        Qi_total = Qd_total + Ql_total
        eff = Qd_total / Qi_total * 100 if Qi_total > 0 else 0
        cats = ['Erzeugung', 'Bedarf', 'Verluste']
        vals = [Qi_total, Qd_total, Ql_total]
        cols = [COLORS['warning'], COLORS['success'], COLORS['danger']]
        bars = ax.bar(cats, vals, color=cols, alpha=0.85, edgecolor='white',
                      lw=2, width=0.5)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2,
                    b.get_height() + max(vals) * 0.02,
                    f'{v:.0f}', ha='center', va='bottom', fontsize=9,
                    fontweight='bold')
        stat_box(ax, f"η = {eff:.1f}%",
                 color=COLORS['success'] if eff > 95 else COLORS['warning'])
        style_axis(ax, "Energiebilanz", "", "MWh")

        # ── Row 4: Stats + Warnings ─────────────────────────────────
        ax = fig.add_subplot(gs[4, :2]); ax.axis('off')
        vm = max(
            (self.df_pipes[f"{p}_velocity"].max()
             for p in self.pipe_names
             if f"{p}_velocity" in self.df_pipes.columns),
            default=0)
        va = (np.mean([self.df_pipes[f"{p}_velocity"].mean()
                       for p in self.pipe_names
                       if f"{p}_velocity" in self.df_pipes.columns])
              if self.pipe_names else 0)
        sep_txt = "Ja" if self._has_separate_mdot() else "Nein (Fallback)"

        txt = (
            f"NETZWERK\n{'=' * 30}\n"
            f"Pipes:       {len(self.pipe_names)}\n"
            f"Nodes:       {len(self.node_names)}\n"
            f"  Producer:  "
            f"{sum(1 for t in self.node_types.values() if t == 'producer')}\n"
            f"  Junction:  "
            f"{sum(1 for t in self.node_types.values() if t == 'junction')}\n"
            f"  Consumer:  "
            f"{sum(1 for t in self.node_types.values() if t == 'consumer')}\n"
            f"  VL/RL sep: {sep_txt}\n\n"
            f"HYDRAULIK\n{'=' * 30}\n"
            f"v_max:   {vm:.4f} m/s\n"
            f"v_mean:  {va:.4f} m/s\n\n"
            f"ENERGIE\n{'=' * 30}\n"
            f"Bedarf:    {Qd_total:>10.0f} MWh\n"
            f"Verluste:  {Ql_total:>10.1f} MWh\n"
            f"Effizienz: {eff:>10.1f} %")
        ax.text(0.02, 0.95, txt, transform=ax.transAxes, fontsize=10,
                va='top', family='monospace',
                bbox=dict(boxstyle='round', facecolor='#F9FAFB',
                          edgecolor='#E5E7EB', alpha=0.95))

        ax = fig.add_subplot(gs[4, 2:]); ax.axis('off')
        vb = sum(
            (self.df_pipes[f"{p}_velocity"] < 0.3).sum()
            for p in self.pipe_names
            if f"{p}_velocity" in self.df_pipes.columns)
        tv = len(self.df_pipes) * max(len(self.pipe_names), 1)
        warns = []
        if tv > 0 and vb / tv > 0.5:
            warns.append(f"[!] {vb / tv * 100:.0f}% v unter Minimum")
            warns.append("    -> Durchmesser reduzieren")
        if eff < 95:
            warns.append(f"[!] Effizienz {eff:.1f}% < 95%")
        if not self._has_separate_mdot():
            warns.append("[i] VL/RL ṁ identisch (keine getrennten Spalten)")
        if not warns:
            warns.append("[OK] Keine kritischen Befunde")
        wt = "BEWERTUNG\n" + "=" * 40 + "\n\n" + "\n".join(warns)
        ax.text(0.02, 0.95, wt, transform=ax.transAxes, fontsize=10,
                va='top', family='monospace',
                bbox=dict(boxstyle='round', facecolor='#FFFBEB',
                          edgecolor='#F59E0B', alpha=0.95))

        self._save_plot(fig, "dashboard.png")

    # ================================================================
    # KNOTENFLUSS-SCHEMA HELPER
    # ================================================================
    def _plot_node_flow_schematic(self, ax, node, nt):
        """Annotiertes Pfeil-Schema: ṁ und T aller Verbindungen am Knoten."""
        ax.set_xlim(0, 14); ax.set_ylim(0, 8)
        ax.axis('off')
        ax.set_facecolor('#F8FAFC')

        inp = [p for p, t in self.network_topology.items() if t.get('to') == node]
        outp = [p for p, t in self.network_topology.items() if t.get('from') == node]

        tc = {'producer': COLORS['warning'], 'junction': COLORS['info'],
              'consumer': COLORS['success'], 'unknown': '#9CA3AF'}
        nc = tc.get(nt, '#9CA3AF')

        cx, cy = 7, 4
        circle = plt.Circle((cx, cy), 0.9, color=nc, ec='white', lw=3,
                             alpha=0.93, zorder=5)
        ax.add_patch(circle)
        ax.text(cx, cy + 0.15, node, ha='center', va='center', fontsize=9,
                fontweight='bold', color='white', zorder=6)
        ax.text(cx, cy - 0.35, nt[:4].upper(), ha='center', va='center',
                fontsize=7, color='white', zorder=6, alpha=0.85)

        def _y_pos(idx, total):
            if total == 1:
                return 4.0
            return 1.5 + 5.0 * idx / (total - 1)

        # ── Incoming connections (left side) ─────────────────────────
        for i, p in enumerate(inp):
            yp = _y_pos(i, len(inp))
            topo = self.network_topology.get(p, {})
            fn = topo.get('from', p)
            m_vl = self._get_mdot(p, 'supply')
            m_rl = self._get_mdot(p, 'return')
            m_vl_v = m_vl.mean() if m_vl is not None else 0.0
            m_rl_v = m_rl.mean() if m_rl is not None else 0.0
            t_in_c = f"{p}_T_supply_out"
            t_rl_c = f"{p}_T_return_in"
            T_in = (self.df_pipes[t_in_c].mean()
                    if t_in_c in self.df_pipes.columns else None)
            T_rl = (self.df_pipes[t_rl_c].mean()
                    if t_rl_c in self.df_pipes.columns else None)

            # VL arrow: left → centre (red)
            ax.annotate('', xy=(cx - 0.95, cy + 0.22), xytext=(3.5, yp + 0.22),
                        arrowprops=dict(arrowstyle='->', color=COLORS['vorlauf'],
                                        lw=2.5), zorder=4)
            lbl_vl = f"←{fn}  VL  ṁ={m_vl_v:.3f} kg/s"
            if T_in is not None:
                lbl_vl += f"  T={T_in:.1f}°C"
            ax.text(1.8, yp + 0.62, lbl_vl, ha='left', fontsize=7.5,
                    color=COLORS['vorlauf'], fontweight='bold', family='monospace')

            # RL arrow: centre → left (blue)
            ax.annotate('', xy=(3.5, yp - 0.22), xytext=(cx - 0.95, cy - 0.22),
                        arrowprops=dict(arrowstyle='->', color=COLORS['ruecklauf'],
                                        lw=2.5), zorder=4)
            lbl_rl = f"→{fn}  RL  ṁ={m_rl_v:.3f} kg/s"
            if T_rl is not None:
                lbl_rl += f"  T={T_rl:.1f}°C"
            ax.text(1.8, yp - 0.62, lbl_rl, ha='left', fontsize=7.5,
                    color=COLORS['ruecklauf'], family='monospace')

        # ── Outgoing connections (right side) ────────────────────────
        for i, p in enumerate(outp):
            yp = _y_pos(i, len(outp))
            topo = self.network_topology.get(p, {})
            tn_n = topo.get('to', p)
            m_vl = self._get_mdot(p, 'supply')
            m_rl = self._get_mdot(p, 'return')
            m_vl_v = m_vl.mean() if m_vl is not None else 0.0
            m_rl_v = m_rl.mean() if m_rl is not None else 0.0
            t_out_c = f"{p}_T_supply_in"
            t_rl_c = f"{p}_T_return_out"
            T_out = (self.df_pipes[t_out_c].mean()
                     if t_out_c in self.df_pipes.columns else None)
            T_rl = (self.df_pipes[t_rl_c].mean()
                    if t_rl_c in self.df_pipes.columns else None)

            # VL arrow: centre → right (red)
            ax.annotate('', xy=(10.5, yp + 0.22), xytext=(cx + 0.95, cy + 0.22),
                        arrowprops=dict(arrowstyle='->', color=COLORS['vorlauf'],
                                        lw=2.5), zorder=4)
            lbl_vl = f"{tn_n}→  VL  ṁ={m_vl_v:.3f} kg/s"
            if T_out is not None:
                lbl_vl += f"  T={T_out:.1f}°C"
            ax.text(10.7, yp + 0.62, lbl_vl, ha='left', fontsize=7.5,
                    color=COLORS['vorlauf'], fontweight='bold', family='monospace')

            # RL arrow: right → centre (blue)
            ax.annotate('', xy=(cx + 0.95, cy - 0.22), xytext=(10.5, yp - 0.22),
                        arrowprops=dict(arrowstyle='->', color=COLORS['ruecklauf'],
                                        lw=2.5), zorder=4)
            lbl_rl = f"{tn_n}←  RL  ṁ={m_rl_v:.3f} kg/s"
            if T_rl is not None:
                lbl_rl += f"  T={T_rl:.1f}°C"
            ax.text(10.7, yp - 0.62, lbl_rl, ha='left', fontsize=7.5,
                    color=COLORS['ruecklauf'], family='monospace')

        # ── Heat extraction for consumers ─────────────────────────────
        cq = f"{node}_Q_demand"
        if cq in self.df_nodes.columns:
            Q_mean = self.df_nodes[cq].mean()
            Q_sum = self.df_nodes[cq].sum()
            ax.annotate('', xy=(cx, 0.55), xytext=(cx, cy - 0.92),
                        arrowprops=dict(arrowstyle='->', color=COLORS['success'],
                                        lw=3.5, linestyle='dashed'), zorder=4)
            ax.text(cx + 0.15, 0.25,
                    f"Q̇_mean={Q_mean:.4f} MW   Q_sum={Q_sum:.1f} MWh",
                    ha='center', fontsize=9, fontweight='bold',
                    color=COLORS['success'],
                    bbox=dict(boxstyle='round,pad=0.35', facecolor='#D1FAE5',
                              edgecolor=COLORS['success'], alpha=0.95))

        # ── Mixing temperature annotation for junctions ───────────────
        if nt == 'junction':
            T_mix = self._compute_mixing_temperature(node)
            if T_mix is not None:
                T_mix_mean = T_mix.mean()
                T_node_c = f"{node}_T_supply"
                T_node = (self.df_nodes[T_node_c].mean()
                          if T_node_c in self.df_nodes.columns else None)
                mix_txt = f"T_mix (ṁ-gewogen) = {T_mix_mean:.2f} °C"
                if T_node is not None:
                    mix_txt += f"   T_node = {T_node:.2f} °C"
                ax.text(cx, cy + 1.35, mix_txt, ha='center', fontsize=8.5,
                        fontweight='bold', color=COLORS['info'],
                        bbox=dict(boxstyle='round,pad=0.35', facecolor='#E0F2FE',
                                  edgecolor=COLORS['info'], alpha=0.95))

        # ── Mass balance annotation ───────────────────────────────────
        sum_in_vl = sum(
            self._get_mdot(p, 'supply').mean()
            for p in inp if self._get_mdot(p, 'supply') is not None)
        sum_out_vl = sum(
            self._get_mdot(p, 'supply').mean()
            for p in outp if self._get_mdot(p, 'supply') is not None)
        if sum_in_vl > 0 or sum_out_vl > 0:
            imbalance = abs(sum_in_vl - sum_out_vl)
            bal_color = COLORS['success'] if imbalance < 0.01 else COLORS['warning']
            ax.text(cx, 7.55,
                    f"Σṁ_in={sum_in_vl:.3f} kg/s   Σṁ_out={sum_out_vl:.3f} kg/s"
                    f"   |Δṁ|={imbalance:.4f} kg/s",
                    ha='center', fontsize=9, fontweight='bold', color=bal_color,
                    bbox=dict(boxstyle='round,pad=0.35', facecolor='white',
                              edgecolor=bal_color, alpha=0.95))

        ax.plot([], [], color=COLORS['vorlauf'], lw=2.5, label='Vorlauf (VL)')
        ax.plot([], [], color=COLORS['ruecklauf'], lw=2.5, label='Rücklauf (RL)')
        if cq in self.df_nodes.columns:
            ax.plot([], [], color=COLORS['success'], lw=2.5, ls='--',
                    label='Wärmeentnahme')
        ax.legend(loc='lower left', fontsize=8.5, framealpha=0.92,
                  edgecolor='#E5E7EB')
        ax.set_title(
            f"Knotenfluss-Schema: {node} ({nt.upper()})  —  "
            f"{len(inp)} Eingänge / {len(outp)} Ausgänge",
            fontsize=11, fontweight='bold', color=COLORS['dark'], pad=8)

    def _compute_mixing_temperature(self, node):
        """ṁ-gewichtete Mischtemperatur an einem Knoten (VL)."""
        inp = [p for p, t in self.network_topology.items() if t.get('to') == node]
        numerator = denominator = None
        for p in inp:
            m = self._get_mdot(p, 'supply')
            c_tout = f"{p}_T_supply_out"
            if m is not None and c_tout in self.df_pipes.columns:
                T = self.df_pipes[c_tout]
                aligned_m = m.reindex(T.index) if hasattr(m, 'reindex') else m
                term = aligned_m * T
                numerator = term if numerator is None else numerator + term
                denominator = aligned_m if denominator is None else denominator + aligned_m
        if numerator is not None and denominator is not None:
            denom_safe = denominator.copy()
            denom_safe[denom_safe == 0] = np.nan
            return numerator / denom_safe
        return None

    # ================================================================
    # HYDRAULIK-PARAMETERTABELLE
    # ================================================================
    def _plot_pipe_hydraulics_table(self):
        """Wissenschaftliche farbkodierte Parametertabelle aller Rohrsegmente."""
        print("   Hydraulik-Tabelle...")
        rows = []
        for p in self.pipe_names:
            row = {'Segment': p}
            m_vl = self._get_mdot(p, 'supply')
            m_rl = self._get_mdot(p, 'return')
            row['ṁ_VL_mean\n[kg/s]'] = (f"{m_vl.mean():.4f}"
                                          if m_vl is not None else '—')
            row['ṁ_VL_max\n[kg/s]'] = (f"{m_vl.max():.4f}"
                                         if m_vl is not None else '—')
            row['ṁ_RL_mean\n[kg/s]'] = (f"{m_rl.mean():.4f}"
                                          if m_rl is not None else '—')
            vc = f"{p}_velocity"
            if vc in self.df_pipes.columns:
                v = self.df_pipes[vc]
                row['v_mean\n[m/s]'] = f"{v.mean():.4f}"
                row['v_max\n[m/s]'] = f"{v.max():.4f}"
                row['v<0.3\n[%]'] = f"{(v < 0.3).mean()*100:.1f}"
            else:
                row['v_mean\n[m/s]'] = row['v_max\n[m/s]'] = row['v<0.3\n[%]'] = '—'
            cs = f"{p}_delta_p_supply"; cr = f"{p}_delta_p_return"
            row['Δp_VL\n[mbar]'] = (f"{self.df_pipes[cs].mean()*1000:.3f}"
                                      if cs in self.df_pipes.columns else '—')
            row['Δp_RL\n[mbar]'] = (f"{self.df_pipes[cr].mean()*1000:.3f}"
                                      if cr in self.df_pipes.columns else '—')
            ci_s = f"{p}_T_supply_in"; co_s = f"{p}_T_supply_out"
            row['ΔT_VL\n[K]'] = (
                f"{(self.df_pipes[ci_s] - self.df_pipes[co_s]).mean():.4f}"
                if ci_s in self.df_pipes.columns and co_s in self.df_pipes.columns
                else '—')
            ci_r = f"{p}_T_return_in"; co_r = f"{p}_T_return_out"
            row['ΔT_RL\n[K]'] = (
                f"{(self.df_pipes[ci_r] - self.df_pipes[co_r]).mean():.4f}"
                if ci_r in self.df_pipes.columns and co_r in self.df_pipes.columns
                else '—')
            ql = 0
            if f"{p}_Q_loss_supply" in self.df_pipes.columns:
                ql += self.df_pipes[f"{p}_Q_loss_supply"].sum()
            if f"{p}_Q_loss_return" in self.df_pipes.columns:
                ql += self.df_pipes[f"{p}_Q_loss_return"].sum()
            row['Q_loss\n[MWh]'] = f"{ql:.4f}"
            rows.append(row)

        df_t = pd.DataFrame(rows)
        cols = list(df_t.columns)
        n = len(df_t)
        fig_h = max(12, n * 0.54 + 5)
        fig = plt.figure(figsize=(26, fig_h))
        add_fancy_title(
            fig,
            "HYDRAULIK-PARAMETERTABELLE — ALLE ROHRSEGMENTE",
            f"Mittlere Betriebspunkte | {self.config['scenario']['period']} "
            f"| {n} Segmente | VL (rot) · RL (blau)")

        ax = fig.add_axes([0.01, 0.04, 0.98, 0.84])
        ax.axis('off')

        vb_col = (cols.index('v<0.3\n[%]')
                  if 'v<0.3\n[%]' in cols else None)
        cell_colors = []
        for ri, (_, r) in enumerate(df_t.iterrows()):
            base = '#FAFAFA' if ri % 2 == 0 else 'white'
            rc = [base] * len(cols)
            if vb_col is not None:
                val = r['v<0.3\n[%]']
                if val != '—':
                    pct = float(val)
                    rc[vb_col] = ('#FEE2E2' if pct > 50
                                  else '#FEF3C7' if pct > 10
                                  else '#D1FAE5')
            cell_colors.append(rc)

        tbl = ax.table(cellText=df_t.values, colLabels=cols,
                       cellLoc='center', loc='center',
                       cellColours=cell_colors)
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8.5)
        tbl.scale(1, 1.9)

        for j, c in enumerate(cols):
            cell = tbl[0, j]
            if 'VL' in c or '_VL' in c:
                cell.set_facecolor('#991B1B')
            elif 'RL' in c or '_RL' in c:
                cell.set_facecolor('#1D4ED8')
            elif c == 'Segment':
                cell.set_facecolor(COLORS['dark'])
            else:
                cell.set_facecolor('#374151')
            cell.set_text_props(color='white', fontweight='bold', fontsize=8.5)

        fig.text(
            0.01, 0.018,
            "Farblegende v<0.3 m/s:  ■ grün = <10 %   ■ gelb = 10–50 %   "
            "■ rot = >50 % der Betriebsstunden  |  "
            "Δp = mittlerer stündlicher Druckverlust [mbar]  |  "
            "ΔT = mittlere Temperaturabsenkung je Segment [K]  |  "
            "Q_loss = integrierter Wärmeverlust [MWh]",
            fontsize=8.5, color='#6B7280', style='italic')

        self._save_plot(fig, "pipe_hydraulics_table.png")

    # ================================================================
    # NETZ-KPI-ZUSAMMENFASSUNG
    # ================================================================
    def _compute_network_kpis(self):
        kpi = {'n_pipes': len(self.pipe_names), 'n_nodes': len(self.node_names)}

        tq = None
        for n in self.node_names:
            c = f"{n}_Q_demand"
            if c in self.df_nodes.columns:
                tq = self.df_nodes[c] if tq is None else tq + self.df_nodes[c]
        kpi['Q_demand_total'] = tq.sum() if tq is not None else 0
        kpi['tq_series'] = tq

        ql_vl = sum(self.df_pipes[f"{p}_Q_loss_supply"].sum()
                    for p in self.pipe_names
                    if f"{p}_Q_loss_supply" in self.df_pipes.columns)
        ql_rl = sum(self.df_pipes[f"{p}_Q_loss_return"].sum()
                    for p in self.pipe_names
                    if f"{p}_Q_loss_return" in self.df_pipes.columns)
        kpi['Q_loss_vl'] = ql_vl
        kpi['Q_loss_rl'] = ql_rl
        kpi['Q_loss_total'] = ql_vl + ql_rl
        kpi['Q_input'] = kpi['Q_demand_total'] + kpi['Q_loss_total']
        kpi['eta'] = (kpi['Q_demand_total'] / kpi['Q_input'] * 100
                      if kpi['Q_input'] > 0 else 0)
        kpi['q_loss_spec'] = (kpi['Q_loss_total'] / len(self.df_pipes)
                              if len(self.df_pipes) > 0 else 0)

        prod = [n for n, t in self.node_types.items() if t == 'producer']
        T_VL_vals, T_RL_vals = [], []
        for n in prod:
            if f"{n}_T_supply" in self.df_nodes.columns:
                T_VL_vals.extend(self.df_nodes[f"{n}_T_supply"].values)
            if f"{n}_T_return" in self.df_nodes.columns:
                T_RL_vals.extend(self.df_nodes[f"{n}_T_return"].values)
        kpi['T_VL_mean'] = float(np.mean(T_VL_vals)) if T_VL_vals else 0.0
        kpi['T_RL_mean'] = float(np.mean(T_RL_vals)) if T_RL_vals else 0.0
        kpi['dT_spread_mean'] = kpi['T_VL_mean'] - kpi['T_RL_mean']
        if T_VL_vals:
            kpi['T_VL_series'] = np.array(T_VL_vals)
        if T_RL_vals:
            kpi['T_RL_series'] = np.array(T_RL_vals)

        vm = [self.df_pipes[f"{p}_velocity"].max()
              for p in self.pipe_names
              if f"{p}_velocity" in self.df_pipes.columns]
        va = [self.df_pipes[f"{p}_velocity"].mean()
              for p in self.pipe_names
              if f"{p}_velocity" in self.df_pipes.columns]
        kpi['v_max'] = float(max(vm)) if vm else 0.0
        kpi['v_mean'] = float(np.mean(va)) if va else 0.0
        n_below = sum((self.df_pipes[f"{p}_velocity"] < 0.3).sum()
                      for p in self.pipe_names
                      if f"{p}_velocity" in self.df_pipes.columns)
        n_total = len(self.df_pipes) * max(len(vm), 1)
        kpi['v_below_pct'] = n_below / n_total * 100 if n_total > 0 else 0

        dp_means = [(p, self.df_pipes[f"{p}_delta_p_supply"].mean() * 1000)
                    for p in self.pipe_names
                    if f"{p}_delta_p_supply" in self.df_pipes.columns]
        dp_means.sort(key=lambda x: x[1], reverse=True)
        kpi['top_dp_pipes'] = dp_means[:3]

        dT_means = [
            (p, (self.df_pipes[f"{p}_T_supply_in"]
                 - self.df_pipes[f"{p}_T_supply_out"]).mean())
            for p in self.pipe_names
            if (f"{p}_T_supply_in" in self.df_pipes.columns
                and f"{p}_T_supply_out" in self.df_pipes.columns)]
        dT_means.sort(key=lambda x: x[1], reverse=True)
        kpi['top_dT_pipes'] = dT_means[:3]

        return kpi

    def _build_scientific_summary(self, kpi):
        lim = self.config['limits']
        sc = self.config['scenario']
        warns = []
        if kpi['eta'] < 95:
            warns.append(
                f"[!] η_Netz = {kpi['eta']:.2f}% < 95 % — Dämmmaßnahmen prüfen")
        if kpi['v_below_pct'] > 20:
            warns.append(
                f"[!] {kpi['v_below_pct']:.1f}% aller Betriebspunkte "
                f"unter v_min = {lim['velocity_min_m_s']} m/s — "
                "Rohrdurchmesser reduzieren")
        if kpi['dT_spread_mean'] < lim['delta_T_c'] * 0.8:
            warns.append(
                f"[!] Mittl. Spreizung {kpi['dT_spread_mean']:.1f} K < "
                f"{lim['delta_T_c']*0.8:.0f} K — Rücklauftemperatur erhöhen")
        for p, dp in kpi.get('top_dp_pipes', [])[:1]:
            warns.append(
                f"[!] Max. Druckverlust: {p} (Ø {dp:.2f} mbar)")
        for p, dT in kpi.get('top_dT_pipes', [])[:1]:
            if dT > 0.5:
                warns.append(
                    f"[!] Max. ΔT_VL: {p} (Ø {dT:.3f} K)")
        if not warns:
            warns = ["[OK] Keine kritischen Betriebsparameter identifiziert"]
        n_prod = sum(1 for t in self.node_types.values() if t == 'producer')
        n_junc = sum(1 for t in self.node_types.values() if t == 'junction')
        n_cons = sum(1 for t in self.node_types.values() if t == 'consumer')
        sep = "─" * 115
        return (
            f"WISSENSCHAFTLICHE NETZ-ZUSAMMENFASSUNG  —  {sc['name']}  |  "
            f"{sc['period']}\n{sep}\n"
            f"  ENERGIEBILANZ :  Einspeisung: {kpi['Q_input']:.1f} MWh  │  "
            f"Nützliche Wärme: {kpi['Q_demand_total']:.1f} MWh  │  "
            f"Verluste: {kpi['Q_loss_total']:.2f} MWh  "
            f"(VL: {kpi['Q_loss_vl']:.2f} / RL: {kpi['Q_loss_rl']:.2f})  │  "
            f"η_Netz = {kpi['eta']:.3f}%\n"
            f"  HYDRAULIK     :  v_max: {kpi['v_max']:.4f} m/s  │  "
            f"v_mean: {kpi['v_mean']:.4f} m/s  │  "
            f"v < {lim['velocity_min_m_s']} m/s: {kpi['v_below_pct']:.2f}% "
            f"d. Betr.punkte\n"
            f"  TEMPERATUREN  :  T̄_VL: {kpi['T_VL_mean']:.2f} °C  │  "
            f"T̄_RL: {kpi['T_RL_mean']:.2f} °C  │  "
            f"Spreizung Ø: {kpi['dT_spread_mean']:.2f} K  │  "
            f"Soll: {lim['delta_T_c']} K\n"
            f"  TOPOLOGIE     :  {kpi['n_pipes']} Rohrsegmente  │  "
            f"{kpi['n_nodes']} Knoten  (Erzeug.: {n_prod}  │  "
            f"Junctions: {n_junc}  │  Verbraucher: {n_cons})\n{sep}\n"
            "  BEFUNDE       :  " + ("\n" + " " * 18).join(warns))

    def _plot_network_kpi_summary(self):
        """Umfassende wissenschaftliche Netzzusammenfassung mit Dauerlinie, KPIs etc."""
        print("   Netz-KPI-Zusammenfassung...")
        kpi = self._compute_network_kpis()

        sc = self.config['scenario']
        fig = plt.figure(figsize=(26, 32))
        fig.text(0.5, 0.992, "WISSENSCHAFTLICHE NETZZUSAMMENFASSUNG",
                 ha='center', fontsize=24, fontweight='bold', color=COLORS['dark'])
        fig.text(0.5, 0.977,
                 f"{sc['name']}  ·  {sc['period']}  ·  "
                 f"{kpi['n_pipes']} Rohrsegmente / {kpi['n_nodes']} Knoten",
                 ha='center', fontsize=13, color='#6B7280', style='italic')

        gs = fig.add_gridspec(7, 4, hspace=0.42, wspace=0.32,
                              top=0.970, bottom=0.028, left=0.06, right=0.97)

        # ── Row 0: KPI-Cards ─────────────────────────────────────────
        lim = self.config['limits']
        cards = [
            ("Netzwirkungsgrad η",
             f"{kpi['eta']:.3f} %",
             COLORS['success'] if kpi['eta'] > 95 else COLORS['warning'],
             "η = Q_Verbraucher / Q_Einspeisung"),
            ("Spez. Wärmeverlust",
             f"{kpi['q_loss_spec']:.4f} MWh/h",
             COLORS['info'],
             "Q_loss_total / n_Zeitschritte"),
            ("Mittl. VL-Temperatur",
             f"{kpi['T_VL_mean']:.2f} °C",
             COLORS['vorlauf'],
             "T̄_VL (Erzeugerknoten)"),
            ("Mittl. Netz-Spreizung",
             f"{kpi['dT_spread_mean']:.2f} K",
             (COLORS['success']
              if kpi['dT_spread_mean'] >= lim['delta_T_c'] * 0.9
              else COLORS['warning']),
             f"T̄_VL − T̄_RL  (Soll: {lim['delta_T_c']} K)"),
        ]
        for col, (title, val, color, formula) in enumerate(cards):
            ax = fig.add_subplot(gs[0, col]); ax.axis('off')
            ax.set_facecolor('white')
            bbox = FancyBboxPatch((0.04, 0.06), 0.92, 0.88,
                                   boxstyle="round,pad=0.05",
                                   facecolor=color + '18', edgecolor=color,
                                   lw=2.5, transform=ax.transAxes)
            ax.add_patch(bbox)
            ax.text(0.5, 0.87, title, ha='center', va='top', fontsize=10,
                    fontweight='bold', color=COLORS['dark'],
                    transform=ax.transAxes)
            ax.text(0.5, 0.52, val, ha='center', va='center', fontsize=21,
                    fontweight='bold', color=color, transform=ax.transAxes,
                    family='monospace')
            ax.text(0.5, 0.16, formula, ha='center', va='bottom', fontsize=8,
                    color='#6B7280', style='italic', transform=ax.transAxes)

        # ── Row 1: Energiebilanz-Balken + ṁ-Häufigkeitsverteilung ────
        ax = fig.add_subplot(gs[1, :2]); cb(ax)
        cats = ['Einspeisung', 'Nützliche\nWärme', 'VL-Verluste', 'RL-Verluste']
        vals = [kpi['Q_input'], kpi['Q_demand_total'],
                kpi['Q_loss_vl'], kpi['Q_loss_rl']]
        cols_ = [COLORS['warning'], COLORS['success'],
                 COLORS['vorlauf'], COLORS['ruecklauf']]
        bars = ax.bar(cats, vals, color=cols_, alpha=0.85, edgecolor='white',
                      lw=2, width=0.55)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2,
                    b.get_height() + max(vals) * 0.025,
                    f'{v:.1f}\nMWh', ha='center', va='bottom',
                    fontsize=9, fontweight='bold')
        style_axis(ax, "Jährliche Energiebilanz", "", "MWh")

        ax = fig.add_subplot(gs[1, 2:]); cb(ax)
        all_vl, all_rl = [], []
        for p in self.pipe_names:
            m = self._get_mdot(p, 'supply')
            if m is not None:
                all_vl.extend(m.values)
            m = self._get_mdot(p, 'return')
            if m is not None:
                all_rl.extend(m.values)
        if all_vl:
            ax.hist(all_vl, bins=70, color=COLORS['vorlauf'], alpha=0.65,
                    edgecolor='white', lw=0.3, label='VL')
        if all_rl:
            ax.hist(all_rl, bins=70, color=COLORS['ruecklauf'], alpha=0.50,
                    edgecolor='white', lw=0.3, label='RL')
        ml(ax)
        style_axis(ax, "Massenstrom-Häufigkeitsverteilung (alle Rohre)",
                   "ṁ [kg/s]", "Häufigkeit")

        # ── Row 2: T-Boxplots + Druckverlust-Ranking ─────────────────
        ax = fig.add_subplot(gs[2, :2]); cb(ax)
        prod = [n for n, t in self.node_types.items() if t == 'producer']
        junc = [n for n, t in self.node_types.items() if t == 'junction']
        cons = [n for n, t in self.node_types.items() if t == 'consumer']
        data_bp, labels_bp, colors_bp_list = [], [], []
        for group, label, c in [
            (prod, 'Erzeuger', COLORS['warning']),
            (junc, 'Junctions', COLORS['info']),
            (cons, 'Verbraucher', COLORS['success']),
        ]:
            temps = [v for n in group
                     for v in (self.df_nodes[f"{n}_T_supply"].values
                                if f"{n}_T_supply" in self.df_nodes.columns
                                else [])]
            if temps:
                data_bp.append(temps); labels_bp.append(label)
                colors_bp_list.append(c)
        if data_bp:
            bp = ax.boxplot(data_bp, tick_labels=labels_bp, patch_artist=True,
                            medianprops=dict(color='black', lw=2.5),
                            whiskerprops=dict(lw=1.5),
                            capprops=dict(lw=1.5))
            for patch, c in zip(bp['boxes'], colors_bp_list):
                patch.set_facecolor(c); patch.set_alpha(0.7)
        ax.axhline(y=lim['temp_supply_c'], color=COLORS['vorlauf'],
                   ls='--', lw=1.5, alpha=0.7,
                   label=f"Soll VL {lim['temp_supply_c']} °C")
        ax.axhline(y=lim['temp_return_c'], color=COLORS['ruecklauf'],
                   ls='--', lw=1.5, alpha=0.7,
                   label=f"Soll RL {lim['temp_return_c']} °C")
        ml(ax)
        style_axis(ax, "VL-Temperaturverteilung nach Knotentyp", "", "°C")

        ax = fig.add_subplot(gs[2, 2:]); cb(ax)
        dp_vl, dp_rl, pipe_lbls = [], [], []
        for p in self.pipe_names:
            cs_dp = f"{p}_delta_p_supply"; cr_dp = f"{p}_delta_p_return"
            if cs_dp in self.df_pipes.columns:
                dp_vl.append(self.df_pipes[cs_dp].mean() * 1000)
                dp_rl.append(self.df_pipes[cr_dp].mean() * 1000
                              if cr_dp in self.df_pipes.columns else 0)
                pipe_lbls.append(p)
        if pipe_lbls:
            dp_s = sorted(zip(dp_vl, dp_rl, pipe_lbls), reverse=True)
            dvl_, drl_, plbl = zip(*dp_s[:16])
            x = np.arange(len(plbl)); w = 0.38
            ax.bar(x - w / 2, dvl_, w, color=COLORS['vorlauf'], alpha=0.82,
                   label='VL Ø')
            ax.bar(x + w / 2, drl_, w, color=COLORS['ruecklauf'], alpha=0.82,
                   label='RL Ø')
            ax.set_xticks(x)
            ax.set_xticklabels(plbl, rotation=50, ha='right', fontsize=7)
            ml(ax)
        style_axis(ax, "Mittlerer Druckverlust je Segment (Top 16)", "", "mbar")

        # ── Row 3: Jahresdauerlinien Wärmebedarf + Temperatur ────────
        ax = fig.add_subplot(gs[3, :2]); cb(ax)
        tq_s = kpi.get('tq_series')
        if tq_s is not None:
            sorted_q = np.sort(tq_s.values)[::-1]
            h = np.arange(len(sorted_q))
            ax.fill_between(h, sorted_q, alpha=0.35, color=COLORS['success'])
            ax.plot(h, sorted_q, color=COLORS['success'], lw=2.5)
            q_max = sorted_q[0]
            q_mean = sorted_q.mean()
            ax.axhline(y=q_mean, color=COLORS['dark'], ls='--', lw=1.5,
                       label=f'Ø = {q_mean:.3f} MW')
            flh = tq_s.sum() / q_max if q_max > 0 else 0
            stat_box(ax,
                     f"Q_max  : {q_max:.4f} MW\n"
                     f"Q_mean : {q_mean:.4f} MW\n"
                     f"Q_sum  : {tq_s.sum():.1f} MWh\n"
                     f"VLStd  : {flh:.0f} h",
                     color=COLORS['success'])
            ml(ax)
        style_axis(ax,
                   "Jahresdauerlinie — Gesamtwärmebedarf",
                   "Betriebsstunden [h]", "Q [MW]")

        ax = fig.add_subplot(gs[3, 2:]); cb(ax)
        T_VL_s = kpi.get('T_VL_series')
        T_RL_s = kpi.get('T_RL_series')
        if T_VL_s is not None:
            sv = np.sort(T_VL_s)[::-1]
            ax.fill_between(np.arange(len(sv)), sv, alpha=0.35,
                            color=COLORS['vorlauf'])
            ax.plot(sv, color=COLORS['vorlauf'], lw=2.5, label='VL')
        if T_RL_s is not None:
            sr = np.sort(T_RL_s)[::-1]
            ax.fill_between(np.arange(len(sr)), sr, alpha=0.35,
                            color=COLORS['ruecklauf'])
            ax.plot(sr, color=COLORS['ruecklauf'], lw=2.5,
                    ls='--', label='RL')
        ml(ax)
        style_axis(ax, "Temperatur-Dauerlinie (Erzeugerknoten)",
                   "Betriebsstunden [h]", "T [°C]")

        # ── Row 4: ΔT-Profil Rohre + Spreizung vs. Jahresenergie ─────
        ax = fig.add_subplot(gs[4, :2]); cb(ax)
        td2 = []
        for p in self.pipe_names:
            ci_s2 = f"{p}_T_supply_in"; co_s2 = f"{p}_T_supply_out"
            ci_r2 = f"{p}_T_return_in"; co_r2 = f"{p}_T_return_out"
            if ci_s2 in self.df_pipes.columns and co_s2 in self.df_pipes.columns:
                dT_vl = (self.df_pipes[ci_s2] - self.df_pipes[co_s2]).mean()
                dT_rl = ((self.df_pipes[ci_r2] - self.df_pipes[co_r2]).mean()
                          if ci_r2 in self.df_pipes.columns
                          and co_r2 in self.df_pipes.columns else 0)
                td2.append((p, dT_vl, dT_rl))
        if td2:
            td2.sort(key=lambda x: x[1], reverse=True)
            pp2, dvl2, drl2 = zip(*td2[:20])
            x2 = np.arange(len(pp2)); w2 = 0.38
            cm_ = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(pp2)))
            ax.bar(x2 - w2 / 2, dvl2, w2, color=COLORS['vorlauf'], alpha=0.82,
                   label='ΔT_VL')
            ax.bar(x2 + w2 / 2, drl2, w2, color=COLORS['ruecklauf'], alpha=0.82,
                   label='ΔT_RL')
            ax.set_xticks(x2)
            ax.set_xticklabels(pp2, rotation=50, ha='right', fontsize=7)
            ml(ax)
        style_axis(ax, "Mittlere Temperaturabsenkung je Segment", "", "ΔT [K]")

        ax = fig.add_subplot(gs[4, 2:]); cb(ax)
        c_data = [
            (n, self.df_nodes[f"{n}_Q_demand"].sum(),
             (self.df_nodes[f"{n}_T_supply"].mean()
              if f"{n}_T_supply" in self.df_nodes.columns else np.nan),
             (self.df_nodes[f"{n}_T_return"].mean()
              if f"{n}_T_return" in self.df_nodes.columns else np.nan))
            for n in cons if f"{n}_Q_demand" in self.df_nodes.columns]
        if c_data:
            cq2_ = [d[1] for d in c_data]
            cdT2 = [d[2] - d[3] for d in c_data]
            cn2_ = [d[0] for d in c_data]
            ax.scatter(cdT2, cq2_, c=range(len(cn2_)), cmap='plasma',
                       s=90, alpha=0.88, edgecolors='white', lw=1, zorder=5)
            for i, n in enumerate(cn2_):
                ax.annotate(n, (cdT2[i], cq2_[i]), fontsize=7,
                            xytext=(5, 4), textcoords='offset points',
                            alpha=0.9)
            ax.axvline(x=lim['delta_T_c'], color=COLORS['success'],
                       ls='--', lw=1.5,
                       label=f"Soll ΔT = {lim['delta_T_c']} K")
            ml(ax)
        style_axis(ax, "Spreizung vs. Jahresenergiebedarf (Verbraucher)",
                   "ΔT = T_VL − T_RL [K]", "Q [MWh]")

        # ── Row 5: Waermebedarf Verbraucher-Ranking ───────────────────
        ax = fig.add_subplot(gs[5, :2]); cb(ax)
        c_sorted = sorted(
            [(n, self.df_nodes[f"{n}_Q_demand"].sum())
             for n in cons if f"{n}_Q_demand" in self.df_nodes.columns],
            key=lambda x: x[1], reverse=True)[:16]
        if c_sorted:
            cn3, cq3 = zip(*c_sorted)
            y3 = np.arange(len(cn3))
            cmap3 = plt.cm.YlOrRd(np.linspace(0.3, 0.9, len(cn3)))
            bars3 = ax.barh(y3, cq3, color=cmap3, alpha=0.85,
                            edgecolor='white', lw=0.5)
            ax.set_yticks(y3); ax.set_yticklabels(cn3, fontsize=8)
            ax.invert_yaxis()
            for b, v in zip(bars3, cq3):
                ax.text(v + max(cq3) * 0.01, b.get_y() + b.get_height() / 2,
                        f'{v:.1f}', va='center', fontsize=7.5, fontweight='bold')
        style_axis(ax, "Wärmebedarf je Verbraucher (Top 16)", "MWh", "")

        ax = fig.add_subplot(gs[5, 2:]); cb(ax)
        # Velocity box plots per pipe (top 12 by max velocity)
        vdata = [(p, self.df_pipes[f"{p}_velocity"].values)
                 for p in self.pipe_names
                 if f"{p}_velocity" in self.df_pipes.columns]
        vdata.sort(key=lambda x: x[1].max(), reverse=True)
        vdata = vdata[:12]
        if vdata:
            vp_names, vp_vals = zip(*vdata)
            bp2 = ax.boxplot(vp_vals, tick_labels=vp_names, patch_artist=True,
                             medianprops=dict(color='black', lw=2),
                             whiskerprops=dict(lw=1.2),
                             capprops=dict(lw=1.2))
            vm_c = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(vp_vals)))
            for patch, c in zip(bp2['boxes'], vm_c):
                patch.set_facecolor(c); patch.set_alpha(0.75)
            ax.axhline(y=lim['velocity_min_m_s'], color=COLORS['danger'],
                       ls='--', lw=2, label=f"v_min = {lim['velocity_min_m_s']} m/s")
            ax.axhline(y=lim['velocity_max_m_s'], color=COLORS['warning'],
                       ls='--', lw=2, label=f"v_max = {lim['velocity_max_m_s']} m/s")
            ax.set_xticklabels(vp_names, rotation=50, ha='right', fontsize=7)
            ml(ax)
        style_axis(ax, "Geschwindigkeits-Boxplots (Top 12 Rohre)", "", "v [m/s]")

        # ── Row 6: Wissenschaftlicher Textbefund ─────────────────────
        ax = fig.add_subplot(gs[6, :]); ax.axis('off')
        summary_text = self._build_scientific_summary(kpi)
        ax.text(0.005, 0.97, summary_text, transform=ax.transAxes,
                fontsize=9.5, va='top', family='monospace',
                bbox=dict(boxstyle='round,pad=0.65', facecolor='#F0F9FF',
                          edgecolor=COLORS['primary'], alpha=0.97, lw=2))

        self._save_plot(fig, "network_kpi_summary.png")

    # ================================================================
    # EXPORT & SUMMARY  ── VL/RL SPLIT in Statistiken ──
    # ================================================================
    def _export_results(self):
        print("\n[4] EXPORT")
        ps = []
        for p in self.pipe_names:
            s = {"pipe": p}
            # VL Massenstrom
            m_vl = self._get_mdot(p, 'supply')
            if m_vl is not None:
                s["m_dot_vl_max"] = m_vl.max()
                s["m_dot_vl_mean"] = m_vl.mean()
            # RL Massenstrom
            m_rl = self._get_mdot(p, 'return')
            if m_rl is not None:
                s["m_dot_rl_max"] = m_rl.max()
                s["m_dot_rl_mean"] = m_rl.mean()
            c = f"{p}_velocity"
            if c in self.df_pipes.columns:
                s["v_max"] = self.df_pipes[c].max()
                s["v_mean"] = self.df_pipes[c].mean()
                s["v_below_pct"] = ((self.df_pipes[c] < 0.3).sum()
                                    / len(self.df_pipes) * 100)
            cs_c, cr_c = f"{p}_Q_loss_supply", f"{p}_Q_loss_return"
            if cs_c in self.df_pipes.columns:
                s["Q_loss_vl_MWh"] = self.df_pipes[cs_c].sum()
            if cr_c in self.df_pipes.columns:
                s["Q_loss_rl_MWh"] = self.df_pipes[cr_c].sum()
            s["Q_loss_total_MWh"] = s.get("Q_loss_vl_MWh", 0) + s.get(
                "Q_loss_rl_MWh", 0)
            c = f"{p}_Q_consumer"
            if c in self.df_pipes.columns:
                s["Q_consumer_MWh"] = self.df_pipes[c].sum()
            ps.append(s)
        pd.DataFrame(ps).to_csv(
            self.output_path / "pipe_statistics.csv", index=False)
        print("   pipe_statistics.csv")

        ns = []
        for n in self.node_names:
            s = {"node": n, "type": self.node_types.get(n, "unknown")}
            c = f"{n}_Q_demand"
            if c in self.df_nodes.columns:
                s["Q_demand_MWh"] = self.df_nodes[c].sum()
                s["Q_demand_max_MW"] = self.df_nodes[c].max()
            ns.append(s)
        pd.DataFrame(ns).to_csv(
            self.output_path / "node_statistics.csv", index=False)
        print("   node_statistics.csv")

    def _print_summary(self):
        print("\n" + "=" * 70)
        print("  ANALYSE ABGESCHLOSSEN (v4.0 – Wissenschaftliche Netzanalyse)")
        print("=" * 70)
        print(f"\n  Plots: {self.output_path}\n")
        for f in sorted(self.output_path.glob("*.png")):
            print(f"    {f.name}")
        for f in sorted(self.output_path.glob("*.csv")):
            print(f"    {f.name}")
        print()


# ==============================================================================
# HAUPTPROGRAMM
# ==============================================================================
if __name__ == "__main__":
    analyzer = NetworkAnalyzer(CONFIG)
    analyzer.run()