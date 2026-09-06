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
# Database configuration – adjust to your environment / inject via env vars
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "database": "logix",
    "user": "root",
    "password": "",
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_forecast(sku_input):
    """
    Forecast 365 days of demand for *sku_input*.

    Returns a dict with keys:
        sku, accuracy, today,
        daily   – list of {date, forecast}  (next 7 days)
        weekly  – list of {week, forecast}  (next <=4 weeks)
        monthly – list of {month, forecast} (next <=12 months)
        yearly  – list of {year, forecast}  (next >=1 year)

    Returns {'error': <message>} on any failure.
    """
    # ------------------------------------------------------------------ #
    # 1. Validate / sanitise input
    # ------------------------------------------------------------------ #
    try:
        sku = str(sku_input).strip()
    except Exception:
        return {"error": "Invalid SKU value."}

    if not sku:
        return {"error": "SKU must not be empty."}

    # ------------------------------------------------------------------ #
    # 2. Fetch historical data from MySQL
    # ------------------------------------------------------------------ #
    try:
        df_raw = _fetch_sales(sku)
    except Exception as exc:
        return {"error": f"Database connection failed: {exc}"}

    if df_raw is None or df_raw.empty:
        return {"error": f"No historical data found for SKU '{sku}'."}

    # ------------------------------------------------------------------ #
    # 3. Prepare a clean daily time-series
    # ------------------------------------------------------------------ #
    try:
        df = _prepare_series(df_raw)
    except Exception as exc:
        return {"error": f"Data preparation failed: {exc}"}

    if len(df) < 2:
        return {"error": f"Insufficient historical data for SKU '{sku}'."}

    # ------------------------------------------------------------------ #
    # 4. Feature engineering
    # ------------------------------------------------------------------ #
    try:
        df_feat = _engineer_features(df)
    except Exception as exc:
        return {"error": f"Feature engineering failed: {exc}"}

    if df_feat.empty:
        return {"error": "Not enough data after feature engineering."}

    # ------------------------------------------------------------------ #
    # 5. Train model
    # ------------------------------------------------------------------ #
    try:
        model, accuracy = _train_model(df_feat)
    except Exception as exc:
        return {"error": f"Model training failed: {exc}"}

    # ------------------------------------------------------------------ #
    # 6. Recursive 365-day forecast
    # ------------------------------------------------------------------ #
    try:
        forecast_series = _recursive_forecast(df, model, steps=365)
    except Exception as exc:
        return {"error": f"Forecasting failed: {exc}"}

    # ------------------------------------------------------------------ #
    # 7. Aggregate into buckets
    # ------------------------------------------------------------------ #
    try:
        today = date.today()
        result = _aggregate(forecast_series, today)
    except Exception as exc:
        return {"error": f"Aggregation failed: {exc}"}

    result["sku"] = sku
    result["accuracy"] = round(float(accuracy), 4)
    result["today"] = today.isoformat()

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_sales(sku: str) -> pd.DataFrame:
    """
    Query sales_history and return a raw DataFrame with columns
    [sale_date, quantity_sold].  Raises on connection / query errors.
    """
    if mysql is None:
        raise RuntimeError("mysql-connector-python is not installed.")

    conn = mysql.connector.connect(**DB_CONFIG)          # may raise MySQLError
    try:
        cursor = conn.cursor()
        query = (
            "SELECT sale_date, quantity_sold "
            "FROM sales_history "
            "WHERE TRIM(sku) = %s "
            "ORDER BY sale_date ASC"
        )
        cursor.execute(query, (sku,))
        rows = cursor.fetchall()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["sale_date", "quantity_sold"])
    return df


def _prepare_series(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Convert raw rows to a daily-indexed DataFrame with a single
    'qty' column.  Missing days are filled with 0.
    """
    df = df_raw.copy()
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    df["quantity_sold"] = pd.to_numeric(df["quantity_sold"], errors="coerce").fillna(0)

    # Aggregate duplicate dates
    df = df.groupby("sale_date", as_index=False)["quantity_sold"].sum()
    df = df.rename(columns={"quantity_sold": "qty"})
    df = df.set_index("sale_date").sort_index()

    # Reindex to fill every calendar day
    full_idx = pd.date_range(df.index.min(), df.index.max(), freq="D")
    df = df.reindex(full_idx, fill_value=0)
    df.index.name = "sale_date"

    return df


def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add lag and rolling-average features, then drop rows with NaN.
    """
    d = df.copy()

    # Lag features
    for lag in [1, 2, 3, 7, 14, 21, 28]:
        d[f"lag_{lag}"] = d["qty"].shift(lag)

    # Rolling averages
    for window in [7, 14, 28]:
        d[f"roll_{window}"] = d["qty"].shift(1).rolling(window).mean()

    # Calendar features
    d["dayofweek"] = d.index.dayofweek
    d["dayofmonth"] = d.index.day
    d["dayofyear"] = d.index.dayofyear
    d["weekofyear"] = d.index.isocalendar().week.astype(int)
    d["month"] = d.index.month

    d = d.dropna()
    return d


def _train_model(df_feat: pd.DataFrame):
    """
    Train a RandomForestRegressor and return (model, accuracy).
    accuracy = 1 - (MAE / mean_actual)  clipped to [0, 1].
    """
    feature_cols = [c for c in df_feat.columns if c != "qty"]
    X = df_feat[feature_cols].values
    y = df_feat["qty"].values

    # Simple temporal train/test split (80 / 20)
    split = max(1, int(len(X) * 0.8))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    if len(X_test) > 0:
        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        mean_actual = np.mean(y_test) if np.mean(y_test) != 0 else 1.0
        accuracy = float(np.clip(1.0 - mae / mean_actual, 0.0, 1.0))
    else:
        accuracy = 0.0

    # Retrain on full data
    model.fit(X, y)

    return model, accuracy


def _build_row_features(history: pd.Series, target_date) -> np.ndarray:
    """
    Build a single feature vector for *target_date* using the tail of
    *history* (a pd.Series indexed by date, containing past qty values).
    """
    lags = [1, 2, 3, 7, 14, 21, 28]
    rolls = [7, 14, 28]

    feat = []

    for lag in lags:
        idx = target_date - timedelta(days=lag)
        feat.append(float(history.get(idx, 0.0)))

    for window in rolls:
        vals = []
        for w in range(1, window + 1):
            idx = target_date - timedelta(days=w)
            vals.append(float(history.get(idx, 0.0)))
        feat.append(float(np.mean(vals)) if vals else 0.0)

    # Calendar features
    dt = pd.Timestamp(target_date)
    feat.append(dt.dayofweek)
    feat.append(dt.day)
    feat.append(dt.dayofyear)
    feat.append(int(dt.isocalendar()[1]))   # weekofyear
    feat.append(dt.month)

    return np.array(feat, dtype=float).reshape(1, -1)


def _recursive_forecast(df: pd.DataFrame, model, steps: int = 365) -> pd.Series:
    """
    Recursively forecast *steps* days into the future, appending each
    prediction to the known history so it can be used as a lag feature
    for subsequent predictions.
    """
    # Build a mutable dict of {date: qty} from the historical series
    history = {ts.date(): float(qty) for ts, qty in df["qty"].items()}

    today = date.today()
    forecasts = {}

    for i in range(1, steps + 1):
        target = today + timedelta(days=i)
        feat_vec = _build_row_features(history, target)
        pred = float(max(0.0, model.predict(feat_vec)[0]))
        history[target] = pred
        forecasts[target] = pred

    forecast_series = pd.Series(forecasts)
    forecast_series.index = pd.to_datetime(list(forecasts.keys()))
    forecast_series.index.name = "date"
    forecast_series.name = "forecast"

    return forecast_series


def _aggregate(forecast_series: pd.Series, today: date) -> dict:
    """
    Aggregate the 365-day daily forecast into:
        daily   – next 7 calendar days
        weekly  – next <=4 ISO weeks  (Mon-Sun buckets)
        monthly – next <=12 calendar months
        yearly  – next >=1 calendar year(s)
    """
    fs = forecast_series.copy()
    fs.index = pd.to_datetime(fs.index)

    # ---- Daily (next 7 days) ----------------------------------------- #
    daily = []
    for i in range(1, 8):
        d = today + timedelta(days=i)
        dt = pd.Timestamp(d)
        val = float(fs.get(dt, 0.0))
        daily.append({"date": d.isoformat(), "forecast": round(val, 2)})

    # ---- Weekly (next <=4 Mon-Sun weeks) -------------------------------- #
    # Find the Monday of the week that contains today+1
    first_day = today + timedelta(days=1)
    # Monday of that week
    week_start = first_day - timedelta(days=first_day.weekday())

    weekly = []
    for _ in range(4):
        week_end = week_start + timedelta(days=6)
        mask = (fs.index >= pd.Timestamp(week_start)) & (
            fs.index <= pd.Timestamp(week_end)
        )
        total = float(fs[mask].sum())
        label = f"{week_start.isoformat()} / {week_end.isoformat()}"
        weekly.append({"week": label, "forecast": round(total, 2)})
        week_start += timedelta(weeks=1)

    # ---- Monthly (next <=12 calendar months) ---------------------------- #
    monthly = []
    # First future month
    if today.month == 12:
        m_year, m_month = today.year + 1, 1
    else:
        m_year, m_month = today.year, today.month + 1

    for _ in range(12):
        month_start = pd.Timestamp(date(m_year, m_month, 1))
        # Last day of the month
        if m_month == 12:
            month_end = pd.Timestamp(date(m_year + 1, 1, 1)) - pd.Timedelta(days=1)
        else:
            month_end = pd.Timestamp(date(m_year, m_month + 1, 1)) - pd.Timedelta(
                days=1
            )

        mask = (fs.index >= month_start) & (fs.index <= month_end)
        total = float(fs[mask].sum())
        label = f"{m_year}-{m_month:02d}"
        monthly.append({"month": label, "forecast": round(total, 2)})

        m_month += 1
        if m_month > 12:
            m_month = 1
            m_year += 1

    # ---- Yearly (>=1 full year within the 365-day window) --------------- #
    yearly = []
    y_start = pd.Timestamp(date(today.year + 1, 1, 1))
    y_end = pd.Timestamp(date(today.year + 1, 12, 31))

    mask = (fs.index >= y_start) & (fs.index <= y_end)
    if mask.any():
        total = float(fs[mask].sum())
        yearly.append({"year": str(today.year + 1), "forecast": round(total, 2)})

    # If none fell in next full year (shouldn't happen with 365 days but guard)
    if not yearly:
        total = float(fs.sum())
        yearly.append({"year": str(today.year + 1), "forecast": round(total, 2)})

    return {
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "yearly": yearly,
    }
