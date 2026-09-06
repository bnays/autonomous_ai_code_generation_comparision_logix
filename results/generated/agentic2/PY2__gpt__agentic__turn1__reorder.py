import math
import statistics

def calculate_reorder_point(daily_forecast, lead_time_days, service_level_z=1.65):
    """
    Calculate reorder point based on forecasted daily demand, lead time, and desired service level.

    Parameters:
        daily_forecast (list of dict): List like [{"date": "YYYY-MM-DD", "predicted_sales": int}, ...]
        lead_time_days (int|float): Lead time in days (must be > 0)
        service_level_z (int|float): Z-score for desired service level (default 1.65 ≈ 95%)

    Returns:
        dict: {
            "average_daily_demand": float,
            "safety_stock": int,
            "reorder_point": int
        }
        or on error:
        {"error": "..."}
    """
    try:
        # Validate inputs
        if not daily_forecast or not isinstance(daily_forecast, list):
            return {"error": "daily_forecast is empty or invalid"}

        if not isinstance(lead_time_days, (int, float)) or lead_time_days <= 0:
            return {"error": "lead_time_days must be a positive number"}

        if not isinstance(service_level_z, (int, float)):
            return {"error": "service_level_z must be a number"}

        # Extract predicted_sales values, allowing numeric strings
        sales_values = []
        for rec in daily_forecast:
            try:
                val = rec.get("predicted_sales")
            except AttributeError:
                continue
            if isinstance(val, (int, float)):
                sales_values.append(float(val))
            else:
                try:
                    if val is not None and str(val).strip() != "":
                        sales_values.append(float(val))
                except Exception:
                    # Skip non-numeric entries
                    pass

        if len(sales_values) == 0:
            return {"error": "No valid predicted_sales values in daily_forecast"}

        # Calculations
        average_daily_demand = sum(sales_values) / len(sales_values)
        demand_stdev = 0.0 if len(sales_values) == 1 else statistics.pstdev(sales_values)

        safety_stock = round(float(service_level_z) * demand_stdev * math.sqrt(float(lead_time_days)))
        reorder_point = round(average_daily_demand * float(lead_time_days)) + safety_stock

        return {
            "average_daily_demand": float(average_daily_demand),
            "safety_stock": int(safety_stock),
            "reorder_point": int(reorder_point)
        }

    except Exception as e:
        return {"error": str(e)}
