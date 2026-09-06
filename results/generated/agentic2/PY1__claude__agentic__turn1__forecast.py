import traceback
from datetime import date, timedelta

import numpy as np
import pandas as pd

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:
    mysql = None
    MySQLError = Exception

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

# ---------------------------------------------------------------------------
# Database configuration – adjust via environment or a config file as needed
# ---------------------------------------------------------------------------
import os

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
    Given a daily time-series (index=date, values=quantity_sold),
    build a feature DataFrame with lag and rolling-average columns.

    Returns (X, y) where X is a numpy array and y is a numpy array.
    Both arrays are aligned (rows with any NaN are dropped).
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
    Build a single feature row (1-D numpy array) for *pred_date* using the
    rolling history already available.

    history_window : list of recent daily values (most recent last).
                     Must contain at least 30 elements (padded with 0s if needed).
    """
    # Ensure we have enough history
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

    # ISO week
    iso_week = pred_date.isocalendar()[1]
    row["week_of_year"] = iso_week

    return np.array([row[col] for col in feature_cols], dtype=float)


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def run_forecast(sku_input):
    """
    Connect to MySQL, fetch historical sales for the given SKU, train a
    RandomForestRegressor, produce a 365-day recursive forecast, and return
    a structured result dict.

    Returns
    -------
    dict with keys:
        sku, today, accuracy,
        daily   – list of {date, forecasted_quantity} for next 7 days
        weekly  – list of {week_start, week_end, forecasted_quantity} (≤4 rows)
        monthly – list of {month, forecasted_quantity} (≤12 rows)
        yearly  – list of {year, forecasted_quantity} (≥1 row)

    On any failure returns {'error': <message>}.
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
    # 1. Fetch data from MySQL
    # ------------------------------------------------------------------
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        query = (
            "SELECT sale_date, quantity_sold "
            "FROM sales_history "
            "WHERE sku = %s "
            "ORDER BY sale_date ASC"
        )
        cursor.execute(query, (sku,))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

    except MySQLError as exc:
        return {"error": f"Database connection/query failed: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error while fetching data: {exc}"}

    if not rows:
        return {"error": f"No historical data found for SKU '{sku}'."}

    # ------------------------------------------------------------------
    # 2. Build a complete daily time-series (fill gaps with 0)
    # ------------------------------------------------------------------
    try:
        raw_df = pd.DataFrame(rows, columns=["sale_date", "quantity_sold"])
        raw_df["sale_date"] = pd.to_datetime(raw_df["sale_date"])
        raw_df = raw_df.groupby("sale_date")["quantity_sold"].sum()

        full_index = pd.date_range(raw_df.index.min(), raw_df.index.max(), freq="D")
        series = raw_df.reindex(full_index, fill_value=0).astype(float)
        series.index = pd.DatetimeIndex(series.index)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Error processing historical data: {exc}"}

    # ------------------------------------------------------------------
    # 3. Feature engineering
    # ------------------------------------------------------------------
    try:
        X, y, feature_cols = _build_features(series)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Feature engineering failed: {exc}"}

    if len(X) == 0:
        return {"error": "Not enough historical data to engineer features for training."}

    # ------------------------------------------------------------------
    # 4. Train / evaluate
    # ------------------------------------------------------------------
    try:
        model = RandomForestRegressor(n_estimators=100, random_state=42)

        # Simple train/test split (last 20 % as test, min 1 sample)
        split = max(1, int(len(X) * 0.8))
        if split < len(X):
            X_train, X_test = X[:split], X[split:]
            y_train, y_test = y[:split], y[split:]
            model.fit(X_train, y_train)
            preds_test = model.predict(X_test)
            mae = mean_absolute_error(y_test, preds_test)
            mean_actual = np.mean(np.abs(y_test)) if np.mean(np.abs(y_test)) != 0 else 1.0
            accuracy = float(max(0.0, 1.0 - mae / mean_actual))
            # Retrain on full data for forecasting
            model.fit(X, y)
        else:
            model.fit(X, y)
            accuracy = None  # Cannot evaluate with single sample
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Model training failed: {exc}"}

    # ------------------------------------------------------------------
    # 5. Recursive 365-day forecast
    # ------------------------------------------------------------------
    try:
        today = date.today()

        # Seed the rolling history from the last 30 actual values
        history_vals = list(series.values[-30:])

        forecast_dates = []
        forecast_values = []

        for i in range(365):
            pred_date = today + timedelta(days=i + 1)
            row_features = _make_row_features(history_vals, pred_date, feature_cols)
            pred = float(model.predict(row_features.reshape(1, -1))[0])
            pred = max(0.0, pred)  # quantities cannot be negative

            forecast_dates.append(pred_date)
            forecast_values.append(pred)

            # Extend history window
            history_vals.append(pred)
            if len(history_vals) > 60:  # keep window manageable
                history_vals.pop(0)

        forecast_df = pd.DataFrame({"date": forecast_dates, "quantity": forecast_values})
        forecast_df["date"] = pd.to_datetime(forecast_df["date"])

    except Exception as exc:  # noqa: BLE001
        return {"error": f"Forecast generation failed: {exc}"}

    # ------------------------------------------------------------------
    # 6. Aggregate into buckets
    # ------------------------------------------------------------------
    try:
        # -- Daily: first 7 days
        daily = []
        for _, r in forecast_df.head(7).iterrows():
            daily.append({
                "date": r["date"].date().isoformat(),
                "forecasted_quantity": round(r["quantity"], 4),
            })

        # -- Weekly: group by ISO week, first ≤4 complete/partial weeks
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

        # -- Yearly: group by year, ≥1 row
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
    # 7. Build and return result
    # ------------------------------------------------------------------
    result = {
        "sku": sku,
        "today": today.isoformat(),
        "accuracy": round(accuracy, 4) if accuracy is not None else None,
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "yearly": yearly,
    }
    return result
