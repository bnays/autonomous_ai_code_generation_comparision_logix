import math
import json
from typing import List, Dict, Any, Union

import numpy as np


def calculate_reorder_point(
    daily_forecast: List[Dict[str, Any]],
    lead_time_days: Union[int, float],
    service_level_z: Union[int, float] = 1.65
) -> Dict[str, Any]:
    """
    Calculate reorder point using forecasted daily demand.

    Parameters:
        daily_forecast: List of dicts like [{"date": "YYYY-MM-DD", "predicted_sales": int}, ...]
        lead_time_days: Lead time in days (must be positive)
        service_level_z: Z-score for desired service level (default 1.65 ~ 95%)

    Returns:
        On success:
            {
                "average_daily_demand": float,
                "safety_stock": int,
                "reorder_point": int
            }
        On error:
            { "error": "message" }
    """
    try:
        # Validate daily_forecast
        if not isinstance(daily_forecast, list) or len(daily_forecast) == 0:
            return {"error": "daily_forecast must be a non-empty list"}

        # Extract and validate predicted_sales values
        sales_values = []
        for i, rec in enumerate(daily_forecast):
            if not isinstance(rec, dict) or "predicted_sales" not in rec:
                return {"error": f"Item at index {i} is invalid or missing 'predicted_sales'"}
            val = rec["predicted_sales"]
            try:
                val = float(val)
            except (TypeError, ValueError):
                return {"error": f"'predicted_sales' at index {i} must be numeric"}
            sales_values.append(val)

        if len(sales_values) == 0:
            return {"error": "No valid 'predicted_sales' values found in daily_forecast"}

        # Validate lead_time_days
        try:
            lead_time = float(lead_time_days)
        except (TypeError, ValueError):
            return {"error": "lead_time_days must be a positive number"}
        if not math.isfinite(lead_time) or lead_time <= 0:
            return {"error": "lead_time_days must be a positive number"}

        # Validate service_level_z
        try:
            z = float(service_level_z)
        except (TypeError, ValueError):
            return {"error": "service_level_z must be numeric"}
        if not math.isfinite(z):
            return {"error": "service_level_z must be finite"}

        # Calculations
        average_daily_demand = float(np.mean(sales_values))
        demand_stdev = float(np.std(sales_values, ddof=0))  # population std dev

        safety_stock = int(round(z * demand_stdev * math.sqrt(lead_time)))
        reorder_point = int(round(average_daily_demand * lead_time) + safety_stock)

        return {
            "average_daily_demand": average_daily_demand,
            "safety_stock": safety_stock,
            "reorder_point": reorder_point
        }

    except Exception as e:
        # Match forecast.py's convention: never raise, always return error dict
        return {"error": str(e)}


if __name__ == "__main__":
    # Optional simple CLI for testing:
    # Reads JSON list for daily_forecast from stdin and lead_time_days from env var or defaults
    import sys
    try:
        input_json = sys.stdin.read().strip()
        daily = json.loads(input_json) if input_json else []
        lead_time_arg = float(sys.argv[1]) if len(sys.argv) > 1 else 7
        result = calculate_reorder_point(daily, lead_time_arg)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
