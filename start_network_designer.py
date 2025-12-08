#!/usr/bin/env python
"""Start the Network Designer Dashboard.

Usage:
    python start_network_designer.py

Then open browser at http://localhost:5006
"""

import panel as pn
from energis.io.network_designer import create_network_designer

# Enable Panel extensions
pn.extension('plotly')

# Create designer instance
designer = create_network_designer()

# Create dashboard
dashboard = designer.create_dashboard()

# Serve
if __name__ == '__main__':
    print("=" * 60)
    print("🗺️  EnerGIS Network Designer")
    print("=" * 60)
    print("\n✅ Starting dashboard server...")
    print("📍 Open browser at: http://localhost:5006")
    print("\nPress Ctrl+C to stop\n")

    dashboard.show(port=5006, open=True)
