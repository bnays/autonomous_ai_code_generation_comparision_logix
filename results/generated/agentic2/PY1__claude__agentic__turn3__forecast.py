import os
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:
    mysql = None
    MySQLError = Exception

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "localhost"),
    "port": int(os.environ.get("MYSQL_PORT", 3306)),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": os.environ.get("MYSQL_DATABASE", "logix"),
}


# ---------------------------------------------------------------------------
# Helper – feature engineering
# ---------------------------------------------------------------------------

def _build_features(series: pd.Series):
    """
    Given a daily time-series (index=DatetimeIndex, values=quantity_sold),
    build lag and rolling-average features.

    Returns (X, y, feature_cols).
    """
    df = pd.DataFrame({"y": series.values}, index=series.index)

    # Lag features
    for lag in [1, 2, 3, 7, 14]:
        df[f"lag_{lag}"] = df["y"].shift(lag)

    # Rolling-average features
    for window in [3, 7, 14, 30]:
        df[f"roll_mean_{window}"] = df["y"].shift(1).rolling(window).mean()

    # Calendar features
    df["day_of_week"] = df.index.dayofweek
    df["day_of_month"] = df.index.day
    df["month"] = df.index.month
    df["week_of_year"] = df.index.isocalendar().week.astype(int)

    df.dropna(inplace=True)

    feature_cols = [c for c in df.columns if c != "y"]
    X = df[feature_cols].values
    y = df["y"].values
    return X, y, feature_cols


def _make_row_features(history_window: list, pred_date: date, feature_cols: list):
    """
    Build a single feature row for *pred_date* using the rolling history.
    """
    window = list(history_window)
    while len(window) < 30:
        window.insert(0, 0.0)

    row = {}
    for lag in [1, 2, 3, 7, 14]:
        row[f"lag_{lag}"] = window[-lag]

    for w in [3, 7, 14, 30]:
        row[f"roll_mean_{w}"] = float(np.mean(window[-w:]))

    row["day_of_week"] = pred_date.weekday()
    row["day_of_month"] = pred_date.day
    row["month"] = pred_date.month
    row["week_of_year"] = pred_date.isocalendar()[1]

    return np.array([row[col] for col in feature_cols], dtype=float)


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def run_forecast(sku_input):
    """
    Connect to MySQL via pd.read_sql, fetch historical sales for the given SKU,
    train a RandomForestRegressor, produce a 365-day recursive forecast, and
    return a structured result dict.

    Returns {'error': ...} on any failure – never raises.
    """

    # ------------------------------------------------------------------
    # 0. Sanitise input
    # ------------------------------------------------------------------
    if sku_input is None:
        return {"error": "SKU must not be None."}

    sku = str(sku_input).strip()
    if not sku:
        return {"error": "SKU must not be empty or whitespace."}

    # ------------------------------------------------------------------
    # 1. Fetch data from MySQL using pd.read_sql
    # ------------------------------------------------------------------
    try:
        conn = mysql.connector.connect(**DB_CONFIG)

        query = (
            "SELECT sale_date AS date, quantity_sold "
            "FROM sales_history "
            "WHERE sku = %s "
            "ORDER BY sale_date ASC"
        )
        raw_df = pd.read_sql(
            sql=query,
            con=conn,
            params=[sku],
        )

        conn.close()

    except MySQLError as exc:
        return {"error": f"Database connection/query failed: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error while fetching data: {exc}"}

    # ------------------------------------------------------------------
    # 2. Check for empty data
    # ------------------------------------------------------------------
    if raw_df.empty:
        return {"error": f"No historical data found for SKU: {sku}"}

    # ------------------------------------------------------------------
    # 3. Build a complete daily time-series (fill gaps with 0)
    # ------------------------------------------------------------------
    try:
        # Support either 'date' or 'sale_date' column name from the query result
        date_col = "date" if "date" in raw_df.columns else "sale_date"
        qty_col = "quantity_sold"

        raw_df[date_col] = pd.to_datetime(raw_df[date_col])
        grouped = raw_df.groupby(date_col)[qty_col].sum()

        full_index = pd.date_range(grouped.index.min(), grouped.index.max(), freq="D")
        series = grouped.reindex(full_index, fill_value=0).astype(float)
        series.index = pd.DatetimeIndex(series.index)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Error processing historical data: {exc}"}

    # ------------------------------------------------------------------
    # 4. Feature engineering
    # ------------------------------------------------------------------
    try:
        X, y, feature_cols = _build_features(series)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Feature engineering failed: {exc}"}

    if len(X) == 0:
        return {"error": "Not enough historical data to engineer features for training."}

    # ------------------------------------------------------------------
    # 5. Train / evaluate
    # ------------------------------------------------------------------
    try:
        model = RandomForestRegressor(n_estimators=100, random_state=42)

        split = max(1, int(len(X) * 0.8))
        if split < len(X):
            X_train, X_test = X[:split], X[split:]
            y_train, y_test = y[:split], y[split:]
            model.fit(X_train, y_train)
            preds_test = model.predict(X_test)
            mae = mean_absolute_error(y_test, preds_test)
            mean_actual = float(np.mean(np.abs(y_test)))
            if mean_actual == 0:
                mean_actual = 1.0
            accuracy = float(max(0.0, 1.0 - mae / mean_actual))
            # Retrain on full data for forecasting
            model.fit(X, y)
        else:
            model.fit(X, y)
            accuracy = None
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Model training failed: {exc}"}

    # ------------------------------------------------------------------
    # 6. Recursive 365-day forecast
    # ------------------------------------------------------------------
    try:
        today = date.today()

        history_vals = list(series.values[-30:])

        forecast_dates = []
        forecast_values = []

        for i in range(365):
            pred_date = today + timedelta(days=i + 1)
            row_features = _make_row_features(history_vals, pred_date, feature_cols)
            pred = float(model.predict(row_features.reshape(1, -1))[0])
            pred = max(0.0, pred)

            forecast_dates.append(pred_date)
            forecast_values.append(pred)

            history_vals.append(pred)
            if len(history_vals) > 60:
                history_vals.pop(0)

        forecast_df = pd.DataFrame({"date": forecast_dates, "quantity": forecast_values})
        forecast_df["date"] = pd.to_datetime(forecast_df["date"])

    except Exception as exc:  # noqa: BLE001
        return {"error": f"Forecast generation failed: {exc}"}

    # ------------------------------------------------------------------
    # 7. Aggregate into buckets
    # ------------------------------------------------------------------
    try:
        # -- Daily: first 7 days
        daily = []
        for _, r in forecast_df.head(7).iterrows():
            daily.append({
                "date": r["date"].date().isoformat(),
                "forecasted_quantity": round(r["quantity"], 4),
            })

        # -- Weekly: group by ISO year+week, first ≤4 weeks
        forecast_df["iso_year"] = forecast_df["date"].dt.isocalendar().year.astype(int)
        forecast_df["iso_week"] = forecast_df["date"].dt.isocalendar().week.astype(int)

        weekly_groups = (
            forecast_df.groupby(["iso_year", "iso_week"])
            .agg(
                week_start=("date", "min"),
                week_end=("date", "max"),
                forecasted_quantity=("quantity", "sum"),
            )
            .reset_index(drop=True)
        )
        weekly = []
        for _, r in weekly_groups.head(4).iterrows():
            weekly.append({
                "week_start": r["week_start"].date().isoformat(),
                "week_end": r["week_end"].date().isoformat(),
                "forecasted_quantity": round(r["forecasted_quantity"], 4),
            })

        # -- Monthly: group by year-month, first ≤12
        forecast_df["year_month"] = forecast_df["date"].dt.to_period("M")
        monthly_groups = (
            forecast_df.groupby("year_month")["quantity"]
            .sum()
            .reset_index()
        )
        monthly_groups.columns = ["year_month", "forecasted_quantity"]
        monthly = []
        for _, r in monthly_groups.head(12).iterrows():
            monthly.append({
                "month": str(r["year_month"]),
                "forecasted_quantity": round(r["forecasted_quantity"], 4),
            })

        # -- Yearly: group by calendar year, ≥1 row
        forecast_df["year"] = forecast_df["date"].dt.year
        yearly_groups = (
            forecast_df.groupby("year")["quantity"]
            .sum()
            .reset_index()
        )
        yearly_groups.columns = ["year", "forecasted_quantity"]
        yearly = []
        for _, r in yearly_groups.iterrows():
            yearly.append({
                "year": int(r["year"]),
                "forecasted_quantity": round(r["forecasted_quantity"], 4),
            })

    except Exception as exc:  # noqa: BLE001
        return {"error": f"Aggregation failed: {exc}"}

    # ------------------------------------------------------------------
    # 8. Build and return result
    # ------------------------------------------------------------------
    return {
        "sku": sku,
        "today": today.isoformat(),
        "accuracy": round(accuracy, 4) if accuracy is not None else None,
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "yearly": yearly,
    }
