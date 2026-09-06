import math
import statistics
import json
import sys

def calculate_reorder_point(daily_forecast, lead_time_days, service_level_z=1.65):
    """
    Calculates safety stock and reorder point based on daily forecast projections.

    Parameters:
        daily_forecast (list): List of dicts, e.g. [{"date": "...", "predicted_sales": int}, ...]
        lead_time_days (int/float): Supplier lead time in days.
        service_level_z (float): Z-score corresponding to desired service level. Defaults to 1.65 (~95%).

    Returns:
        dict: Calculated metrics or an error dictionary matching forecast.py convention.
    """
    try:
        if not daily_forecast:
            return {"error": "daily_forecast cannot be empty"}

        if lead_time_days is None or lead_time_days <= 0:
            return {"error": "lead_time_days must be a positive number"}

        sales = [
            item["predicted_sales"] 
            for item in daily_forecast 
            if isinstance(item, dict) and "predicted_sales" in item
        ]

        if not sales:
            return {"error": "Invalid daily_forecast format or missing predicted_sales data"}

        average_daily_demand = float(statistics.mean(sales))
        demand_stdev = float(statistics.pstdev(sales)) if len(sales) > 1 else 0.0

        safety_stock = int(round(service_level_z * demand_stdev * math.sqrt(lead_time_days)))
        reorder_point = int(round(average_daily_demand * lead_time_days)) + safety_stock

        return {
            "average_daily_demand": round(average_daily_demand, 2),
            "safety_stock": safety_stock,
            "reorder_point": reorder_point
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    try:
        forecast_arg = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
        lead_time_arg = float(sys.argv[2]) if len(sys.argv) > 2 else 0
        z_arg = float(sys.argv[3]) if len(sys.argv) > 3 else 1.65
        result = calculate_reorder_point(forecast_arg, lead_time_arg, z_arg)
    except Exception as e:
        result = {"error": str(e)}
    print(json.dumps(result))
