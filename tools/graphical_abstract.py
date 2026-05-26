"""
Graphical Abstract v3 — Real network layout adapted
District Heating Topology & Physics Fidelity Comparison
"""

import matplotlib
matplotlib.use('Agg')  # Avoid display warnings

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

# ─── CONFIG ───────────────────────────────────────────────────────
COLORS = {
    'supply': '#C0392B',
    'supply_light': '#F5B7B1',
    'return': '#2980B9',
    'return_light': '#AED6F1',
    'orange': '#E67E22',
    'blue': '#3498DB',
    'teal': '#1ABC9C',
    'gray': '#7F8C8D',
    'dark': '#2C3E50',
    'white': '#FFFFFF',
    'lightgray': '#F7F9F9',
    'green': '#27AE60',
}

fig = plt.figure(figsize=(25, 10), dpi=150, facecolor='white')

# ─── LAYOUT ───────────────────────────────────────────────────────
ax_upper = fig.add_axes([0.02, 0.40, 0.96, 0.58])
ax_lower = fig.add_axes([0.06, 0.04, 0.55, 0.33])
ax_zoom = fig.add_axes([0.66, 0.04, 0.30, 0.33])

# ═══════════════════════════════════════════════════════════════════
# UPPER SECTION: Network Diagrams
# ═══════════════════════════════════════════════════════════════════
ax_upper.set_xlim(0, 100)
ax_upper.set_ylim(0, 60)
ax_upper.axis('off')

# ─── Helper Functions ─────────────────────────────────────────────
def draw_node(ax, x, y, size=1.5, color=COLORS['dark'], alpha=1.0):
    circle = plt.Circle((x, y), size, color=color, zorder=5, alpha=alpha)
    ax.add_patch(circle)

def draw_pipe(ax, x1, y1, x2, y2, color=COLORS['supply'], lw=3,
              style='-', alpha=1.0):
    ax.plot([x1, x2], [y1, y2], color=color, lw=lw, ls=style,
            alpha=alpha, zorder=3, solid_capstyle='round')

def draw_pipe_double(ax, x1, y1, x2, y2, lw=2.5, offset=0.4):
    """Draw supply + return pipe as parallel lines."""
    dx, dy = x2 - x1, y2 - y1
    length = np.sqrt(dx**2 + dy**2)
    if length == 0:
        return
    nx, ny = -dy / length * offset, dx / length * offset
    draw_pipe(ax, x1 + nx, y1 + ny, x2 + nx, y2 + ny, COLORS['supply'], lw)
    draw_pipe(ax, x1 - nx, y1 - ny, x2 - nx, y2 - ny, COLORS['return'], lw)

def draw_pipe_gradient(ax, x1, y1, x2, y2, lw=3, n_segments=15):
    """Draw pipe with strong color gradient (temperature drop)."""
    for i in range(n_segments):
        frac = i / n_segments
        frac_next = (i + 1) / n_segments
        xi = x1 + frac * (x2 - x1)
        yi = y1 + frac * (y2 - y1)
        xi_next = x1 + frac_next * (x2 - x1)
        yi_next = y1 + frac_next * (y2 - y1)
        r = int(192 * (1 - frac) + 245 * frac)
        g = int(57 * (1 - frac) + 183 * frac)
        b = int(43 * (1 - frac) + 177 * frac)
        color = f'#{r:02x}{g:02x}{b:02x}'
        ax.plot([xi, xi_next], [yi, yi_next], color=color, lw=lw,
                zorder=3, solid_capstyle='round')

def draw_heat_loss_arrow(ax, x, y, size=2.0):
    """Small arrow indicating heat loss."""
    ax.annotate('', xy=(x + 0.3, y - size), xytext=(x, y),
                arrowprops=dict(arrowstyle='->', color=COLORS['orange'],
                               lw=1.2, connectionstyle='arc3,rad=0.3'))

def draw_box_label(ax, x, y, text, fontsize=9, color=COLORS['dark'],
                   bg=COLORS['lightgray'], edge=COLORS['gray']):
    ax.text(x, y, text, ha='center', va='center', fontsize=fontsize,
            color=color, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=bg,
                     edgecolor=edge, lw=0.8))

def draw_building(ax, x, y, w=2, h=1.5, color=COLORS['gray']):
    """Simple building rectangle."""
    rect = plt.Rectangle((x - w/2, y - h/2), w, h, 
                          facecolor=color, edgecolor=COLORS['dark'],
                          lw=0.8, alpha=0.5, zorder=2)
    ax.add_patch(rect)

# ─── Column centers ───────────────────────────────────────────────
col_centers = [12.5, 37.5, 62.5, 87.5]

# ═══════════════════════════════════════════════════════════════════
# DIAGRAM 1: L1 — Copperplate (unchanged)
# ═══════════════════════════════════════════════════════════════════
cx = col_centers[0]

ax_upper.text(cx, 58, 'L1 — Copperplate', ha='center', va='top',
              fontsize=13, fontweight='bold', color=COLORS['dark'])

# Central bus
circle_main = plt.Circle((cx, 35), 5, facecolor='#EBF5FB',
                          edgecolor=COLORS['dark'], lw=2.5, zorder=4)
ax_upper.add_patch(circle_main)
ax_upper.text(cx, 35, 'Single\nBus', ha='center', va='center',
              fontsize=10, color=COLORS['dark'], fontweight='bold')

# Assets
assets = [
    (cx - 7, 47, 'CHP'), (cx, 50, 'HP'), (cx + 7, 47, 'GB'),
    (cx - 7, 23, 'TES'), (cx + 7, 23, 'EB'),
]
for ax_x, ay, label in assets:
    draw_box_label(ax_upper, ax_x, ay, label, fontsize=8)
    draw_pipe(ax_upper, ax_x,
              ay - 2 if ay > 35 else ay + 2,
              cx + (ax_x - cx) * 0.3,
              35 + 4 * (1 if ay > 35 else -1),
              color=COLORS['gray'], lw=1.2, style='--')

# Demand arrow
ax_upper.annotate('', xy=(cx, 14), xytext=(cx, 30),
                  arrowprops=dict(arrowstyle='->', lw=3,
                                 color=COLORS['blue']))
ax_upper.text(cx, 12, 'Demand (all)', ha='center', va='top',
              fontsize=9, color=COLORS['dark'])

# Missing physics
ax_upper.text(cx, 5, r'$\times$ Q$_{loss}$   $\times$ $\Delta$P   $\times$ $\tau$',
              ha='center', fontsize=9, color=COLORS['supply'],
              fontweight='bold')

# ═══════════════════════════════════════════════════════════════════
# DIAGRAM 2: L2 — 7 Zones (SPINE TOPOLOGY matching your network)
# ═══════════════════════════════════════════════════════════════════
cx = col_centers[1]

ax_upper.text(cx, 58, 'L2 — 7 Zones', ha='center', va='top',
              fontsize=13, fontweight='bold', color=COLORS['dark'])

# Spine topology: main trunk goes bottom-left to top-right
# with branches to both sides (matching your real network)
l2_nodes = {
    'Z1': (cx - 6, 20),   # Source node (bottom-left, central plant)
    'Z2': (cx - 4, 30),   # Junction on trunk
    'Z3': (cx - 1, 38),   # Junction on trunk
    'Z4': (cx + 2, 45),   # Junction on trunk (upper)
    'Z5': (cx - 9, 33),   # Branch left (consumer zone)
    'Z6': (cx + 5, 35),   # Branch right (consumer zone)
    'Z7': (cx + 7, 48),   # Remote node (HP location, top-right)
}

# Trunk edges + branch edges
l2_edges = [
    ('Z1', 'Z2'),  # Trunk
    ('Z2', 'Z3'),  # Trunk
    ('Z3', 'Z4'),  # Trunk
    ('Z2', 'Z5'),  # Branch left
    ('Z3', 'Z6'),  # Branch right
    ('Z4', 'Z7'),  # Branch to remote HP
]

for e1, e2 in l2_edges:
    x1, y1 = l2_nodes[e1]
    x2, y2 = l2_nodes[e2]
    draw_pipe_double(ax_upper, x1, y1, x2, y2, lw=2.8, offset=0.5)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    draw_heat_loss_arrow(ax_upper, mx + 1.2, my, size=1.5)

for name, (nx_pos, ny_pos) in l2_nodes.items():
    draw_node(ax_upper, nx_pos, ny_pos, size=1.8, color=COLORS['dark'])

# Asset labels at specific nodes
draw_box_label(ax_upper, cx - 9, 17, 'CHP+TES\n+GB', fontsize=6, bg='#FDEBD0')
draw_box_label(ax_upper, cx + 10, 50, 'HP+EB', fontsize=6, bg='#D5F5E3')

# Small building icons at consumer zones
for zn in ['Z5', 'Z6']:
    zx, zy = l2_nodes[zn]
    draw_building(ax_upper, zx, zy - 3.5, w=3, h=2)

# Labels
ax_upper.text(cx, 7, r'$\checkmark$ Q$_{loss}$ (fixed U$\cdot$L$\cdot\Delta$T)',
              ha='center', fontsize=9, color=COLORS['green'], fontweight='bold')
ax_upper.text(cx, 3, r'$\times$ $\Delta$P   $\times$ $\tau$   $\times$ T-propagation',
              ha='center', fontsize=8, color=COLORS['gray'])

# ═══════════════════════════════════════════════════════════════════
# DIAGRAM 3: L3 — 15 Nodes (SPINE TOPOLOGY, more detail)
# ═══════════════════════════════════════════════════════════════════
cx = col_centers[2]

ax_upper.text(cx, 58, 'L3 — 15 Nodes\n(basic MILP)', ha='center',
              va='top', fontsize=13, fontweight='bold', color=COLORS['dark'])

# Real-topology-inspired: main spine with multiple branches
# Spine runs from bottom-left (source) to top-right (remote HP)
l3_nodes = {
    # Main trunk (spine) — bottom-left to top-right
    'J1':  (cx - 8, 18),   # Central plant (source)
    'J2':  (cx - 6, 24),   # Trunk junction 1
    'J3':  (cx - 4, 30),   # Trunk junction 2
    'J4':  (cx - 2, 36),   # Trunk junction 3
    'J5':  (cx + 0, 40),   # Trunk junction 4
    'J6':  (cx + 2, 44),   # Trunk junction 5
    'J7':  (cx + 4, 48),   # Trunk end (near remote HP)
    # Branches left (west consumers)
    'J8':  (cx - 10, 27),  # Branch from J2
    'J9':  (cx - 9, 33),   # Branch from J3
    'J10': (cx - 7, 39),   # Branch from J4
    'J11': (cx - 5, 45),   # Branch from J5
    # Branches right (east consumers)
    'J12': (cx + 2, 27),   # Branch from J2
    'J13': (cx + 4, 33),   # Branch from J3
    'J14': (cx + 6, 40),   # Branch from J5
    # Remote HP location
    'J15': (cx + 7, 51),   # Remote HP node
}

l3_edges = [
    # Main trunk
    ('J1', 'J2'), ('J2', 'J3'), ('J3', 'J4'), ('J4', 'J5'),
    ('J5', 'J6'), ('J6', 'J7'),
    # Branches left
    ('J2', 'J8'), ('J3', 'J9'), ('J4', 'J10'), ('J5', 'J11'),
    # Branches right
    ('J2', 'J12'), ('J3', 'J13'), ('J5', 'J14'),
    # Remote HP connection
    ('J7', 'J15'),
]

for e1, e2 in l3_edges:
    x1, y1 = l3_nodes[e1]
    x2, y2 = l3_nodes[e2]
    draw_pipe_double(ax_upper, x1, y1, x2, y2, lw=1.8, offset=0.3)
    # Small heat loss arrows on longer segments
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    pipe_len = np.sqrt((x2-x1)**2 + (y2-y1)**2)
    if pipe_len > 4:  # Only on longer pipes
        draw_heat_loss_arrow(ax_upper, mx + 0.8, my, size=1.0)

for name, (nx_pos, ny_pos) in l3_nodes.items():
    draw_node(ax_upper, nx_pos, ny_pos, size=0.9, color=COLORS['dark'])

# Asset indicators
draw_box_label(ax_upper, cx - 10, 14, 'CHP+TES+GB', fontsize=6, bg='#FDEBD0')
draw_box_label(ax_upper, cx + 9, 53, 'HP+EB', fontsize=6, bg='#D5F5E3')

# Small buildings at branch ends
branch_ends = ['J8', 'J9', 'J10', 'J11', 'J12', 'J13', 'J14']
for be in branch_ends:
    bx, by = l3_nodes[be]
    draw_building(ax_upper, bx, by, w=1.8, h=1.2, color='#BDC3C7')

# Labels
ax_upper.text(cx, 7, r'$\checkmark$ Q$_{loss}$ (fixed U$\cdot$L$\cdot\Delta$T)',
              ha='center', fontsize=9, color=COLORS['green'], fontweight='bold')
ax_upper.text(cx, 3, 'Physics identical to L2',
              ha='center', fontsize=8, color=COLORS['gray'], style='italic')

# ═══════════════════════════════════════════════════════════════════
# DIAGRAM 4: L3⁺/L3ᴺᴸ — Extended Physics (same spine topology)
# ═══════════════════════════════════════════════════════════════════
cx = col_centers[3]
offset_x = col_centers[3] - col_centers[2]

ax_upper.text(cx, 58, r'L3$^+$ / L3$^{NL}$ — 15 Nodes' + '\n(extended physics)',
              ha='center', va='top', fontsize=13, fontweight='bold',
              color=COLORS['dark'])

# Same topology as L3 but with gradient pipes (T-drop visible)
for e1, e2 in l3_edges:
    x1, y1 = l3_nodes[e1]
    x2, y2 = l3_nodes[e2]
    # Gradient pipe (supply) — shows temperature dropping
    draw_pipe_gradient(ax_upper, x1 + offset_x, y1,
                       x2 + offset_x, y2, lw=2.8, n_segments=12)
    # Return pipe (constant, thin blue)
    dx, dy = x2 - x1, y2 - y1
    length = np.sqrt(dx**2 + dy**2)
    if length > 0:
        nx_off = -dy / length * 0.4
        ny_off = dx / length * 0.4
        draw_pipe(ax_upper, x1 + offset_x - nx_off, y1 - ny_off,
                  x2 + offset_x - nx_off, y2 - ny_off,
                  COLORS['return_light'], lw=1.5)

for name, (nx_pos, ny_pos) in l3_nodes.items():
    draw_node(ax_upper, nx_pos + offset_x, ny_pos, size=0.9,
              color=COLORS['dark'])

# Buildings at branch ends
for be in branch_ends:
    bx, by = l3_nodes[be]
    draw_building(ax_upper, bx + offset_x, by, w=1.8, h=1.2, color='#BDC3C7')

# Physics annotations — larger, positioned clearly
ax_upper.text(cx - 6, 14, r'$\Delta$P (pressure drop)',
              fontsize=10, color=COLORS['orange'], fontweight='bold')
ax_upper.text(cx + 3, 14, r'$\tau$ (transport delay)',
              fontsize=10, color=COLORS['teal'], fontweight='bold')
ax_upper.text(cx - 1, 10, r'T$_{out}$ < T$_{in}$ (propagation)',
              fontsize=10, color=COLORS['supply'], fontweight='bold')

# ─── INSET: PWL vs Quadratic ─────────────────────────────────────
inset_left = cx - 11
inset_bottom = 20
inset_w = 22
inset_h = 12

ax_upper.add_patch(FancyBboxPatch(
    (inset_left, inset_bottom), inset_w, inset_h,
    boxstyle='round,pad=0.5', facecolor='#FDFEFE',
    edgecolor=COLORS['gray'], lw=1.5, zorder=6))

ax_upper.text(cx, inset_bottom + inset_h - 1.5,
              r'$\Delta$P approximation:', ha='center',
              fontsize=9, color=COLORS['dark'], zorder=7, fontweight='bold')

# PWL (staircase) — L3⁺
pwl_x = np.array([0, 1, 1, 2, 2, 3, 3, 4, 4, 5]) * 1.8 + inset_left + 2
pwl_y = np.array([0, 0, 1.5, 1.5, 3, 3, 5, 5, 6.5, 6.5]) * 0.7 + inset_bottom + 2
ax_upper.plot(pwl_x, pwl_y, color=COLORS['blue'], lw=2.5, zorder=7)
ax_upper.text(inset_left + 13, inset_bottom + 3.5, r'L3$^+$ (MILP/PWL)',
              fontsize=8, color=COLORS['blue'], fontweight='bold', zorder=7)

# Quadratic curve — L3ᴺᴸ
quad_x = np.linspace(inset_left + 2, inset_left + 11, 50)
quad_y = 0.08 * (quad_x - inset_left - 2)**2 + inset_bottom + 2
ax_upper.plot(quad_x, quad_y, color=COLORS['teal'], lw=2.5, ls='--', zorder=7)
ax_upper.text(inset_left + 13, inset_bottom + 7, r'L3$^{NL}$ (MIQCP/Quad)',
              fontsize=8, color=COLORS['teal'], fontweight='bold', zorder=7)

ax_upper.text(cx, inset_bottom - 2, r'$\Delta \leq$ 0.35% $\rightarrow$ MILP validated $\checkmark$',
              ha='center', fontsize=10, color=COLORS['green'],
              fontweight='bold', zorder=7)

# ═══════════════════════════════════════════════════════════════════
# ARROWS BETWEEN DIAGRAMS
# ═══════════════════════════════════════════════════════════════════
arrow_y = 54

transitions = [
    (col_centers[0] + 9, col_centers[1] - 9, '+Losses\n+Topology',
     COLORS['orange']),
    (col_centers[1] + 9, col_centers[2] - 9, '+Spatial\nresolution',
     COLORS['blue']),
    (col_centers[2] + 9, col_centers[3] - 9,
     r'+$\Delta$P  +T(x)  +$\tau$', COLORS['teal']),
]

for x_start, x_end, label, color in transitions:
    ax_upper.annotate('', xy=(x_end, arrow_y), xytext=(x_start, arrow_y),
                      arrowprops=dict(arrowstyle='->', lw=3, color=color))
    ax_upper.text((x_start + x_end) / 2, arrow_y + 2, label,
                  ha='center', va='bottom', fontsize=10, color=color,
                  fontweight='bold')

# ═══════════════════════════════════════════════════════════════════
# LOWER LEFT: Waterfall Chart
# ═══════════════════════════════════════════════════════════════════
ax_lower.set_facecolor('white')

categories = ['L1\n(Baseline)', 'L1$\\rightarrow$L2\n(+Losses)',
              'L2$\\rightarrow$L3\n(+Spatial)',
              'L3$\\rightarrow$L3$^+$\n(+Ext.Phys.)',
              'L3$^+$$\\rightarrow$L3$^{NL}$\n(Lineariz.)']
values = [0, 12, 2.4, 0.11, 0.35]
colors_bar = [COLORS['gray'], COLORS['orange'], COLORS['blue'],
              COLORS['teal'], COLORS['gray']]

cumulative = np.cumsum(values)
bottoms = cumulative - np.array(values)

bars = ax_lower.bar(range(len(categories)), values, bottom=bottoms,
                    color=colors_bar, edgecolor='white', lw=2, width=0.6,
                    zorder=3)

for i, (val, bot) in enumerate(zip(values, bottoms)):
    if val >= 2:
        ax_lower.text(i, bot + val / 2, f'+{val}%', ha='center',
                     va='center', fontsize=12, fontweight='bold',
                     color='white')
    elif val > 0:
        ax_lower.text(i, bot + val + 0.3, f'+{val}%', ha='center',
                     va='bottom', fontsize=10, fontweight='bold',
                     color=colors_bar[i])

for i in range(len(categories) - 1):
    ax_lower.plot([i + 0.3, i + 0.7], [cumulative[i], cumulative[i]],
                 color=COLORS['dark'], lw=1, ls=':', alpha=0.5)

ax_lower.annotate(r'63 t CO$_2$/yr' + '\nhidden by L1!',
                  xy=(1, 12.5), xytext=(2.2, 15.5),
                  fontsize=10, color=COLORS['supply'], fontweight='bold',
                  arrowprops=dict(arrowstyle='->', color=COLORS['supply'],
                                 lw=2))

ax_lower.set_xticks(range(len(categories)))
ax_lower.set_xticklabels(categories, fontsize=10)
ax_lower.set_ylabel('Cost deviation from L1 [%]', fontsize=11)
ax_lower.set_ylim(0, 18)
ax_lower.set_title('Effect Hierarchy (full scale)', fontsize=11,
                   fontweight='bold', pad=10)
ax_lower.spines['top'].set_visible(False)
ax_lower.spines['right'].set_visible(False)
ax_lower.yaxis.grid(True, alpha=0.3)

# ═══════════════════════════════════════════════════════════════════
# LOWER RIGHT: Zoom on small effects
# ═══════════════════════════════════════════════════════════════════
ax_zoom.set_facecolor('#FAFAFA')

zoom_categories = ['L2$\\rightarrow$L3\n(Spatial)',
                   'L3$\\rightarrow$L3$^+$\n(Ext.Phys.)',
                   'L3$^+$$\\rightarrow$L3$^{NL}$\n(Lineariz.)']
zoom_values = [2.4, 0.11, 0.35]
zoom_colors = [COLORS['blue'], COLORS['teal'], COLORS['gray']]

ax_zoom.bar(range(len(zoom_categories)), zoom_values,
            color=zoom_colors, edgecolor='white', lw=2, width=0.5, zorder=3)

for i, val in enumerate(zoom_values):
    ax_zoom.text(i, val + 0.05, f'{val}%', ha='center', va='bottom',
                fontsize=11, fontweight='bold', color=zoom_colors[i])

ax_zoom.set_xticks(range(len(zoom_categories)))
ax_zoom.set_xticklabels(zoom_categories, fontsize=10)
ax_zoom.set_ylabel('Cost deviation [%]', fontsize=11)
ax_zoom.set_ylim(0, 3.0)
ax_zoom.set_title('Zoom: Small effects', fontsize=11,
                  fontweight='bold', pad=10)
ax_zoom.spines['top'].set_visible(False)
ax_zoom.spines['right'].set_visible(False)
ax_zoom.yaxis.grid(True, alpha=0.3)

ax_zoom.axhline(y=0.35, color=COLORS['green'], ls='--', lw=1.5, alpha=0.7)
ax_zoom.text(1.5, 0.55, 'MILP adequate\nfor planning', ha='center',
             fontsize=9, color=COLORS['green'], fontweight='bold')

# ─── Key Finding Banner ───────────────────────────────────────────
fig.text(0.5, 0.38,
         r'Physics inclusion (12%)  $\gg$  Spatial refinement (2.4%)  $\gg$  Linearization ($\leq$0.35%)',
         ha='center', va='center', fontsize=14, fontweight='bold',
         color=COLORS['dark'],
         bbox=dict(boxstyle='round,pad=0.5', facecolor='#FEF9E7',
                  edgecolor=COLORS['orange'], lw=2))

# ─── SAVE ─────────────────────────────────────────────────────────
plt.savefig('graphical_abstract_v3.pdf', dpi=300, bbox_inches='tight',
            facecolor='white')
plt.savefig('graphical_abstract_v3.tiff', dpi=300, bbox_inches='tight',
            facecolor='white')
plt.savefig('graphical_abstract_v3.png', dpi=300, bbox_inches='tight',
            facecolor='white')

print("Saved: graphical_abstract_v3.pdf / .tiff / .png")