"""Base class for forecast generators used in MPC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any
from calion.utils.timeseries import TimeSeriesTable


class ForecastGenerator(ABC):
    """Base class for forecast generation methods.

    Forecast generators create predicted time series data from a given
    time index forward. Different implementations represent different
    forecasting approaches (persistence, perfect+noise, historical analog, etc.).
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize forecast generator.

        Parameters
        ----------
        config:
            Full configuration dictionary (may contain method-specific parameters)
        """
        self.config = config

    @abstractmethod
    def generate_forecast(
        self,
        historical_data: TimeSeriesTable,
        current_index: int,
        horizon_hours: float,
        dt_h: float,
    ) -> TimeSeriesTable:
        """Generate forecast starting from current_index.

        Parameters
        ----------
        historical_data:
            Full historical time series (contains "true" future data for perfect forecast)
        current_index:
            Current time index (start of forecast window)
        horizon_hours:
            Forecast horizon in hours
        dt_h:
            Time step in hours

        Returns
        -------
        Forecasted time series for the next horizon_hours
        """
        pass

    @abstractmethod
    def get_method_name(self) -> str:
        """Return human-readable method name for logging.

        Returns
        -------
        Method name (e.g., "Persistence", "Perfect + Noise 10%")
        """
        pass
