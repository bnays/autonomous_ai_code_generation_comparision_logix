import math
import json
import sys
import numpy as np

def calculate_reorder_point(daily_forecast, lead_time_days, service_level_z=1.65):
    try:
        if not daily_forecast:
            return {"error": "daily_forecast cannot be empty"}
        
        if not isinstance(lead_time_days, (int, float)) or lead_time_days <= 0:
            return {"error": "lead_time_days must be a positive number"}

        sales = [item["predicted_sales"] for item in daily_forecast]
        
        average_daily_demand = float(np.mean(sales))
        demand_stdev = float(np.std(sales, ddof=0))  # Population standard deviation

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
    if len(sys.argv) > 2:
        try:
            forecast_arg = json.loads(sys.argv[1])
            lead_time_arg = float(sys.argv[2])
            z_arg = float(sys.argv[3]) if len(sys.argv) > 3 else 1.65
            result = calculate_reorder_point(forecast_arg, lead_time_arg, z_arg)
        except Exception as e:
            result = {"error": str(e)}
    else:
        result = {"error": "Usage: python reorder.py <daily_forecast_json> <lead_time_days> [service_level_z]"}
    
    print(json.dumps(result))
