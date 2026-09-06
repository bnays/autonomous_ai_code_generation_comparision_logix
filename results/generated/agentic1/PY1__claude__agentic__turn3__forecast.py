import traceback
from datetime import date, timedelta

import mysql.connector
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

# ---------------------------------------------------------------------------
# Database configuration – adjust via environment / config as needed
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "logix",
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _fetch_sales(sku: str) -> pd.DataFrame:
    """
    Connect to MySQL, run a parameterized query via pd.read_sql,
    and return a DataFrame with columns [sale_date, quantity_sold].
    Raises on DB error.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        query = (
            "SELECT sale_date, quantity_sold "
            "FROM sales_history "
            "WHERE sku = %s "
            "ORDER BY sale_date ASC"
        )
        df = pd.read_sql(sql=query, con=conn, params=[sku])
    finally:
        conn.close()

    return df


def _build_full_series(df: pd.DataFrame) -> pd.Series:
    """
    Given a DataFrame with a date column (sale_date or date) and
    quantity_sold, aggregate duplicates, reindex to a continuous daily
    DatetimeIndex, filling gaps with 0.
    """
    df = df.copy()

    # Normalise the date column name
    if "sale_date" in df.columns:
        date_col = "sale_date"
    elif "date" in df.columns:
        date_col = "date"
    else:
        # Fall back to the first column
        date_col = df.columns[0]

    df[date_col] = pd.to_datetime(df[date_col])
    df["quantity_sold"] = pd.to_numeric(df["quantity_sold"], errors="coerce").fillna(0)

    df = df.groupby(date_col, as_index=False)["quantity_sold"].sum()
    df.sort_values(date_col, inplace=True)

    series = df.set_index(date_col)["quantity_sold"]
    idx = pd.date_range(series.index.min(), series.index.max(), freq="D")
    return series.reindex(idx, fill_value=0)


def _engineer_features(series: pd.Series) -> pd.DataFrame:
    """Create lag and rolling-average features from a daily sales Series."""
    df = pd.DataFrame({"y": series.values}, index=series.index)

    lags = [1, 2, 3, 7, 14, 21, 28]
    for lag in lags:
        df[f"lag_{lag}"] = df["y"].shift(lag)

    windows = [7, 14, 28]
    for w in windows:
        df[f"roll_mean_{w}"] = df["y"].shift(1).rolling(w).mean()
        df[f"roll_std_{w}"] = df["y"].shift(1).rolling(w).std()

    # Calendar features
    df["dayofweek"] = df.index.dayofweek
    df["dayofmonth"] = df.index.day
    df["month"] = df.index.month
    df["dayofyear"] = df.index.dayofyear

    return df


def _train_model(df_feat: pd.DataFrame):
    """
    Drop NaN rows, train RandomForestRegressor(n_estimators=100, random_state=42).
    Returns (model, mae, feature_cols) or (None, None, None) on failure.
    """
    df_clean = df_feat.dropna()
    if df_clean.empty:
        return None, None, None

    feature_cols = [c for c in df_clean.columns if c != "y"]
    X = df_clean[feature_cols].values
    y = df_clean["y"].values

    model = RandomForestRegressor(n_estimators=100, random_state=42)

    # Simple train/val split (last 20 % as validation)
    split = max(1, int(len(X) * 0.8))
    if split < len(X):
        model.fit(X[:split], y[:split])
        y_pred_val = model.predict(X[split:])
        mae = float(mean_absolute_error(y[split:], y_pred_val))
        # Retrain on full data for forecasting
        model.fit(X, y)
    else:
        model.fit(X, y)
        y_pred_train = model.predict(X)
        mae = float(mean_absolute_error(y, y_pred_train))

    return model, mae, feature_cols


def _compute_accuracy(mae: float, series: pd.Series) -> float:
    """Return a 0-100 accuracy score based on MAE vs mean sales."""
    mean_sales = series.mean()
    if mean_sales <= 0:
        return 100.0 if mae == 0 else 0.0
    accuracy = max(0.0, 1.0 - mae / mean_sales) * 100.0
    return round(accuracy, 2)


def _recursive_forecast(model, series: pd.Series, feature_cols: list, horizon: int = 365):
    """
    Recursively forecast `horizon` days beyond the last date in `series`.
    Returns a list of (date, predicted_quantity) tuples.
    """
    history = list(series.values)
    last_date = series.index[-1]

    predictions = []

    for step in range(1, horizon + 1):
        forecast_date = last_date + timedelta(days=step)

        row = {}

        def get_hist(lag, _history=history):
            idx = len(_history) - lag
            return _history[idx] if idx >= 0 else 0.0

        for lag in [1, 2, 3, 7, 14, 21, 28]:
            row[f"lag_{lag}"] = get_hist(lag)

        for w in [7, 14, 28]:
            window_vals = [history[-(w - i)] for i in range(w) if len(history) >= (w - i)]
            if window_vals:
                row[f"roll_mean_{w}"] = float(np.mean(window_vals))
                row[f"roll_std_{w}"] = float(np.std(window_vals)) if len(window_vals) > 1 else 0.0
            else:
                row[f"roll_mean_{w}"] = 0.0
                row[f"roll_std_{w}"] = 0.0

        row["dayofweek"] = forecast_date.dayofweek
        row["dayofmonth"] = forecast_date.day
        row["month"] = forecast_date.month
        row["dayofyear"] = forecast_date.timetuple().tm_yday

        X_row = np.array([[row.get(c, 0.0) for c in feature_cols]])
        pred = float(model.predict(X_row)[0])
        pred = max(0.0, pred)

        history.append(pred)
        predictions.append((forecast_date.date(), round(pred, 4)))

    return predictions


def _aggregate_forecast(predictions: list, today: date) -> dict:
    """
    Aggregate a list of (date, qty) into daily/weekly/monthly/yearly buckets.

    - daily  : next 7 calendar days  (up to 7 rows)
    - weekly : next 4 weeks          (up to 4 rows)
    - monthly: next 12 months        (up to 12 rows)
    - yearly : full 365 days grouped by year (>= 1 row)
    """
    df = pd.DataFrame(predictions, columns=["date", "quantity"])
    df["date"] = pd.to_datetime(df["date"])

    # ---- Daily: first 7 rows ------------------------------------------------
    daily_df = df.head(7).copy()
    daily = [
        {"date": str(r["date"].date()), "quantity": round(r["quantity"], 2)}
        for _, r in daily_df.iterrows()
    ]

    # ---- Weekly: group into calendar weeks, keep first 4 --------------------
    df["week_start"] = df["date"] - pd.to_timedelta(df["date"].dt.dayofweek, unit="D")
    weekly_grp = (
        df.groupby("week_start", as_index=False)["quantity"]
        .sum()
        .sort_values("week_start")
        .head(4)
    )
    weekly = [
        {
            "week_start": str(r["week_start"].date()),
            "week_end": str((r["week_start"] + timedelta(days=6)).date()),
            "quantity": round(r["quantity"], 2),
        }
        for _, r in weekly_grp.iterrows()
    ]

    # ---- Monthly: group by year-month, keep first 12 ------------------------
    df["year_month"] = df["date"].dt.to_period("M")
    monthly_grp = (
        df.groupby("year_month", as_index=False)["quantity"]
        .sum()
        .sort_values("year_month")
        .head(12)
    )
    monthly = [
        {
            "month": str(r["year_month"]),
            "quantity": round(r["quantity"], 2),
        }
        for _, r in monthly_grp.iterrows()
    ]

    # ---- Yearly: group by year (covers all 365 days) ------------------------
    df["year"] = df["date"].dt.year
    yearly_grp = (
        df.groupby("year", as_index=False)["quantity"]
        .sum()
        .sort_values("year")
    )
    yearly = [
        {"year": int(r["year"]), "quantity": round(r["quantity"], 2)}
        for _, r in yearly_grp.iterrows()
    ]

    return {
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "yearly": yearly,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_forecast(sku_input):
    """
    Run a 365-day recursive sales forecast for the given SKU.

    Parameters
    ----------
    sku_input : str
        The SKU identifier (whitespace will be stripped).

    Returns
    -------
    dict
        On success:
            {
                "sku": str,
                "today": str,          # ISO date
                "accuracy": float,     # 0-100
                "daily":   [...],      # 7 rows
                "weekly":  [...],      # <= 4 rows
                "monthly": [...],      # <= 12 rows
                "yearly":  [...],      # >= 1 row
            }
        On failure:
            {"error": str}
    """
    try:
        sku = str(sku_input).strip()
        today = date.today()

        # 1. Fetch historical sales from DB
        try:
            df_raw = _fetch_sales(sku)
        except Exception as db_err:
            return {"error": f"Database connection failed: {db_err}"}

        # 2. Check for empty data
        if df_raw.empty:
            return {"error": f"No historical data found for SKU: {sku}"}

        # 3. Build continuous daily series
        series = _build_full_series(df_raw)

        # 4. Engineer features
        df_feat = _engineer_features(series)

        # 5. Train model
        model, mae, feature_cols = _train_model(df_feat)
        if model is None:
            return {"error": f"Insufficient data to train model for SKU: {sku}"}

        # 6. Compute accuracy
        accuracy = _compute_accuracy(mae, series)

        # 7. Recursive 365-day forecast
        predictions = _recursive_forecast(model, series, feature_cols, horizon=365)

        # 8. Aggregate into buckets
        aggregated = _aggregate_forecast(predictions, today)

        return {
            "sku": sku,
            "today": str(today),
            "accuracy": accuracy,
            **aggregated,
        }

    except Exception:
        # Never raise – return error dict instead
        return {"error": f"Unexpected error during forecast: {traceback.format_exc()}"}
