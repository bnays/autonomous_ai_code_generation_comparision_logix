# File: ai-module/reorder.py
import json
import math
import sys


def calculate_reorder_point(daily_forecast, lead_time_days, service_level_z=1.65):
    """
    Calculate the reorder point for a given SKU based on forecasted daily demand.

    Parameters
    ----------
    daily_forecast : list of dict
        Forecasted daily sales shaped like forecast.py's `daily` output:
        [{"date": "YYYY-MM-DD", "predicted_sales": int}, ...]
    lead_time_days : int or float
        Supplier lead time in days. Must be a positive number.
    service_level_z : float, optional
        Z-score corresponding to the desired service level (default 1.65 ≈ 95%).

    Returns
    -------
    dict
        On success:
            {
                "average_daily_demand": float,
                "safety_stock": int,
                "reorder_point": int
            }
        On failure:
            {"error": str}
    """
    try:
        # --- Input Validation ---
        if not daily_forecast:
            return {"error": "daily_forecast is empty; cannot compute reorder point."}

        try:
            lead_time_days = float(lead_time_days)
        except (TypeError, ValueError):
            return {"error": f"lead_time_days must be a numeric value, got: {lead_time_days!r}"}

        if lead_time_days <= 0:
            return {"error": f"lead_time_days must be a positive number, got: {lead_time_days}"}

        # --- Extract Demand Values ---
        sales_values = []
        for i, record in enumerate(daily_forecast):
            if not isinstance(record, dict):
                return {"error": f"Entry at index {i} in daily_forecast is not a dict: {record!r}"}
            if "predicted_sales" not in record:
                return {"error": f"Entry at index {i} is missing the 'predicted_sales' key."}
            try:
                sales_values.append(float(record["predicted_sales"]))
            except (TypeError, ValueError):
                return {
                    "error": (
                        f"'predicted_sales' at index {i} cannot be converted to a number: "
                        f"{record['predicted_sales']!r}"
                    )
                }

        n = len(sales_values)

        # --- Statistics ---
        average_daily_demand = sum(sales_values) / n

        # Population standard deviation (consistent with using full known forecast window)
        variance = sum((x - average_daily_demand) ** 2 for x in sales_values) / n
        demand_stdev = math.sqrt(variance)

        # --- Reorder Point Components ---
        safety_stock = round(service_level_z * demand_stdev * math.sqrt(lead_time_days))
        reorder_point = round(average_daily_demand * lead_time_days) + safety_stock

        return {
            "average_daily_demand": round(average_daily_demand, 4),
            "safety_stock": int(safety_stock),
            "reorder_point": int(reorder_point),
        }

    except Exception as e:
        # Mirror forecast.py's convention: never raise, always return {"error": ...}
        return {"error": str(e)}


if __name__ == "__main__":
    # Minimal CLI for ad-hoc testing:
    # python reorder.py '<json_daily_forecast>' <lead_time_days> [service_level_z]
    # Example:
    #   python reorder.py '[{"date":"2024-01-01","predicted_sales":10}]' 7 1.65
    if len(sys.argv) < 3:
        result = {"error": "Usage: reorder.py '<json_daily_forecast>' <lead_time_days> [service_level_z]"}
    else:
        try:
            forecast_arg = json.loads(sys.argv[1])
        except json.JSONDecodeError as exc:
            forecast_arg = None
            result = {"error": f"Invalid JSON for daily_forecast: {exc}"}
        else:
            lead_arg = sys.argv[2]
            z_arg = float(sys.argv[3]) if len(sys.argv) > 3 else 1.65
            result = calculate_reorder_point(forecast_arg, lead_arg, z_arg)

    print(json.dumps(result))
