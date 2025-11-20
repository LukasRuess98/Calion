"""Perfect forecast with additive Gaussian noise."""

from __future__ import annotations

import numpy as np
from typing import Dict, Any

from energis.forecasting.base import ForecastGenerator
from energis.utils.timeseries import TimeSeriesTable
from energis.run import orchestrator


class PerfectNoiseForecast(ForecastGenerator):
    """Perfect forecast with additive Gaussian noise.

    This forecast uses the true future data but adds controlled noise
    to simulate realistic forecast errors. This allows studying the
    value of forecast accuracy by varying the noise level.

    Noise is added to:
    - Demand: Gaussian noise proportional to mean demand
    - Prices: Lognormal noise (to keep prices positive)
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize with noise parameters.

        Parameters
        ----------
        config:
            Configuration dictionary containing:
            - scenario.mpc.noise_std_dev: Standard deviation (default: 0.10 = 10%)
            - scenario.mpc.random_seed: Random seed for reproducibility (default: 42)
        """
        super().__init__(config)

        mpc_cfg = config.get("scenario", {}).get("mpc", {})
        self.std_dev = float(mpc_cfg.get("noise_std_dev", 0.10))
        seed = mpc_cfg.get("random_seed", 42)
        self.rng = np.random.RandomState(seed)

    def generate_forecast(
        self,
        historical_data: TimeSeriesTable,
        current_index: int,
        horizon_hours: float,
        dt_h: float,
    ) -> TimeSeriesTable:
        """Generate perfect forecast with noise.

        Parameters
        ----------
        historical_data:
            Full historical time series (contains true future)
        current_index:
            Current time index
        horizon_hours:
            Forecast horizon in hours
        dt_h:
            Time step in hours

        Returns
        -------
        Forecasted time series (perfect + noise)
        """
        # Calculate horizon in steps
        horizon_steps = int(horizon_hours / dt_h)
        end_index = min(current_index + horizon_steps, len(historical_data))

        # Get perfect forecast (true future data)
        indices = list(range(current_index, end_index))
        forecast = orchestrator._slice_table(historical_data, indices)

        # Add noise to demand series
        if "demand_mw" in forecast.series:
            demand = np.array(forecast.series["demand_mw"])
            if len(demand) > 0 and demand.mean() > 0:
                # Additive Gaussian noise scaled by mean
                noise = self.rng.normal(0, self.std_dev * demand.mean(), len(demand))
                noisy_demand = demand + noise
                # Clip to ensure non-negative
                forecast.series["demand_mw"] = noisy_demand.clip(min=0).tolist()

        # Add noise to electricity price (lognormal to keep positive)
        if "price_elec_eur_mwh" in forecast.series:
            price = np.array(forecast.series["price_elec_eur_mwh"])
            if len(price) > 0:
                # Multiplicative lognormal noise
                noise_factor = self.rng.lognormal(0, self.std_dev, len(price))
                noisy_price = price * noise_factor
                forecast.series["price_elec_eur_mwh"] = noisy_price.clip(min=0).tolist()

        # Add noise to gas price if present
        if "price_gas_eur_mwh" in forecast.series:
            price = np.array(forecast.series["price_gas_eur_mwh"])
            if len(price) > 0:
                noise_factor = self.rng.lognormal(0, self.std_dev, len(price))
                noisy_price = price * noise_factor
                forecast.series["price_gas_eur_mwh"] = noisy_price.clip(min=0).tolist()

        return forecast

    def get_method_name(self) -> str:
        """Return method name with noise level.

        Returns
        -------
        Method name including noise percentage
        """
        return f"Perfect + Noise (σ={self.std_dev:.0%})"
