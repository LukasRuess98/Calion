# Add Interactive Panel Dashboard for EnerGIS Optimization Results

## 🎛️ Summary

This PR adds a comprehensive **interactive dashboard** for analyzing EnerGIS optimization results using Panel and Plotly. The dashboard provides real-time visualization and exploration capabilities for PF, RH, and MPC workflows.

## 🎯 Features

### **5 Interactive Tabs:**

1. **📊 Overview Tab**
   - KPI cards with key metrics (costs, CAPEX, demand, peak)
   - System summary with active components
   - Quick demand profile visualization

2. **📈 Timeseries Tab** (HIGHLY INTERACTIVE)
   - Multi-component selection (checkboxes for HP, generators, etc.)
   - Dynamic time range slider (hour to year)
   - Multiple plot types (Stacked Area, Lines, Bars)
   - Three synchronized plots:
     - Heat balance (demand + generation)
     - Electric balance (grid flows + consumption)
     - Storage operation (SOC + charge/discharge)

3. **💰 Costs Tab**
   - Interactive cost breakdown chart (top 10)
   - Sortable/filterable data table
   - Formatted values (EUR with separators)
   - Percentage progress bars
   - Top-3 summary

4. **🏭 Design Tab**
   - Capacity visualization (heat pumps + storage)
   - Design data table
   - JSON export of complete design

5. **🔀 Comparison Tab** (PF + RH/MPC only)
   - Side-by-side cost comparison
   - Optimality gap calculation
   - Automatic interpretation (Excellent/Good/High)

### **Interactive Capabilities:**
- 🔍 Zoom & Pan on all plots
- ℹ️ Hover tooltips with detailed values
- 📸 Screenshot download
- 🔄 Reset view
- 📊 Legend click to toggle series
- 🔀 Sortable tables
- ✅ Multi-select components

## 📦 New Files

### 1. `energis/io/dashboard.py` (1,350+ lines)
Complete dashboard implementation:
- `create_dashboard(workflow, title)`: Main entry point
- `EnerGISDashboard` class with all tab generators
- Plotly-based interactive visualizations
- Responsive design for all screen sizes

### 2. `notebooks/interactive_dashboard.ipynb`
Demo notebook with:
- Step-by-step tutorial
- Dependency checks
- Usage examples (Jupyter + webapp)
- Export instructions

### 3. `docs/DASHBOARD.md` (370+ lines)
Comprehensive documentation:
- ASCII mockups for all tabs
- API reference
- Deployment guides (Docker, Heroku, Cloud)
- Troubleshooting section
- Customization examples
- Best practices

## 🚀 Usage

### Quick Start (3 lines):
```python
from energis.run import rolling_horizon as rh
from energis.io.dashboard import create_dashboard

workflow = rh.run_workflow(CONFIG_PATHS)
dashboard = create_dashboard(workflow)
dashboard  # Display in Jupyter
```

### As Webapp:
```bash
pip install panel holoviews bokeh plotly
panel serve notebooks/interactive_dashboard.ipynb --show
```

## 📋 Testing Instructions

### 1. Install dependencies:
```bash
pip install panel holoviews bokeh plotly
```

### 2. Test in Jupyter:
```bash
jupyter notebook notebooks/interactive_dashboard.ipynb
# Run all cells
```

### 3. Test as webapp:
```bash
panel serve notebooks/interactive_dashboard.ipynb --show
# Opens browser at http://localhost:5006
```

### 4. Integration test in existing notebook:
Add to `scenario_studio.ipynb` or `runner.ipynb`:
```python
from energis.io.dashboard import create_dashboard
dashboard = create_dashboard(workflow)
dashboard
```

## 🔬 What to Test

- [ ] Dashboard loads without errors
- [ ] All 5 tabs are visible and functional
- [ ] Component selection in Timeseries tab updates plots
- [ ] Time range slider changes displayed data
- [ ] Cost table is sortable
- [ ] KPI cards show correct values
- [ ] Comparison tab appears when PF+RH results available
- [ ] Plots are interactive (zoom, pan, hover)
- [ ] Webapp mode works (`panel serve ...`)

## 📊 Visual Preview

### Tab Structure:
```
┌─────────────────────────────────────────────────────┐
│  EnerGIS Interactive Dashboard 🔥                   │
│  ┌────┬────────┬────────┬─────────┬──────────┐     │
│  │ 📊 │  📈    │  💰    │  🏭     │   🔀     │     │
│  │Over│Times.  │ Costs  │ Design  │ Compare  │     │
│  └────┴────────┴────────┴─────────┴──────────┘     │
│                                                      │
│  [Interactive content based on selected tab]        │
│                                                      │
└─────────────────────────────────────────────────────┘
```

See `docs/DASHBOARD.md` for detailed ASCII mockups of all tabs.

## 🎨 Technology Stack

- **Panel**: Dashboard framework
- **Plotly**: Interactive plots
- **Holoviews**: High-level plotting
- **Bokeh**: Backend for Panel

## 🔄 Integration with Existing Code

✅ **Zero Breaking Changes**:
- All existing code continues to work
- Dashboard is opt-in via import
- No changes to existing notebooks required

✅ **Compatible with Current Exports**:
- Works alongside existing plot exports
- Can read data from `workflow` object
- Complements static PDF/SVG exports

## 🌐 Deployment Options

Dashboard can be deployed as:
1. **Jupyter Extension** (local development)
2. **Standalone Webapp** (via `panel serve`)
3. **Docker Container** (see docs/DASHBOARD.md)
4. **Cloud Services** (Heroku, AWS, Azure, GCP)

## 📚 Documentation

Complete documentation in `docs/DASHBOARD.md`:
- Installation guide
- API reference
- Deployment instructions
- Customization examples
- Troubleshooting
- Best practices

## 🎓 Use Cases

### For Dissertation:
- Interactive presentations
- Live demos for committee
- Exploratory analysis
- Quick scenario comparisons

### For Stakeholders:
- Webapp for external access
- No Python knowledge required
- Intuitive interface

### For Research:
- Fast debugging of optimizations
- Visual validation of results
- Component comparisons

## 🔮 Future Enhancements

Potential additions (not in this PR):
- Multi-scenario comparison (side-by-side)
- CSV download from dashboard
- Automatic PDF report generation
- Dark mode theme
- Real-time updates for MPC
- Authentication for webapp deployment

## ✅ Checklist

- [x] Code follows project style
- [x] All new files documented
- [x] Demo notebook included
- [x] Comprehensive documentation
- [x] No breaking changes
- [x] Works with existing workflows
- [x] Tested in Jupyter environment
- [x] Webapp mode tested

## 📝 Related Issues

Addresses feature request for interactive visualizations in notebooks.

## 💡 Notes

**Dependencies**: This feature requires `panel`, `holoviews`, `bokeh`, and `plotly`. These are optional dependencies and do not affect existing functionality if not installed.

**Performance**: For large datasets (>100k timesteps), consider data aggregation or using the time range slider to view subsets.

**Browser Compatibility**: Tested in Chrome, Firefox, Safari. Webapp mode requires WebSocket support.

---

**Ready for review!** 🚀

Please test the dashboard with your own optimization results and provide feedback on:
- UI/UX improvements
- Additional plot types needed
- Performance issues
- Documentation clarity
