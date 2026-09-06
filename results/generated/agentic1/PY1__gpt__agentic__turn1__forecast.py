import os
import sys
import math
import traceback
from datetime import datetime, timedelta, date

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except Exception:  # pragma: no cover
    mysql = None
    MySQLError = Exception


def _get_db_connection():
    """
    Create a MySQL connection from environment variables.
    Expected env vars:
      - MYSQL_HOST (default: localhost)
      - MYSQL_PORT (default: 3306)
      - MYSQL_USER (default: root)
      - MYSQL_PASSWORD (default: empty)
      - MYSQL_DATABASE (default: logix)
    """
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "logix"),
            autocommit=False,
        )
        return conn
    except Exception as e:
        raise MySQLError(f"Failed to connect to MySQL: {e}") from e


def _fetch_sales_history(sku: str):
    """
    Fetch sales history for a given SKU from MySQL.
    Returns a pandas DataFrame with columns: ['sale_date', 'quantity_sold'].
    Raises only locally; caller should capture and convert to error dict.
    """
    conn = None
    try:
        conn = _get_db_connection()
        query = """
            SELECT sale_date, quantity_sold
            FROM sales_history
            WHERE sku = %s
            ORDER BY sale_date
        """
        df = None
        with conn.cursor() as cur:
            cur.execute(query, (sku,))
            rows = cur.fetchall()
            if not rows:
                return pd.DataFrame(columns=["sale_date", "quantity_sold"])
            df = pd.DataFrame(rows, columns=["sale_date", "quantity_sold"])
        return df
    finally:
        try:
            if conn is not None and conn.is_connected():
                conn.close()
        except Exception:
            pass


def _prepare_daily_series(df: pd.DataFrame) -> pd.Series:
    """
    Convert raw sales rows into a daily time series (sum per day), filling gaps with zeros.
    """
    df = df.copy()
    df["sale_date"] = pd.to_datetime(df["sale_date"]).dt.normalize()
    df = df.sort_values("sale_date")
    # Ensure numeric
    df["quantity_sold"] = pd.to_numeric(df["quantity_sold"], errors="coerce").fillna(0.0)
    # Resample to daily frequency
    daily = (
        df.set_index("sale_date")
        .resample("D")["quantity_sold"]
        .sum()
        .astype(float)
        .rename("y")
    )
    daily = daily.asfreq("D", fill_value=0.0)
    return daily


def _add_calendar_features(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Adds calendar-based features given DateTimeIndex.
    """
    idx = frame.index
    frame["dow"] = idx.dayofweek.astype(int)  # 0-6
    frame["month"] = idx.month.astype(int)    # 1-12
    frame["dom"] = idx.day.astype(int)        # 1-31
    frame["is_weekend"] = ((frame["dow"] >= 5).astype(int))
    frame["is_month_start"] = idx.is_month_start.astype(int)
    frame["is_month_end"] = idx.is_month_end.astype(int)
    return frame


def _build_supervised(ts: pd.Series) -> pd.DataFrame:
    """
    Build a supervised learning frame with lag and rolling features.
    """
    df = pd.DataFrame({"y": ts.copy()})
    # Lags
    lags = [1, 7, 14, 28]
    for l in lags:
        df[f"lag_{l}"] = ts.shift(l)

    # Rolling means (shifted by 1 to avoid leakage)
    wins = [7, 14, 28]
    for w in wins:
        df[f"roll_mean_{w}"] = ts.shift(1).rolling(window=w, min_periods=max(1, w // 2)).mean()

    df = _add_calendar_features(df)
    df = df.dropna()
    return df


def _split_train_val(df: pd.DataFrame):
    """
    Split into train and validation sets, preferring up to 30 days for validation.
    """
    n = len(df)
    if n <= 1:
        return df, df.iloc[0:0]

    # target y is in 'y'
    val_size = min(30, max(7, int(round(n * 0.2))))
    # Ensure at least 10 in train if possible
    if n - val_size < 10:
        val_size = max(1, n - 10) if n > 10 else 1

    train = df.iloc[: n - val_size]
    val = df.iloc[n - val_size :]
    return train, val


def _smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Symmetric Mean Absolute Percentage Error (sMAPE).
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = (np.abs(y_true) + np.abs(y_pred)) + 1e-8
    return float(np.mean(2.0 * np.abs(y_true - y_pred) / denom))


def _fit_model(train_df: pd.DataFrame):
    """
    Fit RandomForestRegressor on the training data.
    Returns model and feature columns list.
    """
    X_train = train_df.drop(columns=["y"])
    y_train = train_df["y"].values
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    return model, list(X_train.columns)


def _evaluate_model(model, feature_cols, val_df: pd.DataFrame) -> float:
    """
    Evaluate model on validation set returning accuracy (1 - sMAPE), clipped to [0,1].
    Returns np.nan if val_df is empty.
    """
    if val_df is None or len(val_df) == 0:
        return float("nan")
    X_val = val_df[feature_cols]
    y_val = val_df["y"].values
    preds = np.clip(model.predict(X_val), 0.0, None)
    smape = _smape(y_val, preds)
    acc = max(0.0, min(1.0, 1.0 - smape))
    return float(acc)


def _make_feature_row_for_date(dt: pd.Timestamp, series: pd.Series, feature_cols: list) -> pd.DataFrame:
    """
    Construct a single-row DataFrame of features for a given date, based on the known history series.
    The feature names should match training feature_cols.
    """
    rec = {}
    # Calendar features
    dow = int(dt.dayofweek)
    month = int(dt.month)
    dom = int(dt.day)
    is_weekend = 1 if dow >= 5 else 0
    # For month start/end use pandas flags
    tmp_idx = pd.DatetimeIndex([dt])
    is_month_start = int(tmp_idx.is_month_start[0])
    is_month_end = int(tmp_idx.is_month_end[0])

    # Precompute for speed
    series_nonempty = series if len(series) > 0 else pd.Series([0.0])

    # Lags and rolling means
    # Define expected lags/wins to compute; model may not use all, but compute to be safe
    lag_names = [c for c in feature_cols if c.startswith("lag_")]
    roll_names = [c for c in feature_cols if c.startswith("roll_mean_")]

    # Compute lag features
    for name in lag_names:
        try:
            l = int(name.split("_")[1])
        except Exception:
            l = 1
        if len(series_nonempty) >= l:
            val = float(series_nonempty.iloc[-l])
        else:
            # Fallback to mean of available history (or zero)
            val = float(series_nonempty.mean()) if len(series_nonempty) > 0 else 0.0
        rec[name] = val

    # Compute rolling means using last w actuals
    for name in roll_names:
        try:
            w = int(name.split("_")[2])
        except Exception:
            w = 7
        if len(series_nonempty) >= 1:
            window_vals = series_nonempty.tail(w)
            rec[name] = float(window_vals.mean())
        else:
            rec[name] = 0.0

    # Calendar feature names must match training
    rec.update(
        {
            "dow": dow,
            "month": month,
            "dom": dom,
            "is_weekend": is_weekend,
            "is_month_start": is_month_start,
            "is_month_end": is_month_end,
        }
    )

    # Ensure all feature columns exist, fill missing with 0
    for col in feature_cols:
        if col not in rec:
            rec[col] = 0.0

    row = pd.DataFrame([rec], index=[dt])
    # Align column order
    row = row[feature_cols]
    return row


def _recursive_forecast(model, feature_cols, history_series: pd.Series, horizon_days: int = 365) -> pd.Series:
    """
    Produce recursive daily forecasts for the given horizon.
    Returns a pandas Series indexed by forecast dates with predicted values.
    """
    # Ensure copy
    hist = history_series.copy()
    forecasts = []

    last_date = hist.index.max()
    current_series = hist.copy()

    for i in range(1, horizon_days + 1):
        target_date = last_date + timedelta(days=i)
        feat_row = _make_feature_row_for_date(pd.to_datetime(target_date), current_series, feature_cols)
        yhat = model.predict(feat_row)[0]
        # Clip to non-negative
        yhat = 0.0 if (yhat is None or np.isnan(yhat)) else max(0.0, float(yhat))
        forecasts.append((target_date, yhat))
        # Append prediction to series for subsequent lags/rolling computations
        current_series.loc[target_date] = yhat

    forecast_series = pd.Series(
        [v for _, v in forecasts],
        index=pd.to_datetime([d for d, _ in forecasts]),
        name="forecast",
        dtype=float,
    )
    return forecast_series


def _aggregate_forecasts(forecast_series: pd.Series):
    """
    Aggregate the forecast series into daily (7 rows), weekly (<=4), monthly (<=12), yearly (>=1).
    Returns dict with lists of dicts for each aggregation level.
    """
    # Daily: next 7 days
    daily_slice = forecast_series.iloc[:7]
    daily = [
        {"date": dt.date().isoformat(), "forecast": float(val)}
        for dt, val in daily_slice.items()
    ]

    # Weekly: sum by ISO weeks aligned to Monday
    weekly_rs = forecast_series.resample("W-MON").sum()
    weekly = []
    for i, (week_start, total) in enumerate(weekly_rs.items()):
        if i >= 4:
            break
        start_date = pd.to_datetime(week_start).date()
        end_date = start_date + timedelta(days=6)
        weekly.append(
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "forecast": float(total),
            }
        )

    # Monthly: sum by month start
    monthly_rs = forecast_series.resample("MS").sum()
    monthly = []
    for i, (month_start, total) in enumerate(monthly_rs.items()):
        if i >= 12:
            break
        monthly.append({"month": month_start.strftime("%Y-%m"), "forecast": float(total)})

    # Yearly: sum by calendar year end
    yearly_rs = forecast_series.resample("A-DEC").sum()
    yearly = []
    for (year_end, total) in yearly_rs.items():
        y = int(pd.to_datetime(year_end).year)
        yearly.append({"year": y, "forecast": float(total)})

    return {
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "yearly": yearly,
    }


def run_forecast(sku_input):
    """
    Runs the forecast pipeline for a given SKU:
      - Connects to MySQL and fetches sales history for the SKU (whitespace-trimmed).
      - Returns {'error': ...} if DB fails or if no history for SKU.
      - Engineers lag/rolling features, trains RandomForestRegressor(n_estimators=100, random_state=42).
      - Produces a recursive 365-day forecast.
      - Aggregates into daily (7 rows), weekly (<=4 rows), monthly (<=12 rows), and yearly (>=1 row) buckets.
      - Returns dict with sku, accuracy, today, and aggregated forecasts.

    This function never raises; it always returns a dict.
    """
    try:
        if mysql is None:
            return {"error": "mysql.connector is not available in the runtime environment"}

        if sku_input is None:
            return {"error": "SKU is required"}

        sku = str(sku_input).strip()
        if not sku:
            return {"error": "SKU is empty after trimming whitespace"}

        # Fetch data
        try:
            raw_df = _fetch_sales_history(sku)
        except MySQLError as e:
            return {"error": f"Database connection failed: {e}"}
        except Exception as e:
            return {"error": f"Database query failed: {e}"}

        if raw_df is None or raw_df.empty:
            return {"error": f"No historical data found for SKU '{sku}'"}

        # Prepare daily series
        series = _prepare_daily_series(raw_df)

        # Build supervised dataset
        supervised = _build_supervised(series)

        # Check for sufficient data
        if supervised is None or len(supervised) < 20:
            return {"error": f"Not enough historical data to train a model for SKU '{sku}'"}

        # Train/validation split
        train_df, val_df = _split_train_val(supervised)

        # Train model
        model, feature_cols = _fit_model(train_df)

        # Evaluate accuracy
        accuracy = _evaluate_model(model, feature_cols, val_df)
        if accuracy != accuracy or np.isnan(accuracy):  # NaN check
            accuracy = None
        else:
            # Round to 4 decimals
            accuracy = float(round(accuracy, 4))

        # Forecast 365 days ahead
        forecast_series = _recursive_forecast(model, feature_cols, series, horizon_days=365)

        # Aggregate
        aggs = _aggregate_forecasts(forecast_series)

        result = {
            "sku": sku,
            "today": date.today().isoformat(),
            "accuracy": accuracy,
            "daily": aggs["daily"],
            "weekly": aggs["weekly"],
            "monthly": aggs["monthly"],
            "yearly": aggs["yearly"],
        }
        return result

    except Exception as e:
        # Never raise; always return an error dict
        # Optionally include minimal traceback info for debugging
        msg = f"Forecasting failed: {e}"
        try:
            tb = traceback.format_exc(limit=1)
            if tb:
                msg = f"{msg}"
        except Exception:
            pass
        return {"error": msg}
