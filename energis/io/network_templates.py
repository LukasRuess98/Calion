"""Network Templates and Auto-Layout for Network Designer.

Provides pre-defined network templates and automatic component arrangement.
"""

from __future__ import annotations

from typing import Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)


# Pre-defined network templates
NETWORK_TEMPLATES = {
    'simple_hp_storage': {
        'name': 'Einfaches Wärmepumpen-System',
        'description': '1 Wärmepumpe + 1 Speicher + 1 Verbraucher',
        'components': [
            {
                'type': 'heat_pump',
                'id': 'WP1',
                'x': 150,
                'y': 300,
                'status': 'investment',
                'properties': {'capacity_mw': 15.0, 'cop': 3.8}
            },
            {
                'type': 'storage',
                'id': 'Speicher1',
                'x': 450,
                'y': 300,
                'status': 'investment',
                'properties': {'capacity_mwh': 75.0, 'efficiency': 0.98}
            },
            {
                'type': 'consumer',
                'id': 'Verbraucher',
                'x': 750,
                'y': 300,
                'status': 'pending',
                'properties': {'demand_mw': 25.0}
            },
        ],
        'connections': [
            {'from': 'WP1', 'to': 'Speicher1'},
            {'from': 'Speicher1', 'to': 'Verbraucher'},
        ]
    },

    'brownfield_expansion': {
        'name': 'Bestandsausbau',
        'description': 'Bestehender Kessel + neue WP + Speicher',
        'components': [
            {
                'type': 'boiler',
                'id': 'Kessel_Bestand',
                'x': 150,
                'y': 150,
                'status': 'existing',
                'properties': {'capacity_mw': 20.0, 'efficiency': 0.95}
            },
            {
                'type': 'heat_pump',
                'id': 'WP_Neu',
                'x': 150,
                'y': 400,
                'status': 'investment',
                'properties': {'capacity_mw': 15.0, 'cop': 3.8}
            },
            {
                'type': 'storage',
                'id': 'Speicher_Neu',
                'x': 450,
                'y': 275,
                'status': 'investment',
                'properties': {'capacity_mwh': 100.0, 'efficiency': 0.98}
            },
            {
                'type': 'consumer',
                'id': 'Waermenetz',
                'x': 750,
                'y': 275,
                'status': 'pending',
                'properties': {'demand_mw': 35.0}
            },
        ],
        'connections': [
            {'from': 'Kessel_Bestand', 'to': 'Speicher_Neu'},
            {'from': 'WP_Neu', 'to': 'Speicher_Neu'},
            {'from': 'Speicher_Neu', 'to': 'Waermenetz'},
        ]
    },

    'multi_source': {
        'name': 'Multi-Source System',
        'description': '2 WP + 1 Kessel + Speicher + Verbraucher',
        'components': [
            {
                'type': 'heat_pump',
                'id': 'WP1',
                'x': 100,
                'y': 200,
                'status': 'investment',
                'properties': {'capacity_mw': 10.0, 'cop': 3.5}
            },
            {
                'type': 'heat_pump',
                'id': 'WP2',
                'x': 100,
                'y': 400,
                'status': 'investment',
                'properties': {'capacity_mw': 10.0, 'cop': 3.5}
            },
            {
                'type': 'boiler',
                'id': 'Kessel1',
                'x': 100,
                'y': 100,
                'status': 'existing',
                'properties': {'capacity_mw': 15.0, 'efficiency': 0.95}
            },
            {
                'type': 'storage',
                'id': 'Speicher',
                'x': 400,
                'y': 250,
                'status': 'investment',
                'properties': {'capacity_mwh': 120.0, 'efficiency': 0.98}
            },
            {
                'type': 'consumer',
                'id': 'Netz',
                'x': 700,
                'y': 250,
                'status': 'pending',
                'properties': {'demand_mw': 35.0}
            },
        ],
        'connections': [
            {'from': 'WP1', 'to': 'Speicher'},
            {'from': 'WP2', 'to': 'Speicher'},
            {'from': 'Kessel1', 'to': 'Speicher'},
            {'from': 'Speicher', 'to': 'Netz'},
        ]
    },

    'distributed': {
        'name': 'Verteiltes Netzwerk',
        'description': 'Mehrere Erzeuger und Verbraucher',
        'components': [
            {
                'type': 'heat_pump',
                'id': 'WP_Nord',
                'x': 300,
                'y': 100,
                'status': 'investment',
                'properties': {'capacity_mw': 8.0, 'cop': 3.5}
            },
            {
                'type': 'heat_pump',
                'id': 'WP_Sued',
                'x': 300,
                'y': 500,
                'status': 'investment',
                'properties': {'capacity_mw': 8.0, 'cop': 3.5}
            },
            {
                'type': 'storage',
                'id': 'Speicher_Zentral',
                'x': 500,
                'y': 300,
                'status': 'investment',
                'properties': {'capacity_mwh': 80.0, 'efficiency': 0.98}
            },
            {
                'type': 'consumer',
                'id': 'Verbraucher_West',
                'x': 700,
                'y': 200,
                'status': 'pending',
                'properties': {'demand_mw': 10.0}
            },
            {
                'type': 'consumer',
                'id': 'Verbraucher_Ost',
                'x': 700,
                'y': 400,
                'status': 'pending',
                'properties': {'demand_mw': 10.0}
            },
        ],
        'connections': [
            {'from': 'WP_Nord', 'to': 'Speicher_Zentral'},
            {'from': 'WP_Sued', 'to': 'Speicher_Zentral'},
            {'from': 'Speicher_Zentral', 'to': 'Verbraucher_West'},
            {'from': 'Speicher_Zentral', 'to': 'Verbraucher_Ost'},
        ]
    },
}


def get_template(template_name: str) -> Dict[str, Any]:
    """Get network template by name."""
    if template_name not in NETWORK_TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}. Available: {list(NETWORK_TEMPLATES.keys())}")
    return NETWORK_TEMPLATES[template_name].copy()


def list_templates() -> List[Dict[str, str]]:
    """List all available templates."""
    return [
        {
            'id': key,
            'name': template['name'],
            'description': template['description']
        }
        for key, template in NETWORK_TEMPLATES.items()
    ]


class AutoLayout:
    """Automatic layout algorithms for network components."""

    @staticmethod
    def grid_layout(components: List, canvas_width: int = 800, canvas_height: int = 600) -> List:
        """Arrange components in a grid pattern."""
        if not components:
            return components

        n = len(components)
        cols = int(n ** 0.5) + 1
        rows = (n + cols - 1) // cols

        margin_x = 100
        margin_y = 100
        spacing_x = (canvas_width - 2 * margin_x) / (cols - 1) if cols > 1 else 0
        spacing_y = (canvas_height - 2 * margin_y) / (rows - 1) if rows > 1 else 0

        for i, comp in enumerate(components):
            row = i // cols
            col = i % cols
            comp.x = margin_x + col * spacing_x
            comp.y = margin_y + row * spacing_y

        return components

    @staticmethod
    def hierarchical_layout(
        components: List,
        connections: List,
        canvas_width: int = 800,
        canvas_height: int = 600
    ) -> List:
        """Arrange components hierarchically (left to right: producers -> storage -> consumers)."""

        # Categorize components
        producers = []
        storage = []
        consumers = []
        other = []

        for comp in components:
            if comp.component_type in ['heat_pump', 'boiler']:
                producers.append(comp)
            elif comp.component_type == 'storage':
                storage.append(comp)
            elif comp.component_type == 'consumer':
                consumers.append(comp)
            else:
                other.append(comp)

        # Layout columns
        margin_x = 100
        margin_y = 100
        col_width = (canvas_width - 2 * margin_x) / 3

        def position_column(items, col_index):
            x = margin_x + col_index * col_width
            if not items:
                return

            spacing_y = (canvas_height - 2 * margin_y) / (len(items) + 1)

            for i, item in enumerate(items):
                item.x = x
                item.y = margin_y + (i + 1) * spacing_y

        # Position columns
        position_column(producers, 0)
        position_column(storage, 1)
        position_column(consumers, 2)

        # Position "other" in middle if any
        if other:
            position_column(other, 1)

        return components

    @staticmethod
    def circular_layout(components: List, canvas_width: int = 800, canvas_height: int = 600) -> List:
        """Arrange components in a circle."""
        if not components:
            return components

        import math

        center_x = canvas_width / 2
        center_y = canvas_height / 2
        radius = min(canvas_width, canvas_height) / 3

        n = len(components)
        for i, comp in enumerate(components):
            angle = 2 * math.pi * i / n - math.pi / 2  # Start from top
            comp.x = center_x + radius * math.cos(angle)
            comp.y = center_y + radius * math.sin(angle)

        return components

    @staticmethod
    def force_directed_layout(
        components: List,
        connections: List,
        canvas_width: int = 800,
        canvas_height: int = 600,
        iterations: int = 50
    ) -> List:
        """Simple force-directed layout (spring model)."""
        if len(components) < 2:
            return components

        import math

        # Initialize positions if not set
        for comp in components:
            if comp.x == 0 and comp.y == 0:
                import random
                comp.x = random.uniform(100, canvas_width - 100)
                comp.y = random.uniform(100, canvas_height - 100)

        # Build adjacency list
        adj = {comp.component_id: [] for comp in components}
        for conn in connections:
            adj[conn.from_id].append(conn.to_id)
            adj[conn.to_id].append(conn.from_id)

        # Force-directed algorithm
        k = 50  # Ideal spring length
        for _ in range(iterations):
            forces = {comp.component_id: {'x': 0, 'y': 0} for comp in components}

            # Repulsive forces (all pairs)
            for i, comp1 in enumerate(components):
                for comp2 in components[i+1:]:
                    dx = comp2.x - comp1.x
                    dy = comp2.y - comp1.y
                    dist = math.sqrt(dx*dx + dy*dy) + 0.01

                    # Repulsion ~ 1/dist
                    force = k * k / dist
                    fx = force * dx / dist
                    fy = force * dy / dist

                    forces[comp1.component_id]['x'] -= fx
                    forces[comp1.component_id]['y'] -= fy
                    forces[comp2.component_id]['x'] += fx
                    forces[comp2.component_id]['y'] += fy

            # Attractive forces (connected pairs)
            for conn in connections:
                comp1 = next((c for c in components if c.component_id == conn.from_id), None)
                comp2 = next((c for c in components if c.component_id == conn.to_id), None)

                if comp1 and comp2:
                    dx = comp2.x - comp1.x
                    dy = comp2.y - comp1.y
                    dist = math.sqrt(dx*dx + dy*dy) + 0.01

                    # Attraction ~ dist
                    force = (dist - k) / k
                    fx = force * dx
                    fy = force * dy

                    forces[comp1.component_id]['x'] += fx
                    forces[comp1.component_id]['y'] += fy
                    forces[comp2.component_id]['x'] -= fx
                    forces[comp2.component_id]['y'] -= fy

            # Apply forces
            for comp in components:
                comp.x += forces[comp.component_id]['x'] * 0.1  # Damping
                comp.y += forces[comp.component_id]['y'] * 0.1

                # Keep in bounds
                comp.x = max(50, min(canvas_width - 50, comp.x))
                comp.y = max(50, min(canvas_height - 50, comp.y))

        return components


def snap_to_grid(components: List, grid_size: int = 50) -> List:
    """Snap all component coordinates to grid."""
    for comp in components:
        comp.x = round(comp.x / grid_size) * grid_size
        comp.y = round(comp.y / grid_size) * grid_size
    return components


def optimize_layout(
    components: List,
    connections: List,
    method: str = 'hierarchical',
    canvas_width: int = 800,
    canvas_height: int = 600,
    **kwargs
) -> List:
    """Apply automatic layout algorithm.

    Args:
        components: List of NetworkComponent objects
        connections: List of NetworkConnection objects
        method: Layout method ('grid', 'hierarchical', 'circular', 'force')
        canvas_width: Canvas width in pixels
        canvas_height: Canvas height in pixels
        **kwargs: Additional arguments for specific layouts

    Returns:
        Updated components list
    """
    layout = AutoLayout()

    if method == 'grid':
        return layout.grid_layout(components, canvas_width, canvas_height)
    elif method == 'hierarchical':
        return layout.hierarchical_layout(components, connections, canvas_width, canvas_height)
    elif method == 'circular':
        return layout.circular_layout(components, canvas_width, canvas_height)
    elif method == 'force':
        iterations = kwargs.get('iterations', 50)
        return layout.force_directed_layout(components, connections, canvas_width, canvas_height, iterations)
    else:
        raise ValueError(f"Unknown layout method: {method}")
