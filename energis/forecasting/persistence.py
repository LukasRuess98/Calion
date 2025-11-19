"""Persistence forecast: naive baseline assuming tomorrow = today."""

from __future__ import annotations

from energis.forecasting.base import ForecastGenerator
from energis.utils.timeseries import TimeSeriesTable
from energis.run import orchestrator


class PersistenceForecast(ForecastGenerator):
    """Naive persistence forecast: copy current pattern into future.

    This is the simplest possible forecast method that assumes the
    future will exactly repeat the recent past. It serves as a baseline
    to demonstrate the value of more sophisticated forecasting approaches.

    The forecast repeats the last 24 hours of data (or the available pattern)
    to fill the forecast horizon.
    """

    def generate_forecast(
        self,
        historical_data: TimeSeriesTable,
        current_index: int,
        horizon_hours: float,
        dt_h: float,
    ) -> TimeSeriesTable:
        """Generate persistence forecast by repeating recent pattern.

        Parameters
        ----------
        historical_data:
            Full historical time series
        current_index:
            Current time index
        horizon_hours:
            Forecast horizon in hours
        dt_h:
            Time step in hours

        Returns
        -------
        Forecasted time series repeating recent pattern
        """
        # Calculate number of steps in forecast
        horizon_steps = int(horizon_hours / dt_h)

        # Use 24h pattern (or less if not available)
        pattern_hours = 24.0
        pattern_steps = int(pattern_hours / dt_h)

        # Extract pattern from history (last pattern_steps before current_index)
        pattern_start = max(0, current_index - pattern_steps)
        pattern_end = current_index

        if pattern_end <= pattern_start:
            # No history available, use first available data
            pattern_start = 0
            pattern_end = min(pattern_steps, len(historical_data))

        # Build forecast by repeating pattern
        forecast_indices = []
        actual_pattern_length = pattern_end - pattern_start

        if actual_pattern_length == 0:
            # Fallback: use current index repeatedly
            forecast_indices = [min(current_index, len(historical_data) - 1)] * horizon_steps
        else:
            for i in range(horizon_steps):
                # Repeat pattern cyclically
                pattern_idx = pattern_start + (i % actual_pattern_length)
                # Ensure we don't exceed historical data bounds
                pattern_idx = min(pattern_idx, len(historical_data) - 1)
                forecast_indices.append(pattern_idx)

        # Slice and return forecast
        return orchestrator._slice_table(historical_data, forecast_indices)

    def get_method_name(self) -> str:
        """Return method name.

        Returns
        -------
        Method name
        """
        return "Persistence (Naive)"
