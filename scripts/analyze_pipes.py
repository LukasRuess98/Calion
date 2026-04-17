"""
================================================================================
NETZWERK-ANALYSE-SKRIPT v2.1
================================================================================
Korrigiert für tatsächliche Spaltenstruktur:
- Nodes: T_supply, T_return, Q_demand (keine Druckdaten)
- Pipes: m_dot, velocity, delta_p_*, T_*, Q_loss_*, Q_consumer

================================================================================
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
from datetime import datetime

# ==============================================================================
# KONFIGURATION - Angepasst für Memmingen L3 Independent Zone Demands
# ==============================================================================

CONFIG = {
    "paths": {
        "results_dir": "../output/results/thermal_network",
        "output_dir": "../output/results/plots",
        "pipes_file": "pipes/pipes_timeseries.csv",
        "nodes_file": "nodes/nodes_timeseries.csv",
    },
    "data_format": {
        "csv_separator": ";",
    },
    "selection": {
        "max_items_overview": 15,
        
        # Detail-Pipes: Hauptstrang + verschiedene Zweige
        "detail_pipes": [
            "E1_to_V1",
            "E1_to_V2",
            "j1_to_j2",
            "j1_to_j5",
            "j2_to_j3",
            "j3_to_j4",
            "j5_to_V17",
            "V17_to_V18",
            "V18_to_j6",
            "j6_to_j7",
            "j7_to_V27",
        ],
        
        # Detail-Nodes: Erzeuger + Junctions + verschiedene Verbraucher
        "detail_nodes": [
            "E_1",
            "j_1",
            "j_5",
            "j_7",
            "V_1",
            "V_2",
            "V_14",
            "V_17",
            "V_18",
            "V_27",
        ],
    },
    "limits": {
        "velocity_min_m_s": 0.3,
        "velocity_max_m_s": 2.5,
        "pressure_min_bar": 0.5,
        "temp_supply_c": 100,
        "temp_return_c": 40,
        "delta_T_c": 60,
        "cp_kJ_kgK": 4.18,
    },
    "plots": {
        "pipe_bundle_overview": True,
        "pipe_bundle_detail": True,
        "node_overview": True,
        "node_detail": True,
        "system_flow": True,
        "dashboard": True,
        "pipe_with_nodes": True,
        "mass_flow_overview": True,
    },
    "plot_settings": {
        "figsize_overview": (16, 12),
        "figsize_detail": (16, 14),
        "figsize_dashboard": (20, 16),
        "dpi": 150,
        "show_plots": False,
    },
    "scenario": {
        "name": "Memmingen L3 - Independent Zone Demands",
        "description": "27-node network with independent per-zone demand profiles",
        "period": "Januar 2025",
    },
}

# ==============================================================================
# HAUPTKLASSE
# ==============================================================================

class NetworkAnalyzer:
    
    def __init__(self, config: dict):
        self.config = config
        self.df_pipes = None
        self.df_nodes = None
        self.pipe_names = []
        self.node_names = []
        self.node_types = {}
        self.output_path = None
        self.network_topology = {}
        
    def run(self):
        self._print_header()
        self._setup_paths()
        self._load_data()
        self._extract_topology()
        self._create_all_plots()
        self._export_results()
        self._print_summary()
        
    def _print_header(self):
        print("=" * 70)
        print("NETZWERK-ANALYSE v2.1")
        print(f"Szenario: {self.config['scenario']['name']}")
        print(f"Zeitraum: {self.config['scenario']['period']}")
        print("=" * 70)
        
    def _setup_paths(self):
        base = Path(__file__).parent
        self.results_dir = base / self.config["paths"]["results_dir"]
        self.output_path = base / self.config["paths"]["output_dir"]
        self.output_path.mkdir(parents=True, exist_ok=True)
        
    def _load_data(self):
        print("\n[1] DATEN LADEN")
        sep = self.config["data_format"]["csv_separator"]
        
        pipes_file = self.results_dir / self.config["paths"]["pipes_file"]
        if pipes_file.exists():
            self.df_pipes = pd.read_csv(pipes_file, sep=sep, index_col=0)
            print(f"  ✓ Pipes: {self.df_pipes.shape[0]} Zeitschritte, {self.df_pipes.shape[1]} Spalten")
        
        nodes_file = self.results_dir / self.config["paths"]["nodes_file"]
        if nodes_file.exists():
            self.df_nodes = pd.read_csv(nodes_file, sep=sep, index_col=0)
            if self.df_nodes.shape[1] == 0:
                self.df_nodes = pd.read_csv(nodes_file, sep=",", index_col=0)
            print(f"  ✓ Nodes: {self.df_nodes.shape[0]} Zeitschritte, {self.df_nodes.shape[1]} Spalten")
            print(f"  → Node-Spalten (erste 10): {list(self.df_nodes.columns[:10])}")
                
    def _extract_topology(self):
        print("\n[2] TOPOLOGIE EXTRAHIEREN")
        
        if self.df_pipes is not None:
            for col in self.df_pipes.columns:
                if col.endswith("_m_dot"):
                    pipe = col.replace("_m_dot", "")
                    self.pipe_names.append(pipe)
                    if "_to_" in pipe:
                        parts = pipe.split("_to_")
                        if len(parts) == 2:
                            from_node = parts[0]
                            to_node = parts[1]
                            if from_node and from_node[0].isalpha() and len(from_node) > 1 and from_node[1].isdigit():
                                from_node = from_node[0] + "_" + from_node[1:]
                            if to_node and to_node[0].isalpha() and len(to_node) > 1 and to_node[1].isdigit():
                                to_node = to_node[0] + "_" + to_node[1:]
                            self.network_topology[pipe] = {"from": from_node, "to": to_node}
        print(f"  ✓ {len(self.pipe_names)} Rohrbündel erkannt")
        
        if self.df_nodes is not None:
            seen_nodes = set()
            for col in self.df_nodes.columns:
                if "_T_supply" in col:
                    node = col.replace("_T_supply", "")
                    if node not in seen_nodes:
                        seen_nodes.add(node)
                        self.node_names.append(node)
                        if node.startswith("E_"):
                            self.node_types[node] = "producer"
                        elif node.startswith("j_"):
                            self.node_types[node] = "junction"
                        elif node.startswith("V_"):
                            self.node_types[node] = "consumer"
                        else:
                            self.node_types[node] = "unknown"
                            
        print(f"  ✓ {len(self.node_names)} Knoten erkannt")
        print(f"    - Erzeuger: {sum(1 for t in self.node_types.values() if t=='producer')}")
        print(f"    - Junctions: {sum(1 for t in self.node_types.values() if t=='junction')}")
        print(f"    - Verbraucher: {sum(1 for t in self.node_types.values() if t=='consumer')}")
        
    def _create_all_plots(self):
        print("\n[3] PLOTS ERSTELLEN")
        plots = self.config["plots"]
        
        if plots.get("pipe_bundle_overview", False):
            self._plot_pipe_bundle_overview()
        if plots.get("pipe_bundle_detail", False):
            self._plot_pipe_bundle_details()
        if plots.get("node_overview", False):
            self._plot_node_overview()
        if plots.get("node_detail", False):
            self._plot_node_details()
        if plots.get("system_flow", False):
            self._plot_system_flow()
        if plots.get("pipe_with_nodes", False):
            self._plot_pipe_with_nodes()
        if plots.get("mass_flow_overview", False):
            self._plot_mass_flow_overview()
        if plots.get("dashboard", False):
            self._plot_dashboard()

    # ==========================================================================
    # PIPE PLOTS
    # ==========================================================================
    
    def _plot_pipe_bundle_overview(self):
        print("\n  [3.1] Rohrbündel-Übersicht (VL/RL)...")
        
        max_pipes = self.config["selection"]["max_items_overview"]
        
        pipe_max_flow = []
        for pipe in self.pipe_names:
            col = f"{pipe}_m_dot"
            if col in self.df_pipes.columns:
                pipe_max_flow.append((pipe, self.df_pipes[col].max()))
        pipe_max_flow.sort(key=lambda x: x[1], reverse=True)
        top_pipes = [p[0] for p in pipe_max_flow[:max_pipes]]
        
        fig, axes = plt.subplots(3, 2, figsize=(18, 14))
        fig.suptitle("ROHRBÜNDEL-ÜBERSICHT: Vorlauf (━) & Rücklauf (┅)", 
                     fontsize=16, fontweight='bold')
        
        vl_color = '#E63946'
        rl_color = '#457B9D'
        
        ax = axes[0, 0]
        for pipe in top_pipes:
            col = f"{pipe}_m_dot"
            if col in self.df_pipes.columns:
                ax.plot(self.df_pipes[col], label=pipe, alpha=0.8, linewidth=1)
        ax.set_title("Massenstrom (VL = RL)")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("kg/s")
        ax.legend(loc='upper right', fontsize=6, ncol=2)
        ax.grid(True, alpha=0.3)
        
        ax = axes[0, 1]
        for pipe in top_pipes:
            col = f"{pipe}_velocity"
            if col in self.df_pipes.columns:
                ax.plot(self.df_pipes[col], label=pipe, alpha=0.8, linewidth=1)
        limits = self.config["limits"]
        ax.axhline(y=limits["velocity_min_m_s"], color='r', linestyle='--', 
                   linewidth=2, label=f'v_min={limits["velocity_min_m_s"]}')
        ax.axhline(y=limits["velocity_max_m_s"], color='r', linestyle='--', 
                   linewidth=2, label=f'v_max={limits["velocity_max_m_s"]}')
        ax.set_title("Strömungsgeschwindigkeit")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("m/s")
        ax.legend(loc='upper right', fontsize=6)
        ax.grid(True, alpha=0.3)
        
        ax = axes[1, 0]
        for pipe in top_pipes[:6]:
            col_in = f"{pipe}_T_supply_in"
            col_out = f"{pipe}_T_supply_out"
            if col_in in self.df_pipes.columns:
                ax.plot(self.df_pipes[col_in], label=f'{pipe} ein', 
                       color=vl_color, alpha=0.7, linestyle='-')
            if col_out in self.df_pipes.columns:
                ax.plot(self.df_pipes[col_out], label=f'{pipe} aus', 
                       color=vl_color, alpha=0.4, linestyle='--')
        ax.set_title("VORLAUF: Temperatur (Ein → Aus)")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("°C")
        ax.legend(loc='upper right', fontsize=6, ncol=2)
        ax.grid(True, alpha=0.3)
        
        ax = axes[1, 1]
        for pipe in top_pipes[:6]:
            col_in = f"{pipe}_T_return_in"
            col_out = f"{pipe}_T_return_out"
            if col_in in self.df_pipes.columns:
                ax.plot(self.df_pipes[col_in], label=f'{pipe} ein', 
                       color=rl_color, alpha=0.7, linestyle='-')
            if col_out in self.df_pipes.columns:
                ax.plot(self.df_pipes[col_out], label=f'{pipe} aus', 
                       color=rl_color, alpha=0.4, linestyle='--')
        ax.set_title("RÜCKLAUF: Temperatur (Ein → Aus)")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("°C")
        ax.legend(loc='upper right', fontsize=6, ncol=2)
        ax.grid(True, alpha=0.3)
        
        ax = axes[2, 0]
        for pipe in top_pipes[:6]:
            col_s = f"{pipe}_Q_loss_supply"
            col_r = f"{pipe}_Q_loss_return"
            if col_s in self.df_pipes.columns:
                ax.plot(self.df_pipes[col_s] * 1000, label=f'{pipe} VL', 
                       color=vl_color, alpha=0.7)
            if col_r in self.df_pipes.columns:
                ax.plot(self.df_pipes[col_r] * 1000, label=f'{pipe} RL', 
                       color=rl_color, alpha=0.7, linestyle='--')
        ax.set_title("Wärmeverluste: VL vs. RL")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("kW")
        ax.legend(loc='upper right', fontsize=6, ncol=2)
        ax.grid(True, alpha=0.3)
        
        ax = axes[2, 1]
        for pipe in top_pipes[:6]:
            col_s = f"{pipe}_delta_p_supply"
            col_r = f"{pipe}_delta_p_return"
            if col_s in self.df_pipes.columns:
                ax.plot(self.df_pipes[col_s] * 1000, label=f'{pipe} VL', 
                       color=vl_color, alpha=0.7)
            if col_r in self.df_pipes.columns:
                ax.plot(self.df_pipes[col_r] * 1000, label=f'{pipe} RL', 
                       color=rl_color, alpha=0.7, linestyle='--')
        ax.set_title("Druckverluste: VL vs. RL")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("mbar")
        ax.legend(loc='upper right', fontsize=6, ncol=2)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        self._save_plot(fig, "pipe_bundle_overview.png")
        
    def _plot_pipe_bundle_details(self):
        print("  [3.2] Rohrbündel-Details...")
        
        selected = self.config["selection"]["detail_pipes"]
        selected = [p for p in selected if p in self.pipe_names]
        
        if not selected:
            pipe_max = [(p, self.df_pipes[f"{p}_m_dot"].max()) 
                       for p in self.pipe_names if f"{p}_m_dot" in self.df_pipes.columns]
            pipe_max.sort(key=lambda x: x[1], reverse=True)
            selected = [p[0] for p in pipe_max[:4]]
            
        for pipe in selected:
            self._plot_single_pipe(pipe)

    def _plot_single_pipe(self, pipe: str):
        fig, axes = plt.subplots(4, 2, figsize=(16, 18))
        fig.suptitle(f"ROHRBÜNDEL: {pipe}\nVorlauf ━━ (rot) / Rücklauf ┅┅ (blau)", 
                     fontsize=14, fontweight='bold')
        
        vl_color = '#E63946'
        rl_color = '#457B9D'
        
        ax = axes[0, 0]
        col = f"{pipe}_m_dot"
        if col in self.df_pipes.columns:
            m = self.df_pipes[col]
            ax.plot(m, color='green', linewidth=1.5)
            ax.fill_between(range(len(m)), m, alpha=0.3, color='green')
            ax.set_title(f"Massenstrom (max: {m.max():.1f} kg/s)")
        ax.set_ylabel("kg/s")
        ax.grid(True, alpha=0.3)
        
        ax = axes[0, 1]
        col = f"{pipe}_velocity"
        if col in self.df_pipes.columns:
            v = self.df_pipes[col]
            ax.plot(v, color='purple', linewidth=1.5)
            limits = self.config["limits"]
            ax.axhline(y=limits["velocity_min_m_s"], color='r', linestyle='--', label='v_min')
            ax.axhline(y=limits["velocity_max_m_s"], color='r', linestyle='--', label='v_max')
            below_pct = (v < limits["velocity_min_m_s"]).sum() / len(v) * 100
            ax.set_title(f"Geschwindigkeit ({below_pct:.0f}% unter v_min!)")
            ax.legend(fontsize=8)
        ax.set_ylabel("m/s")
        ax.grid(True, alpha=0.3)
        
        ax = axes[1, 0]
        col_in = f"{pipe}_T_supply_in"
        col_out = f"{pipe}_T_supply_out"
        if col_in in self.df_pipes.columns:
            ax.plot(self.df_pipes[col_in], color=vl_color, linewidth=2, label='T_VL_ein')
        if col_out in self.df_pipes.columns:
            ax.plot(self.df_pipes[col_out], color=vl_color, linewidth=2, 
                   linestyle='--', alpha=0.7, label='T_VL_aus')
        ax.set_title("VORLAUF: Temperatur")
        ax.set_ylabel("°C")
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        ax = axes[1, 1]
        col_in = f"{pipe}_T_return_in"
        col_out = f"{pipe}_T_return_out"
        if col_in in self.df_pipes.columns:
            ax.plot(self.df_pipes[col_in], color=rl_color, linewidth=2, label='T_RL_ein')
        if col_out in self.df_pipes.columns:
            ax.plot(self.df_pipes[col_out], color=rl_color, linewidth=2, 
                   linestyle='--', alpha=0.7, label='T_RL_aus')
        ax.set_title("RÜCKLAUF: Temperatur")
        ax.set_ylabel("°C")
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        ax = axes[2, 0]
        col = f"{pipe}_delta_p_supply"
        if col in self.df_pipes.columns:
            dp = self.df_pipes[col] * 1000
            ax.plot(dp, color=vl_color, linewidth=1.5)
            ax.fill_between(range(len(dp)), dp, alpha=0.3, color=vl_color)
            ax.set_title(f"VORLAUF: Druckverlust (max: {dp.max():.3f} mbar)")
        ax.set_ylabel("mbar")
        ax.grid(True, alpha=0.3)
        
        ax = axes[2, 1]
        col = f"{pipe}_delta_p_return"
        if col in self.df_pipes.columns:
            dp = self.df_pipes[col] * 1000
            ax.plot(dp, color=rl_color, linewidth=1.5)
            ax.fill_between(range(len(dp)), dp, alpha=0.3, color=rl_color)
            ax.set_title(f"RÜCKLAUF: Druckverlust (max: {dp.max():.3f} mbar)")
        ax.set_ylabel("mbar")
        ax.grid(True, alpha=0.3)
        
        ax = axes[3, 0]
        col_s = f"{pipe}_Q_loss_supply"
        col_r = f"{pipe}_Q_loss_return"
        total_loss = 0
        if col_s in self.df_pipes.columns:
            q_vl = self.df_pipes[col_s] * 1000
            ax.plot(q_vl, color=vl_color, linewidth=1.5, label='VL-Verlust')
            ax.fill_between(range(len(q_vl)), q_vl, alpha=0.2, color=vl_color)
            total_loss += self.df_pipes[col_s].sum()
        if col_r in self.df_pipes.columns:
            q_rl = self.df_pipes[col_r] * 1000
            ax.plot(q_rl, color=rl_color, linewidth=1.5, label='RL-Verlust')
            ax.fill_between(range(len(q_rl)), q_rl, alpha=0.2, color=rl_color)
            total_loss += self.df_pipes[col_r].sum()
        ax.set_title(f"Wärmeverluste (Σ: {total_loss:.2f} MWh)")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("kW")
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        ax = axes[3, 1]
        col = f"{pipe}_Q_consumer"
        if col in self.df_pipes.columns:
            Q = self.df_pipes[col]
            ax.plot(Q, color='green', linewidth=1.5)
            ax.fill_between(range(len(Q)), Q, alpha=0.3, color='green')
            ax.set_title(f"Wärmeabgabe (Σ: {Q.sum():.1f} MWh)")
        else:
            ax.text(0.5, 0.5, "Keine Verbraucherleistung\n(Junction-Pipe)", 
                   transform=ax.transAxes, ha='center', va='center', fontsize=12)
            ax.set_title("Wärmeabgabe")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("MW")
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        self._save_plot(fig, f"pipe_bundle_{pipe}.png")

    # ==========================================================================
    # NODE PLOTS
    # ==========================================================================
    
    def _plot_node_overview(self):
        print("  [3.3] Knoten-Übersicht...")
        
        if self.df_nodes is None or len(self.node_names) == 0:
            print("    ⚠ Keine Node-Daten verfügbar")
            return
            
        fig, axes = plt.subplots(3, 2, figsize=(18, 16))
        fig.suptitle("KNOTEN-ÜBERSICHT: Temperaturen & Wärmebedarf", 
                     fontsize=16, fontweight='bold')
        
        producers = [n for n, t in self.node_types.items() if t == "producer"]
        junctions = [n for n, t in self.node_types.items() if t == "junction"]
        consumers = [n for n, t in self.node_types.items() if t == "consumer"]
        
        vl_color = '#E63946'
        rl_color = '#457B9D'
        
        ax = axes[0, 0]
        for node in producers:
            col_vl = f"{node}_T_supply"
            col_rl = f"{node}_T_return"
            if col_vl in self.df_nodes.columns:
                ax.plot(self.df_nodes[col_vl], color=vl_color, linewidth=2, label=f'{node} VL')
            if col_rl in self.df_nodes.columns:
                ax.plot(self.df_nodes[col_rl], color=rl_color, linewidth=2, 
                       linestyle='--', label=f'{node} RL')
        ax.set_title("ERZEUGER: Temperaturen")
        ax.set_ylabel("°C")
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        ax = axes[0, 1]
        for node in junctions[:7]:
            col = f"{node}_T_supply"
            if col in self.df_nodes.columns:
                ax.plot(self.df_nodes[col], label=node, alpha=0.8)
        ax.set_title("JUNCTIONS: Vorlauf-Temperatur")
        ax.set_ylabel("°C")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        
        ax = axes[1, 0]
        for node in consumers[:10]:
            col = f"{node}_T_supply"
            if col in self.df_nodes.columns:
                ax.plot(self.df_nodes[col], label=node, alpha=0.7)
        ax.set_title("VERBRAUCHER: Vorlauf-Temperatur")
        ax.set_ylabel("°C")
        ax.legend(fontsize=6, ncol=2)
        ax.grid(True, alpha=0.3)
        
        ax = axes[1, 1]
        for node in consumers[:10]:
            col = f"{node}_T_return"
            if col in self.df_nodes.columns:
                ax.plot(self.df_nodes[col], label=node, alpha=0.7)
        ax.set_title("VERBRAUCHER: Rücklauf-Temperatur")
        ax.set_ylabel("°C")
        ax.legend(fontsize=6, ncol=2)
        ax.grid(True, alpha=0.3)
        
        ax = axes[2, 0]
        for node in consumers[:8]:
            col = f"{node}_Q_demand"
            if col in self.df_nodes.columns:
                ax.plot(self.df_nodes[col], label=node, alpha=0.7)
        ax.set_title("VERBRAUCHER: Wärmebedarf über Zeit")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("MW")
        ax.legend(fontsize=6, ncol=2)
        ax.grid(True, alpha=0.3)
        
        ax = axes[2, 1]
        demand_totals = []
        for node in consumers:
            col = f"{node}_Q_demand"
            if col in self.df_nodes.columns:
                demand_totals.append((node, self.df_nodes[col].sum()))
        demand_totals.sort(key=lambda x: x[1], reverse=True)
        
        if demand_totals:
            nodes, demands = zip(*demand_totals[:15])
            colors = plt.cm.YlOrRd(np.linspace(0.3, 0.9, len(nodes)))
            ax.barh(range(len(nodes)), demands, color=colors)
            ax.set_yticks(range(len(nodes)))
            ax.set_yticklabels(nodes, fontsize=8)
            ax.set_title("Gesamter Wärmebedarf pro Verbraucher")
            ax.set_xlabel("MWh")
            ax.invert_yaxis()
        ax.grid(True, alpha=0.3, axis='x')
        
        plt.tight_layout()
        self._save_plot(fig, "node_overview.png")
        
    def _plot_node_details(self):
        print("  [3.4] Knoten-Details...")
        
        if self.df_nodes is None or len(self.node_names) == 0:
            return
            
        selected = self.config["selection"]["detail_nodes"]
        selected = [n for n in selected if n in self.node_names]
        
        if not selected:
            selected = []
            for n, t in self.node_types.items():
                if t == "producer" and sum(1 for s in selected if self.node_types.get(s) == "producer") < 1:
                    selected.append(n)
                elif t == "junction" and sum(1 for s in selected if self.node_types.get(s) == "junction") < 2:
                    selected.append(n)
                elif t == "consumer" and sum(1 for s in selected if self.node_types.get(s) == "consumer") < 2:
                    selected.append(n)
                    
        for node in selected:
            self._plot_single_node(node)
            
    def _plot_single_node(self, node: str):
        node_type = self.node_types.get(node, "unknown")
        
        fig, axes = plt.subplots(3, 2, figsize=(16, 14))
        fig.suptitle(f"KNOTEN: {node} ({node_type.upper()})\n"
                     f"Vorlauf ━━ (rot) / Rücklauf ┅┅ (blau)", 
                     fontsize=14, fontweight='bold')
        
        vl_color = '#E63946'
        rl_color = '#457B9D'
        
        ax = axes[0, 0]
        col_vl = f"{node}_T_supply"
        col_rl = f"{node}_T_return"
        if col_vl in self.df_nodes.columns:
            ax.plot(self.df_nodes[col_vl], color=vl_color, linewidth=2, label='T_Vorlauf')
        if col_rl in self.df_nodes.columns:
            ax.plot(self.df_nodes[col_rl], color=rl_color, linewidth=2, 
                   linestyle='--', label='T_Rücklauf')
        ax.set_title("Temperaturen: VL vs. RL")
        ax.set_ylabel("°C")
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        ax = axes[0, 1]
        if col_vl in self.df_nodes.columns and col_rl in self.df_nodes.columns:
            delta_T = self.df_nodes[col_vl] - self.df_nodes[col_rl]
            ax.plot(delta_T, color='orange', linewidth=2)
            ax.fill_between(range(len(delta_T)), delta_T, alpha=0.3, color='orange')
            ax.axhline(y=self.config["limits"]["delta_T_c"], color='green', 
                      linestyle='--', label=f'Soll ΔT={self.config["limits"]["delta_T_c"]}°C')
            ax.set_title(f"Temperaturspreizung (Mittel: {delta_T.mean():.1f}°C)")
            ax.legend()
        else:
            ax.text(0.5, 0.5, "Keine RL-Temperatur\n(Junction)", 
                   transform=ax.transAxes, ha='center', va='center')
            ax.set_title("Temperaturspreizung")
        ax.set_ylabel("ΔT [°C]")
        ax.grid(True, alpha=0.3)
        
        ax = axes[1, 0]
        col_q = f"{node}_Q_demand"
        if col_q in self.df_nodes.columns:
            Q = self.df_nodes[col_q]
            ax.plot(Q, color='green', linewidth=1.5)
            ax.fill_between(range(len(Q)), Q, alpha=0.3, color='green')
            ax.set_title(f"Wärmebedarf (Σ: {Q.sum():.1f} MWh)")
        else:
            ax.text(0.5, 0.5, f"Kein Wärmebedarf\n({node_type})", 
                   transform=ax.transAxes, ha='center', va='center', fontsize=12)
            ax.set_title("Wärmebedarf")
        ax.set_ylabel("MW")
        ax.grid(True, alpha=0.3)
        
        ax = axes[1, 1]
        incoming_pipes = []
        for pipe, topo in self.network_topology.items():
            if topo.get('to') == node:
                incoming_pipes.append(pipe)
                
        total_in = None
        for pipe in incoming_pipes:
            col = f"{pipe}_m_dot"
            if col in self.df_pipes.columns:
                m = self.df_pipes[col]
                ax.plot(m, label=f'von {pipe}', alpha=0.8)
                total_in = m if total_in is None else total_in + m
                
        if total_in is not None:
            ax.plot(total_in, color='black', linewidth=2, linestyle=':', label='Σ Eingang')
        ax.set_title(f"Eingehende Massenströme ({len(incoming_pipes)} Pipes)")
        ax.set_ylabel("kg/s")
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
        
        ax = axes[2, 0]
        outgoing_pipes = []
        for pipe, topo in self.network_topology.items():
            if topo.get('from') == node:
                outgoing_pipes.append(pipe)
                
        total_out = None
        for pipe in outgoing_pipes:
            col = f"{pipe}_m_dot"
            if col in self.df_pipes.columns:
                m = self.df_pipes[col]
                ax.plot(m, label=f'nach {pipe}', alpha=0.8)
                total_out = m if total_out is None else total_out + m
                
        if total_out is not None:
            ax.plot(total_out, color='black', linewidth=2, linestyle=':', label='Σ Ausgang')
        ax.set_title(f"Ausgehende Massenströme ({len(outgoing_pipes)} Pipes)")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("kg/s")
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
        
        ax = axes[2, 1]
        if total_in is not None and total_out is not None:
            balance = total_in - total_out
            ax.plot(balance, color='purple', linewidth=1.5)
            ax.fill_between(range(len(balance)), balance, alpha=0.3, color='purple')
            ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
            ax.set_title("Massenbilanz (Ein - Aus)")
            stats = f"Max: {balance.max():.2f}\nMin: {balance.min():.2f}\nMittel: {balance.mean():.4f}"
            ax.text(0.02, 0.98, stats, transform=ax.transAxes, fontsize=9,
                   va='top', bbox=dict(facecolor='wheat', alpha=0.5))
        elif total_in is not None:
            ax.plot(total_in, color='green', linewidth=1.5)
            ax.set_title("Nur Eingang (Endverbraucher)")
        elif total_out is not None:
            ax.plot(total_out, color='blue', linewidth=1.5)
            ax.set_title("Nur Ausgang (Erzeuger)")
        else:
            ax.text(0.5, 0.5, "Keine Pipe-Daten", transform=ax.transAxes, ha='center')
            ax.set_title("Massenbilanz")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("kg/s")
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        self._save_plot(fig, f"node_detail_{node}.png")

    # ==========================================================================
    # SYSTEM FLOW
    # ==========================================================================
    
    def _plot_system_flow(self):
        print("  [3.5] Systemfluss...")
        
        fig, axes = plt.subplots(2, 2, figsize=(18, 14))
        fig.suptitle("SYSTEMFLUSS: Energie- und Massenbilanz", fontsize=16, fontweight='bold')
        
        ax = axes[0, 0]
        total_m = sum(self.df_pipes[f"{p}_m_dot"] for p in self.pipe_names 
                     if f"{p}_m_dot" in self.df_pipes.columns)
        ax.plot(total_m, 'b-', linewidth=1)
        ax.fill_between(range(len(total_m)), total_m, alpha=0.3)
        ax.set_title("Σ Massenstrom aller Rohre")
        ax.set_ylabel("kg/s")
        ax.set_xlabel("Stunde")
        ax.grid(True, alpha=0.3)
        
        ax = axes[0, 1]
        total_Q_demand = None
        for node in self.node_names:
            col = f"{node}_Q_demand"
            if col in self.df_nodes.columns:
                Q = self.df_nodes[col]
                total_Q_demand = Q if total_Q_demand is None else total_Q_demand + Q
                
        if total_Q_demand is not None:
            ax.plot(total_Q_demand, 'g-', linewidth=1)
            ax.fill_between(range(len(total_Q_demand)), total_Q_demand, alpha=0.3, color='green')
            ax.set_title(f"Σ Wärmebedarf (Gesamt: {total_Q_demand.sum():.0f} MWh)")
        ax.set_ylabel("MW")
        ax.set_xlabel("Stunde")
        ax.grid(True, alpha=0.3)
        
        ax = axes[1, 0]
        total_loss = None
        for pipe in self.pipe_names:
            col_s = f"{pipe}_Q_loss_supply"
            col_r = f"{pipe}_Q_loss_return"
            if col_s in self.df_pipes.columns:
                loss = self.df_pipes[col_s]
                if col_r in self.df_pipes.columns:
                    loss = loss + self.df_pipes[col_r]
                total_loss = loss if total_loss is None else total_loss + loss
                
        if total_loss is not None:
            ax.plot(total_loss * 1000, 'r-', linewidth=1)
            ax.fill_between(range(len(total_loss)), total_loss * 1000, alpha=0.3, color='red')
            ax.set_title(f"Σ Wärmeverluste (Gesamt: {total_loss.sum():.1f} MWh)")
        ax.set_ylabel("kW")
        ax.set_xlabel("Stunde")
        ax.grid(True, alpha=0.3)
        
        ax = axes[1, 1]
        Q_demand = total_Q_demand.sum() if total_Q_demand is not None else 0
        Q_loss = total_loss.sum() if total_loss is not None else 0
        Q_input = Q_demand + Q_loss
        
        categories = ['Wärmeerzeugung\n(berechnet)', 'Wärmeabgabe\n(Bedarf)', 'Wärmeverluste\n(Netz)']
        values = [Q_input, Q_demand, Q_loss]
        colors = ['orange', 'green', 'red']
        
        bars = ax.bar(categories, values, color=colors, alpha=0.7, edgecolor='black')
        ax.set_title("ENERGIEBILANZ")
        ax.set_ylabel("MWh")
        
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.02,
                   f'{val:.0f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        if Q_input > 0:
            eff = Q_demand / Q_input * 100
            ax.text(0.98, 0.98, f"Netz-Effizienz: {eff:.1f}%", 
                   transform=ax.transAxes, ha='right', va='top', fontsize=12,
                   bbox=dict(facecolor='lightgreen' if eff > 95 else 'lightyellow', alpha=0.8))
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        self._save_plot(fig, "system_flow.png")

    # ==========================================================================
    # PIPE-NODE KOMBINATION
    # ==========================================================================
    
    def _plot_pipe_with_nodes(self):
        print("  [3.7] Pipe-Node-Kombinationen...")
        
        pipes_with_consumers = []
        for pipe, topo in self.network_topology.items():
            to_node = topo.get('to', '')
            if to_node.startswith('V_'):
                pipes_with_consumers.append(pipe)
        
        if not pipes_with_consumers:
            pipe_flow = [(p, self.df_pipes[f"{p}_m_dot"].max()) 
                         for p in self.pipe_names if f"{p}_m_dot" in self.df_pipes.columns]
            pipe_flow.sort(key=lambda x: x[1], reverse=True)
            pipes_with_consumers = [p[0] for p in pipe_flow[:6]]
        else:
            pipes_with_consumers = pipes_with_consumers[:6]
        
        for pipe in pipes_with_consumers:
            self._plot_single_pipe_with_nodes(pipe)

    def _plot_single_pipe_with_nodes(self, pipe: str):
        topo = self.network_topology.get(pipe, {})
        from_node = topo.get('from', '?')
        to_node = topo.get('to', '?')
        
        fig = plt.figure(figsize=(18, 16))
        fig.suptitle(f"VERBINDUNG: {from_node} → [{pipe}] → {to_node}\n"
                     f"Energiefluss und Wärmeentnahme", 
                     fontsize=14, fontweight='bold')
        
        gs = fig.add_gridspec(4, 3, hspace=0.35, wspace=0.3)
        
        vl_color = '#E63946'
        rl_color = '#457B9D'
        
        # Schema
        ax = fig.add_subplot(gs[0, 0])
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 6)
        ax.axis('off')
        
        from_type = self.node_types.get(from_node, 'unknown')
        to_type = self.node_types.get(to_node, 'unknown')
        
        colors_type = {'producer': 'orange', 'junction': 'lightblue', 
                       'consumer': 'lightgreen', 'unknown': 'gray'}
        
        circle1 = plt.Circle((2, 4), 0.8, color=colors_type[from_type], ec='black', lw=2)
        ax.add_patch(circle1)
        ax.text(2, 4, from_node, ha='center', va='center', fontsize=9, fontweight='bold')
        ax.text(2, 2.8, f'({from_type})', ha='center', va='center', fontsize=7)
        
        rect = plt.Rectangle((3.5, 3.5), 3, 1, color='lightgray', ec='black', lw=2)
        ax.add_patch(rect)
        ax.text(5, 4, pipe, ha='center', va='center', fontsize=8, fontweight='bold')
        
        circle2 = plt.Circle((8, 4), 0.8, color=colors_type[to_type], ec='black', lw=2)
        ax.add_patch(circle2)
        ax.text(8, 4, to_node, ha='center', va='center', fontsize=9, fontweight='bold')
        ax.text(8, 2.8, f'({to_type})', ha='center', va='center', fontsize=7)
        
        ax.annotate('', xy=(3.3, 4.3), xytext=(2.8, 4.3),
                   arrowprops=dict(arrowstyle='->', color=vl_color, lw=2))
        ax.annotate('', xy=(7.2, 4.3), xytext=(6.7, 4.3),
                   arrowprops=dict(arrowstyle='->', color=vl_color, lw=2))
        ax.annotate('', xy=(2.8, 3.7), xytext=(3.3, 3.7),
                   arrowprops=dict(arrowstyle='->', color=rl_color, lw=2))
        ax.annotate('', xy=(6.7, 3.7), xytext=(7.2, 3.7),
                   arrowprops=dict(arrowstyle='->', color=rl_color, lw=2))
        
        ax.text(5, 5.5, 'VL →', color=vl_color, ha='center', fontsize=9, fontweight='bold')
        ax.text(5, 2.3, '← RL', color=rl_color, ha='center', fontsize=9, fontweight='bold')
        ax.set_title("Netzwerkschema", fontsize=10)
        
        # Massenstrom
        ax = fig.add_subplot(gs[0, 1:])
        col = f"{pipe}_m_dot"
        if col in self.df_pipes.columns:
            m = self.df_pipes[col]
            ax.plot(m, color='green', linewidth=1.5, label='Massenstrom')
            ax.fill_between(range(len(m)), m, alpha=0.3, color='green')
            stats_text = f"max: {m.max():.2f} kg/s\nmean: {m.mean():.2f} kg/s"
            ax.text(0.98, 0.98, stats_text, transform=ax.transAxes, ha='right', va='top',
                   fontsize=9, bbox=dict(facecolor='white', alpha=0.8))
        ax.set_title(f"Massenstrom durch [{pipe}]")
        ax.set_ylabel("kg/s")
        ax.set_xlabel("Stunde")
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        
        # Temperaturverlauf
        ax = fig.add_subplot(gs[1, :])
        
        col = f"{from_node}_T_supply"
        T_from_supply = self.df_nodes[col] if col in self.df_nodes.columns else None
        col = f"{pipe}_T_supply_in"
        T_pipe_in = self.df_pipes[col] if col in self.df_pipes.columns else None
        col = f"{pipe}_T_supply_out"
        T_pipe_out = self.df_pipes[col] if col in self.df_pipes.columns else None
        col = f"{to_node}_T_supply"
        T_to_supply = self.df_nodes[col] if col in self.df_nodes.columns else None
        
        if T_from_supply is not None:
            ax.plot(T_from_supply, color=vl_color, linewidth=2, linestyle='-',
                   label=f'{from_node} T_VL', alpha=0.9)
        if T_pipe_in is not None:
            ax.plot(T_pipe_in, color=vl_color, linewidth=1.5, linestyle='--',
                   label=f'[{pipe}] T_ein', alpha=0.7)
        if T_pipe_out is not None:
            ax.plot(T_pipe_out, color=vl_color, linewidth=1.5, linestyle=':',
                   label=f'[{pipe}] T_aus', alpha=0.7)
        if T_to_supply is not None:
            ax.plot(T_to_supply, color='darkred', linewidth=2, linestyle='-',
                   label=f'{to_node} T_VL', alpha=0.9)
        
        ax.set_title(f"VORLAUF-Temperaturverlauf: {from_node} → Pipe → {to_node}")
        ax.set_ylabel("°C")
        ax.set_xlabel("Stunde")
        ax.legend(loc='upper right', ncol=4, fontsize=8)
        ax.grid(True, alpha=0.3)
        
        if T_pipe_in is not None and T_pipe_out is not None:
            delta_T = (T_pipe_in - T_pipe_out).mean()
            ax.text(0.02, 0.02, f'ΔT Pipe (VL): {delta_T:.2f}°C', 
                   transform=ax.transAxes, fontsize=10,
                   bbox=dict(facecolor='lightyellow', alpha=0.8))
        
        # Wärmebedarf
        ax = fig.add_subplot(gs[2, 0])
        col = f"{to_node}_Q_demand"
        if col in self.df_nodes.columns:
            Q = self.df_nodes[col]
            ax.plot(Q, color='green', linewidth=1.5)
            ax.fill_between(range(len(Q)), Q, alpha=0.3, color='green')
            ax.set_title(f"Wärmebedarf {to_node}\n(Σ: {Q.sum():.1f} MWh)")
        else:
            ax.text(0.5, 0.5, f"Kein Wärmebedarf\n({to_node} ist kein Verbraucher)", 
                   transform=ax.transAxes, ha='center', va='center')
            ax.set_title(f"Wärmebedarf {to_node}")
        ax.set_ylabel("MW")
        ax.set_xlabel("Stunde")
        ax.grid(True, alpha=0.3)
        
        # Wärmeverluste
        ax = fig.add_subplot(gs[2, 1])
        col_s = f"{pipe}_Q_loss_supply"
        col_r = f"{pipe}_Q_loss_return"
        total_loss = 0
        if col_s in self.df_pipes.columns:
            Q_vl = self.df_pipes[col_s] * 1000
            ax.plot(Q_vl, color=vl_color, linewidth=1.5, label='VL-Verlust')
            total_loss += self.df_pipes[col_s].sum()
        if col_r in self.df_pipes.columns:
            Q_rl = self.df_pipes[col_r] * 1000
            ax.plot(Q_rl, color=rl_color, linewidth=1.5, label='RL-Verlust')
            total_loss += self.df_pipes[col_r].sum()
        ax.set_title(f"Wärmeverluste [{pipe}]\n(Σ: {total_loss:.2f} MWh)")
        ax.set_ylabel("kW")
        ax.set_xlabel("Stunde")
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Verbraucherleistung
        ax = fig.add_subplot(gs[2, 2])
        col = f"{pipe}_Q_consumer"
        if col in self.df_pipes.columns:
            Q_cons = self.df_pipes[col]
            ax.plot(Q_cons, color='orange', linewidth=1.5)
            ax.fill_between(range(len(Q_cons)), Q_cons, alpha=0.3, color='orange')
            ax.set_title(f"Wärmeabgabe via Pipe\n(Σ: {Q_cons.sum():.1f} MWh)")
        else:
            ax.text(0.5, 0.5, "Keine direkte\nWärmeabgabe", 
                   transform=ax.transAxes, ha='center', va='center')
            ax.set_title("Wärmeabgabe via Pipe")
        ax.set_ylabel("MW")
        ax.set_xlabel("Stunde")
        ax.grid(True, alpha=0.3)
        
        # Energiebilanz
        ax = fig.add_subplot(gs[3, :])
        
        col = f"{pipe}_m_dot"
        m_dot = self.df_pipes[col] if col in self.df_pipes.columns else pd.Series([0] * len(self.df_pipes))
        col = f"{to_node}_Q_demand"
        Q_demand = self.df_nodes[col] if col in self.df_nodes.columns else pd.Series([0] * len(self.df_nodes))
        col_s = f"{pipe}_Q_loss_supply"
        col_r = f"{pipe}_Q_loss_return"
        Q_loss_s = self.df_pipes[col_s] if col_s in self.df_pipes.columns else pd.Series([0] * len(self.df_pipes))
        Q_loss_r = self.df_pipes[col_r] if col_r in self.df_pipes.columns else pd.Series([0] * len(self.df_pipes))
        Q_loss = Q_loss_s + Q_loss_r
        
        ax.plot(m_dot * 10, 'g-', linewidth=2, label='Massenstrom ×10 (skaliert)', alpha=0.7)
        ax.plot(Q_demand, 'b-', linewidth=2, label=f'Wärmebedarf {to_node} (MW)')
        ax.plot(Q_loss * 1000, 'r-', linewidth=1.5, label='Verluste (kW)', alpha=0.7)
        ax.fill_between(range(len(Q_demand)), Q_demand, alpha=0.2, color='blue')
        
        ax.set_title("ENERGIEBILANZ: Massenstrom → Wärmeentnahme → Verluste")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("Verschiedene Einheiten")
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)
        
        Q_dem_sum = Q_demand.sum()
        Q_loss_sum = Q_loss.sum()
        total = Q_dem_sum + Q_loss_sum
        eff = Q_dem_sum / total * 100 if total > 0 else 0
        
        summary = (f"Verbindung: {from_node} → {to_node}\n"
                  f"Pipe: {pipe}\n"
                  f"─────────────────────\n"
                  f"Σ Wärmebedarf: {Q_dem_sum:.1f} MWh\n"
                  f"Σ Verluste:    {Q_loss_sum:.2f} MWh\n"
                  f"Effizienz:     {eff:.1f}%")
        ax.text(0.02, 0.98, summary, transform=ax.transAxes, fontsize=9, va='top',
               fontfamily='monospace', bbox=dict(facecolor='wheat', alpha=0.9))
        
        plt.tight_layout()
        self._save_plot(fig, f"pipe_node_{pipe}.png")

    # ==========================================================================
    # MASSENSTROM-ÜBERSICHT
    # ==========================================================================

    def _plot_mass_flow_overview(self):
        print("  [3.8] Massenstrom-Systemübersicht...")
        
        fig = plt.figure(figsize=(20, 18))
        fig.suptitle("MASSENSTRÖME & WÄRMEENTNAHME IM SYSTEM", 
                     fontsize=16, fontweight='bold')
        
        gs = fig.add_gridspec(4, 3, hspace=0.35, wspace=0.3)
        
        # Massenstrom pro Pipe
        ax = fig.add_subplot(gs[0, 0])
        pipe_flows = []
        for pipe in self.pipe_names:
            col = f"{pipe}_m_dot"
            if col in self.df_pipes.columns:
                pipe_flows.append((pipe, self.df_pipes[col].mean(), self.df_pipes[col].max()))
        pipe_flows.sort(key=lambda x: x[2], reverse=True)
        
        if pipe_flows:
            pipes, means, maxs = zip(*pipe_flows[:15])
            y_pos = range(len(pipes))
            ax.barh(y_pos, maxs, alpha=0.3, color='blue', label='Max')
            ax.barh(y_pos, means, alpha=0.7, color='blue', label='Mittel')
            ax.set_yticks(y_pos)
            ax.set_yticklabels(pipes, fontsize=7)
            ax.set_title("Massenstrom pro Pipe")
            ax.set_xlabel("kg/s")
            ax.legend(fontsize=8)
            ax.invert_yaxis()
        ax.grid(True, alpha=0.3, axis='x')
        
        # Massenstrom Zeitreihe
        ax = fig.add_subplot(gs[0, 1:])
        for pipe, _, _ in pipe_flows[:5]:
            col = f"{pipe}_m_dot"
            ax.plot(self.df_pipes[col], label=pipe, linewidth=1.5, alpha=0.8)
        ax.set_title("Massenstrom Zeitverläufe (Top 5 Pipes)")
        ax.set_xlabel("Stunde")
        ax.set_ylabel("kg/s")
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Korrelation
        ax = fig.add_subplot(gs[1, 0])
        
        total_Q = None
        for node in self.node_names:
            col = f"{node}_Q_demand"
            if col in self.df_nodes.columns:
                total_Q = self.df_nodes[col] if total_Q is None else total_Q + self.df_nodes[col]
        
        total_m = None
        for pipe in self.pipe_names:
            col = f"{pipe}_m_dot"
            if col in self.df_pipes.columns:
                total_m = self.df_pipes[col] if total_m is None else total_m + self.df_pipes[col]
        
        if total_Q is not None and total_m is not None:
            ax.scatter(total_m, total_Q, alpha=0.5, s=10, c=range(len(total_m)), cmap='viridis')
            ax.set_xlabel("Σ Massenstrom (kg/s)")
            ax.set_ylabel("Σ Wärmebedarf (MW)")
            corr = np.corrcoef(total_m, total_Q)[0, 1]
            ax.set_title(f"Korrelation: ṁ ↔ Q\n(r = {corr:.3f})")
        ax.grid(True, alpha=0.3)
        
        # Wärmeentnahme gestapelt
        ax = fig.add_subplot(gs[1, 1:])
        consumers = [n for n, t in self.node_types.items() if t == 'consumer']
        
        consumer_demand = []
        for c in consumers:
            col = f"{c}_Q_demand"
            if col in self.df_nodes.columns:
                consumer_demand.append((c, self.df_nodes[col].sum()))
        consumer_demand.sort(key=lambda x: x[1], reverse=True)
        
        top_consumers = [c[0] for c in consumer_demand[:8]]
        Q_data = []
        labels = []
        for c in top_consumers:
            col = f"{c}_Q_demand"
            if col in self.df_nodes.columns:
                Q_data.append(self.df_nodes[col].values)
                labels.append(c)
        
        if Q_data:
            ax.stackplot(range(len(Q_data[0])), *Q_data, labels=labels, alpha=0.7)
            ax.set_title("Wärmeentnahme nach Verbraucher (gestapelt)")
            ax.set_xlabel("Stunde")
            ax.set_ylabel("MW")
            ax.legend(loc='upper right', fontsize=7, ncol=2)
        ax.grid(True, alpha=0.3)
        
        # Temperaturabfall
        ax = fig.add_subplot(gs[2, :2])
        
        temp_drops = []
        for pipe in self.pipe_names:
            col_in = f"{pipe}_T_supply_in"
            col_out = f"{pipe}_T_supply_out"
            if col_in in self.df_pipes.columns and col_out in self.df_pipes.columns:
                delta_T = (self.df_pipes[col_in] - self.df_pipes[col_out]).mean()
                temp_drops.append((pipe, delta_T, self.df_pipes[col_in].mean()))
        
        if temp_drops:
            temp_drops.sort(key=lambda x: x[2], reverse=True)
            pipes, drops, temps_in = zip(*temp_drops[:20])
            
            colors = plt.cm.coolwarm(np.linspace(0.8, 0.2, len(pipes)))
            ax.bar(range(len(pipes)), drops, color=colors, alpha=0.8)
            ax.set_xticks(range(len(pipes)))
            ax.set_xticklabels(pipes, rotation=45, ha='right', fontsize=6)
            ax.set_title("VL-Temperaturabfall pro Pipe (sortiert nach T_ein)")
            ax.set_ylabel("ΔT (°C)")
            
            ax2 = ax.twinx()
            ax2.plot(range(len(pipes)), temps_in, 'ko-', markersize=3, label='T_ein')
            ax2.set_ylabel("T_supply_in (°C)")
        ax.grid(True, alpha=0.3, axis='y')
        
        # Temperatur vs Bedarf
        ax = fig.add_subplot(gs[2, 2])
        
        T_supply_consumers = []
        Q_demand_consumers = []
        names = []
        for node in consumers:
            col_T = f"{node}_T_supply"
            col_Q = f"{node}_Q_demand"
            if col_T in self.df_nodes.columns and col_Q in self.df_nodes.columns:
                T_supply_consumers.append(self.df_nodes[col_T].mean())
                Q_demand_consumers.append(self.df_nodes[col_Q].sum())
                names.append(node)
        
        if T_supply_consumers:
            ax.scatter(T_supply_consumers, Q_demand_consumers, 
                      c=range(len(names)), cmap='viridis', s=50, alpha=0.7)
            ax.set_xlabel("Mittlere VL-Temp (°C)")
            ax.set_ylabel("Gesamtbedarf (MWh)")
            ax.set_title("Verbraucher:\nTemp vs. Bedarf")
            for i, name in enumerate(names):
                ax.annotate(name, (T_supply_consumers[i], Q_demand_consumers[i]), fontsize=6)
        ax.grid(True, alpha=0.3)
        
        # Energiebilanz-Schema
        ax = fig.add_subplot(gs[3, :])
        
        Q_demand_total = total_Q.sum() if total_Q is not None else 0
        
        Q_loss_vl = 0
        Q_loss_rl = 0
        for pipe in self.pipe_names:
            col_s = f"{pipe}_Q_loss_supply"
            col_r = f"{pipe}_Q_loss_return"
            if col_s in self.df_pipes.columns:
                Q_loss_vl += self.df_pipes[col_s].sum()
            if col_r in self.df_pipes.columns:
                Q_loss_rl += self.df_pipes[col_r].sum()
        Q_loss_total = Q_loss_vl + Q_loss_rl
        Q_input = Q_demand_total + Q_loss_total
        
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.axis('off')
        
        ax.add_patch(plt.Rectangle((0.5, 3), 1.5, 4, color='orange', alpha=0.8))
        ax.text(1.25, 5, f"ERZEUGUNG\n{Q_input:.0f} MWh", ha='center', va='center', 
               fontsize=11, fontweight='bold')
        
        ax.annotate('', xy=(2.5, 5), xytext=(2, 5),
                   arrowprops=dict(arrowstyle='->', color='orange', lw=3))
        
        ax.add_patch(plt.Rectangle((3, 2.5), 3, 5, color='lightgray', alpha=0.8, ec='black'))
        ax.text(4.5, 5, "WÄRMENETZ", ha='center', va='center', fontsize=12, fontweight='bold')
        
        ax.add_patch(plt.Rectangle((3.5, 0.5), 2, 1.5, color='red', alpha=0.6))
        loss_pct = Q_loss_total / Q_input * 100 if Q_input > 0 else 0
        ax.text(4.5, 1.25, f"VERLUSTE\n{Q_loss_total:.1f} MWh\n({loss_pct:.1f}%)", 
               ha='center', va='center', fontsize=9)
        ax.annotate('', xy=(4.5, 2), xytext=(4.5, 2.5),
                   arrowprops=dict(arrowstyle='->', color='red', lw=2))
        ax.text(3.2, 0.3, f"VL: {Q_loss_vl:.1f}", fontsize=7, color='darkred')
        ax.text(5.0, 0.3, f"RL: {Q_loss_rl:.1f}", fontsize=7, color='darkblue')
        
        ax.annotate('', xy=(7, 5), xytext=(6, 5),
                   arrowprops=dict(arrowstyle='->', color='green', lw=3))
        
        ax.add_patch(plt.Rectangle((7.5, 3), 2, 4, color='green', alpha=0.6))
        demand_pct = Q_demand_total / Q_input * 100 if Q_input > 0 else 0
        ax.text(8.5, 5, f"VERBRAUCHER\n{Q_demand_total:.0f} MWh\n({demand_pct:.1f}%)", 
               ha='center', va='center', fontsize=10, fontweight='bold')
        
        eff = Q_demand_total / Q_input * 100 if Q_input > 0 else 0
        ax.text(4.5, 8.5, f"Netz-Effizienz: {eff:.1f}%", ha='center', fontsize=11,
               bbox=dict(facecolor='lightyellow', alpha=0.9, boxstyle='round'))
        
        ax.set_title("ENERGIEFLUSS-ÜBERSICHT", fontsize=14, fontweight='bold', y=1.02)
        
        plt.tight_layout()
        self._save_plot(fig, "mass_flow_system_overview.png")

    # ==========================================================================
    # DASHBOARD
    # ==========================================================================
    
    def _plot_dashboard(self):
        print("  [3.6] Dashboard...")
        
        fig = plt.figure(figsize=(22, 18))
        scenario = self.config["scenario"]
        fig.suptitle(f"NETZWERK-DASHBOARD: {scenario['name']} - {scenario['period']}", 
                     fontsize=18, fontweight='bold', y=0.98)
        
        gs = fig.add_gridspec(4, 4, hspace=0.35, wspace=0.3)
        
        ax = fig.add_subplot(gs[0, 0])
        total_m = sum(self.df_pipes[f"{p}_m_dot"] for p in self.pipe_names 
                     if f"{p}_m_dot" in self.df_pipes.columns)
        ax.plot(total_m, 'b-', linewidth=0.8)
        ax.fill_between(range(len(total_m)), total_m, alpha=0.3)
        ax.set_title("Σ Massenstrom")
        ax.set_ylabel("kg/s")
        
        ax = fig.add_subplot(gs[0, 1])
        all_v = [self.df_pipes[f"{p}_velocity"].values for p in self.pipe_names 
                if f"{p}_velocity" in self.df_pipes.columns]
        if all_v:
            ax.hist(np.concatenate(all_v), bins=50, color='green', alpha=0.7)
            ax.axvline(x=self.config["limits"]["velocity_min_m_s"], color='r', linestyle='--')
        ax.set_title("Geschwindigkeitsverteilung")
        ax.set_xlabel("m/s")
        
        ax = fig.add_subplot(gs[0, 2])
        total_Q = None
        for node in self.node_names:
            col = f"{node}_Q_demand"
            if col in self.df_nodes.columns:
                total_Q = self.df_nodes[col] if total_Q is None else total_Q + self.df_nodes[col]
        if total_Q is not None:
            ax.plot(total_Q, 'g-', linewidth=0.8)
            ax.fill_between(range(len(total_Q)), total_Q, alpha=0.3, color='green')
            ax.set_title(f"Σ Wärmebedarf ({total_Q.sum():.0f} MWh)")
        ax.set_ylabel("MW")
        
        ax = fig.add_subplot(gs[0, 3])
        total_loss = None
        for p in self.pipe_names:
            col_s = f"{p}_Q_loss_supply"
            col_r = f"{p}_Q_loss_return"
            if col_s in self.df_pipes.columns:
                loss = self.df_pipes[col_s].copy()
                if col_r in self.df_pipes.columns:
                    loss = loss + self.df_pipes[col_r]
                total_loss = loss if total_loss is None else total_loss + loss
        if total_loss is None:
            total_loss = pd.Series([0] * len(self.df_pipes))
        ax.plot(total_loss * 1000, 'r-', linewidth=0.8)
        ax.fill_between(range(len(total_loss)), total_loss * 1000, alpha=0.3, color='red')
        ax.set_title(f"Σ Verluste ({total_loss.sum():.1f} MWh)")
        ax.set_ylabel("kW")
        
        ax = fig.add_subplot(gs[1, :2])
        m_data = [self.df_pipes[f"{p}_m_dot"].values for p in self.pipe_names 
                 if f"{p}_m_dot" in self.df_pipes.columns]
        if m_data:
            im = ax.imshow(np.array(m_data), aspect='auto', cmap='Blues')
            ax.set_title("Massenstrom pro Rohr")
            ax.set_xlabel("Stunde")
            ax.set_ylabel("Rohr")
            ax.set_yticks(range(len(self.pipe_names)))
            ax.set_yticklabels(self.pipe_names, fontsize=5)
            plt.colorbar(im, ax=ax, label='kg/s', shrink=0.8)
            
        ax = fig.add_subplot(gs[1, 2:])
        q_data = []
        q_names = []
        for node in self.node_names:
            col = f"{node}_Q_demand"
            if col in self.df_nodes.columns and self.df_nodes[col].max() > 0:
                q_data.append(self.df_nodes[col].values)
                q_names.append(node)
        if q_data:
            im = ax.imshow(np.array(q_data), aspect='auto', cmap='YlOrRd')
            ax.set_title("Wärmebedarf pro Verbraucher")
            ax.set_xlabel("Stunde")
            ax.set_ylabel("Knoten")
            ax.set_yticks(range(len(q_names)))
            ax.set_yticklabels(q_names, fontsize=6)
            plt.colorbar(im, ax=ax, label='MW', shrink=0.8)
            
        ax = fig.add_subplot(gs[2, :2])
        t = 0
        t_data = []
        for node in self.node_names:
            col_vl = f"{node}_T_supply"
            col_rl = f"{node}_T_return"
            if col_vl in self.df_nodes.columns:
                t_data.append({
                    'node': node,
                    'T_VL': self.df_nodes[col_vl].iloc[t],
                    'T_RL': self.df_nodes[col_rl].iloc[t] if col_rl in self.df_nodes.columns else np.nan
                })
        if t_data:
            df_t = pd.DataFrame(t_data)
            x = range(len(df_t))
            w = 0.35
            ax.bar([i-w/2 for i in x], df_t['T_VL'], w, label='VL', color='red', alpha=0.7)
            ax.bar([i+w/2 for i in x], df_t['T_RL'].fillna(0), w, label='RL', color='blue', alpha=0.7)
            ax.set_xticks(x)
            ax.set_xticklabels(df_t['node'], rotation=45, ha='right', fontsize=5)
            ax.set_title(f"Temperaturprofil (t={t})")
            ax.set_ylabel("°C")
            ax.legend(fontsize=8)
            
        ax = fig.add_subplot(gs[2, 2:])
        demand_totals = []
        for node in self.node_names:
            col = f"{node}_Q_demand"
            if col in self.df_nodes.columns:
                demand_totals.append((node, self.df_nodes[col].sum()))
        demand_totals.sort(key=lambda x: x[1], reverse=True)
        top_10 = demand_totals[:12]
        if top_10:
            nodes, vals = zip(*top_10)
            ax.barh(range(len(nodes)), vals, color='green', alpha=0.7)
            ax.set_yticks(range(len(nodes)))
            ax.set_yticklabels(nodes, fontsize=8)
            ax.set_title("Top Wärmebedarf")
            ax.set_xlabel("MWh")
            ax.invert_yaxis()
            
        ax = fig.add_subplot(gs[3, 0:2])
        ax.axis('off')
        
        v_max = max(self.df_pipes[f"{p}_velocity"].max() for p in self.pipe_names 
                   if f"{p}_velocity" in self.df_pipes.columns)
        v_mean = np.mean([self.df_pipes[f"{p}_velocity"].mean() for p in self.pipe_names 
                        if f"{p}_velocity" in self.df_pipes.columns])
        Q_demand = total_Q.sum() if total_Q is not None else 0
        Q_loss = total_loss.sum()
        eff = Q_demand / (Q_demand + Q_loss) * 100 if (Q_demand + Q_loss) > 0 else 0
        
        stats = f"""
NETZWERK-STATISTIK                          HYDRAULIK
{'═'*35}        {'═'*35}
Rohrbündel:     {len(self.pipe_names):>6}                  v_max:      {v_max:>12.4f} m/s
Knoten:         {len(self.node_names):>6}                  v_mittel:   {v_mean:>12.4f} m/s
  - Erzeuger:   {sum(1 for t in self.node_types.values() if t=='producer'):>6}                  
  - Junctions:  {sum(1 for t in self.node_types.values() if t=='junction'):>6}                  THERMISCH
  - Verbraucher:{sum(1 for t in self.node_types.values() if t=='consumer'):>6}                  {'═'*35}

                                            Wärmebedarf:  {Q_demand:>10.0f} MWh
ENERGIE                                     Verluste:     {Q_loss:>10.1f} MWh
{'═'*35}        Effizienz:    {eff:>10.1f} %
"""
        ax.text(0.02, 0.95, stats, transform=ax.transAxes, fontsize=10,
               va='top', fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
               
        ax = fig.add_subplot(gs[3, 2:])
        ax.axis('off')
        
        v_below = sum((self.df_pipes[f"{p}_velocity"] < 0.3).sum() 
                     for p in self.pipe_names if f"{p}_velocity" in self.df_pipes.columns)
        total_v = len(self.df_pipes) * len(self.pipe_names)
        
        warnings = []
        if v_below / total_v > 0.5:
            warnings.append(f"❌ {v_below/total_v*100:.0f}% Geschwindigkeit unter v_min!")
            warnings.append("   → Rohrdurchmesser reduzieren (aktuell 1000mm)")
        if eff < 95:
            warnings.append(f"⚠ Effizienz {eff:.1f}% < 95%")
        if not warnings:
            warnings.append("✅ Keine kritischen Befunde")
            
        warn_text = "BEWERTUNG & EMPFEHLUNGEN\n" + "═"*40 + "\n\n" + "\n".join(warnings)
        ax.text(0.02, 0.95, warn_text, transform=ax.transAxes, fontsize=10,
               va='top', fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
        
        plt.savefig(self.output_path / "dashboard.png", 
                   dpi=self.config["plot_settings"]["dpi"], bbox_inches='tight')
        print(f"    ✓ dashboard.png")
        plt.close(fig)

    # ==========================================================================
    # HILFSFUNKTIONEN
    # ==========================================================================
    
    def _save_plot(self, fig, filename):
        filepath = self.output_path / filename
        fig.savefig(filepath, dpi=self.config["plot_settings"]["dpi"], bbox_inches='tight')
        print(f"    ✓ {filename}")
        plt.close(fig)
        
    def _export_results(self):
        print("\n[4] EXPORT")
        
        pipe_stats = []
        for pipe in self.pipe_names:
            stats = {"pipe": pipe}
            col = f"{pipe}_m_dot"
            if col in self.df_pipes.columns:
                stats["m_dot_max"] = self.df_pipes[col].max()
                stats["m_dot_mean"] = self.df_pipes[col].mean()
            col = f"{pipe}_velocity"
            if col in self.df_pipes.columns:
                stats["v_max"] = self.df_pipes[col].max()
                stats["v_mean"] = self.df_pipes[col].mean()
                stats["v_below_min_pct"] = (self.df_pipes[col] < 0.3).sum() / len(self.df_pipes) * 100
            col_s = f"{pipe}_Q_loss_supply"
            col_r = f"{pipe}_Q_loss_return"
            if col_s in self.df_pipes.columns:
                stats["Q_loss_MWh"] = self.df_pipes[col_s].sum()
                if col_r in self.df_pipes.columns:
                    stats["Q_loss_MWh"] += self.df_pipes[col_r].sum()
            col = f"{pipe}_Q_consumer"
            if col in self.df_pipes.columns:
                stats["Q_consumer_MWh"] = self.df_pipes[col].sum()
            pipe_stats.append(stats)
            
        df_stats = pd.DataFrame(pipe_stats)
        df_stats.to_csv(self.output_path / "pipe_statistics.csv", index=False)
        print(f"  ✓ pipe_statistics.csv")
        
        node_stats = []
        for node in self.node_names:
            stats = {"node": node, "type": self.node_types.get(node, "unknown")}
            col = f"{node}_Q_demand"
            if col in self.df_nodes.columns:
                stats["Q_demand_MWh"] = self.df_nodes[col].sum()
                stats["Q_demand_max_MW"] = self.df_nodes[col].max()
            node_stats.append(stats)
            
        df_nodes = pd.DataFrame(node_stats)
        df_nodes.to_csv(self.output_path / "node_statistics.csv", index=False)
        print(f"  ✓ node_statistics.csv")
        
    def _print_summary(self):
        print("\n" + "=" * 70)
        print("ANALYSE ABGESCHLOSSEN")
        print("=" * 70)
        print(f"\nPlots gespeichert in: {self.output_path}")
        print("\nDateien:")
        for f in sorted(self.output_path.glob("*.png")):
            print(f"  • {f.name}")
        for f in sorted(self.output_path.glob("*.csv")):
            print(f"  • {f.name}")


# ==============================================================================
# HAUPTPROGRAMM
# ==============================================================================

if __name__ == "__main__":
    analyzer = NetworkAnalyzer(CONFIG)
    analyzer.run()