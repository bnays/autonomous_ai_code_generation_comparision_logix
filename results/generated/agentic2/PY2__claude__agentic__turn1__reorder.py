import json
import math


def calculate_reorder_point(daily_forecast, lead_time_days, service_level_z=1.65):
    """
    Calculate the reorder point for a SKU based on a daily sales forecast.

    Parameters
    ----------
    daily_forecast : list[dict]
        Daily forecast data shaped like forecast.py's `daily` output:
        [{"date": "YYYY-MM-DD", "predicted_sales": int}, ...]
    lead_time_days : int | float
        Number of days it takes for a replenishment order to arrive.
        Must be a positive number.
    service_level_z : float
        Z-score corresponding to the desired service level.
        Defaults to 1.65 (~95 % service level).

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
        # --- Input validation ---------------------------------------------------
        if not daily_forecast:
            return {"error": "daily_forecast is empty; cannot compute reorder point."}

        try:
            lead_time_days = float(lead_time_days)
        except (TypeError, ValueError):
            return {"error": f"lead_time_days must be a numeric value, got: {lead_time_days!r}"}

        if lead_time_days <= 0:
            return {"error": f"lead_time_days must be a positive number, got: {lead_time_days}"}

        # --- Extract sales values -----------------------------------------------
        sales_values = []
        for idx, record in enumerate(daily_forecast):
            if not isinstance(record, dict):
                return {"error": f"daily_forecast[{idx}] is not a dict: {record!r}"}
            if "predicted_sales" not in record:
                return {"error": f"daily_forecast[{idx}] is missing key 'predicted_sales'."}
            try:
                sales_values.append(float(record["predicted_sales"]))
            except (TypeError, ValueError):
                return {
                    "error": (
                        f"daily_forecast[{idx}]['predicted_sales'] cannot be converted "
                        f"to a number: {record['predicted_sales']!r}"
                    )
                }

        n = len(sales_values)

        # --- Statistical calculations -------------------------------------------
        average_daily_demand = sum(sales_values) / n

        # Population standard deviation (consistent with a fixed forecast window)
        variance = sum((x - average_daily_demand) ** 2 for x in sales_values) / n
        demand_stdev = math.sqrt(variance)

        # --- Core formulas ------------------------------------------------------
        safety_stock = round(service_level_z * demand_stdev * math.sqrt(lead_time_days))
        reorder_point = round(average_daily_demand * lead_time_days) + safety_stock

        return {
            "average_daily_demand": round(average_daily_demand, 4),
            "safety_stock": int(safety_stock),
            "reorder_point": int(reorder_point),
        }

    except Exception as e:
        # Mirror forecast.py's convention: never raise, always return an error dict.
        return {"error": str(e)}


if __name__ == "__main__":
    import sys

    # Minimal CLI: accept JSON from stdin or a file path as the first argument,
    # plus optional lead_time_days and service_level_z positional arguments.
    #
    # Usage examples:
    #   echo '[{"date":"2024-01-01","predicted_sales":10}]' | python reorder.py - 7
    #   python reorder.py forecast_daily.json 14 1.96
    if len(sys.argv) < 3:
        print(
            json.dumps(
                {"error": "Usage: reorder.py <daily_forecast_json_or_'-'> <lead_time_days> [service_level_z]"}
            )
        )
        sys.exit(1)

    source = sys.argv[1]
    try:
        raw_lead = float(sys.argv[2])
    except ValueError:
        print(json.dumps({"error": f"Invalid lead_time_days: {sys.argv[2]!r}"}))
        sys.exit(1)

    z = 1.65
    if len(sys.argv) >= 4:
        try:
            z = float(sys.argv[3])
        except ValueError:
            print(json.dumps({"error": f"Invalid service_level_z: {sys.argv[3]!r}"}))
            sys.exit(1)

    try:
        if source == "-":
            raw_json = sys.stdin.read()
        else:
            with open(source, "r") as fh:
                raw_json = fh.read()
        daily = json.loads(raw_json)
    except Exception as exc:
        print(json.dumps({"error": f"Failed to read/parse daily_forecast: {exc}"}))
        sys.exit(1)

    result = calculate_reorder_point(daily, raw_lead, z)
    print(json.dumps(result))
