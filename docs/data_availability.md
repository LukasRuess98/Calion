# Data Availability Statement

## Synthetic Example Data

This repository includes a synthetic example dataset for demonstration and testing purposes.

### Dataset Description

- **Location:** `data/` directory
- **Temporal coverage:** Hourly time steps
- **Reference year:** 2023
- **Purpose:** Reproducible examples and unit testing

### Columns

| Column | Unit | Description |
|--------|------|-------------|
| Datum | datetime | Hourly timestamps |
| Day_Ahead_Price | €/MWh | Electricity spot price |
| Wärmebedarf_MW | MW | Thermal heat demand |
| CO2_consumption_based | kg/MWh | Grid electricity emission factor |
| WRG*_Q MW | MW | Available waste heat |
| WRG*_T °C | °C | Waste heat source temperature |

### Generation Method

Data is generated using deterministic formulae to ensure reproducibility:

```python
# Price: daily sinusoidal pattern
price = 100 + 50 * sin(2π × hour / 24)

# Heat demand: seasonal + daily pattern
demand = 100 + 30 * cos(2π × day / 365) + 20 * cos(2π × hour / 24)

# CO2 intensity: inverse correlation with renewables
co2 = 400 + 100 * sin(2π × hour / 24 + π)
```

The synthetic data does **not** contain customer or operational data. Values are scaled to work with default EnerGIS component capacities.

## Real-World Case Study Data

The Stadtbach case study in the publication uses operational data from a German district heating network. Due to confidentiality agreements, this data cannot be published openly.

**For access to real-world data:**
- Contact the corresponding author
- Data may be available under a data sharing agreement

## Anonymization Approach

- Synthetic data uses procedurally generated values (sine/cosine curves)
- No measurements or confidential parameters from real sites
- Column names mirror the configuration defaults for compatibility

## License

The synthetic dataset is released under the MIT License.

You may copy, adapt, and redistribute the files. Attribution to this repository is appreciated.
