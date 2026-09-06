import traceback
from datetime import date, timedelta

import numpy as np
import pandas as pd

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:
    mysql.connector = None
    MySQLError = Exception

from sklearn.ensemble import RandomForestRegressor

# ---------------------------------------------------------------------------
# Database configuration – adjust to your environment / env-vars as needed
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "database": "logix",
    "user": "root",
    "password": "",
}

# ---------------------------------------------------------------------------
# Feature engineering helpers
# ---------------------------------------------------------------------------
LAG_DAYS = [1, 2, 3, 7, 14, 28]
ROLLING_WINDOWS = [7, 14, 28]


def _build_features(series: pd.Series) -> pd.DataFrame:
    """
    Given a daily quantity_sold Series (DatetimeIndex, no gaps),
    build lag + rolling-average features.
    Returns a DataFrame where every row has all features + target.
    Rows with NaN values (insufficient history) are dropped.
    """
    df = pd.DataFrame({"y": series})

    for lag in LAG_DAYS:
        df[f"lag_{lag}"] = df["y"].shift(lag)

    for window in ROLLING_WINDOWS:
        df[f"roll_mean_{window}"] = df["y"].shift(1).rolling(window).mean()

    df.dropna(inplace=True)
    return df


FEATURE_COLS = [f"lag_{l}" for l in LAG_DAYS] + [
    f"roll_mean_{w}" for w in ROLLING_WINDOWS
]


def _recursive_forecast(model: RandomForestRegressor, history: np.ndarray, days: int = 365) -> np.ndarray:
    """
    Recursively produce `days` future predictions using the trained model.
    `history` must be at least max(LAG_DAYS) long (padded if necessary).
    """
    max_lag = max(LAG_DAYS)
    buf = list(history[-max(max_lag, max(ROLLING_WINDOWS)):])  # rolling buffer

    preds = []
    for _ in range(days):
        row = {}
        for lag in LAG_DAYS:
            row[f"lag_{lag}"] = buf[-lag]
        for window in ROLLING_WINDOWS:
            vals = buf[-window:]
            row[f"roll_mean_{window}"] = float(np.mean(vals))

        x = np.array([[row[c] for c in FEATURE_COLS]])
        y_hat = float(model.predict(x)[0])
        y_hat = max(0.0, y_hat)          # quantities cannot be negative
        preds.append(y_hat)
        buf.append(y_hat)

    return np.array(preds)


# ---------------------------------------------------------------------------
# Accuracy helper (MAPE-based, converted to a 0-100 score)
# ---------------------------------------------------------------------------
def _accuracy_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true != 0
    if not mask.any():
        return 0.0
    mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask]))
    return round(max(0.0, (1 - mape) * 100), 2)


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------
def _aggregate_daily(forecast_series: pd.Series) -> list:
    """Return first 7 days."""
    result = []
    for day_date, qty in forecast_series.iloc[:7].items():
        result.append({
            "date": str(day_date.date()),
            "quantity": round(qty, 2),
        })
    return result


def _aggregate_weekly(forecast_series: pd.Series) -> list:
    """Return up to 4 ISO-week buckets."""
    df = pd.DataFrame({"quantity": forecast_series})
    df["week"] = df.index.to_period("W")
    weekly = df.groupby("week")["quantity"].sum().reset_index()
    weekly = weekly.iloc[:4]
    result = []
    for _, row in weekly.iterrows():
        result.append({
            "week": str(row["week"]),
            "quantity": round(row["quantity"], 2),
        })
    return result


def _aggregate_monthly(forecast_series: pd.Series) -> list:
    """Return up to 12 month buckets."""
    df = pd.DataFrame({"quantity": forecast_series})
    df["month"] = df.index.to_period("M")
    monthly = df.groupby("month")["quantity"].sum().reset_index()
    monthly = monthly.iloc[:12]
    result = []
    for _, row in monthly.iterrows():
        result.append({
            "month": str(row["month"]),
            "quantity": round(row["quantity"], 2),
        })
    return result


def _aggregate_yearly(forecast_series: pd.Series) -> list:
    """Return at least 1 year bucket (here exactly 1 for a 365-day window)."""
    df = pd.DataFrame({"quantity": forecast_series})
    df["year"] = df.index.to_period("Y")
    yearly = df.groupby("year")["quantity"].sum().reset_index()
    result = []
    for _, row in yearly.iterrows():
        result.append({
            "year": str(row["year"]),
            "quantity": round(row["quantity"], 2),
        })
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def run_forecast(sku_input):
    """
    Run a 365-day recursive forecast for the given SKU.

    Parameters
    ----------
    sku_input : str
        The SKU identifier (whitespace will be trimmed).

    Returns
    -------
    dict
        On success:
            {
                "sku":      str,
                "today":    str  (ISO date),
                "accuracy": float (0–100),
                "daily":    list[dict],   # 7 rows
                "weekly":   list[dict],   # <=4 rows
                "monthly":  list[dict],   # <=12 rows
                "yearly":   list[dict],   # >=1 row
            }
        On failure:
            {"error": str}
        Never raises.
    """
    # ------------------------------------------------------------------
    # 0. Sanitise input
    # ------------------------------------------------------------------
    try:
        sku = str(sku_input).strip()
    except Exception:
        return {"error": "Invalid SKU value."}

    if not sku:
        return {"error": "SKU must not be empty."}

    today = date.today()

    # ------------------------------------------------------------------
    # 1. Fetch historical data from MySQL
    # ------------------------------------------------------------------
    try:
        if mysql.connector is None:
            return {"error": "mysql.connector is not installed."}

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
        return {"error": f"Database connection failed: {exc}"}
    except Exception as exc:
        return {"error": f"Unexpected error while querying database: {exc}"}

    # ------------------------------------------------------------------
    # 2. Validate data
    # ------------------------------------------------------------------
    if not rows:
        return {"error": f"No historical data found for SKU '{sku}'."}

    # ------------------------------------------------------------------
    # 3. Build a clean daily time-series (fill missing days with 0)
    # ------------------------------------------------------------------
    try:
        raw = pd.DataFrame(rows, columns=["sale_date", "quantity_sold"])
        raw["sale_date"] = pd.to_datetime(raw["sale_date"])
        raw["quantity_sold"] = pd.to_numeric(raw["quantity_sold"], errors="coerce").fillna(0.0)
        raw = raw.groupby("sale_date")["quantity_sold"].sum()

        full_index = pd.date_range(start=raw.index.min(), end=raw.index.max(), freq="D")
        series = raw.reindex(full_index, fill_value=0.0)

    except Exception as exc:
        return {"error": f"Error processing historical data: {exc}"}

    # ------------------------------------------------------------------
    # 4. Feature engineering
    # ------------------------------------------------------------------
    try:
        feat_df = _build_features(series)

        if feat_df.empty or len(feat_df) < 2:
            return {"error": f"Insufficient historical data to train a model for SKU '{sku}'."}

        X = feat_df[FEATURE_COLS].values
        y = feat_df["y"].values

    except Exception as exc:
        return {"error": f"Feature engineering failed: {exc}"}

    # ------------------------------------------------------------------
    # 5. Train model
    # ------------------------------------------------------------------
    try:
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)

        y_pred_train = model.predict(X)
        accuracy = _accuracy_score(y, y_pred_train)

    except Exception as exc:
        return {"error": f"Model training failed: {exc}"}

    # ------------------------------------------------------------------
    # 6. Recursive 365-day forecast
    # ------------------------------------------------------------------
    try:
        history_values = series.values.astype(float)
        raw_preds = _recursive_forecast(model, history_values, days=365)

        forecast_index = pd.date_range(
            start=pd.Timestamp(today) + timedelta(days=1),
            periods=365,
            freq="D",
        )
        forecast_series = pd.Series(raw_preds, index=forecast_index)

    except Exception as exc:
        return {"error": f"Forecast generation failed: {exc}"}

    # ------------------------------------------------------------------
    # 7. Aggregate
    # ------------------------------------------------------------------
    try:
        daily = _aggregate_daily(forecast_series)
        weekly = _aggregate_weekly(forecast_series)
        monthly = _aggregate_monthly(forecast_series)
        yearly = _aggregate_yearly(forecast_series)

    except Exception as exc:
        return {"error": f"Aggregation failed: {exc}"}

    # ------------------------------------------------------------------
    # 8. Return result
    # ------------------------------------------------------------------
    return {
        "sku": sku,
        "today": str(today),
        "accuracy": accuracy,
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "yearly": yearly,
    }
