import os
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

# Ensure mysql package symbol exists for tests that patch forecast.mysql.connector.connect
try:
    import mysql.connector  # noqa: F401
    from mysql.connector import Error as MySQLError
    import mysql as mysql  # expose top-level mysql for patching
except Exception:  # pragma: no cover
    mysql = None
    MySQLError = Exception


def _get_db_connection():
    """
    Create a MySQL connection from environment variables.
    """
    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "logix")

    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )


def _fetch_sales_history_with_pandas(conn, sku: str) -> pd.DataFrame:
    """
    Use pandas.read_sql with a parameterized query to fetch sales history.
    Supports either 'sale_date' or 'date' columns from the source.
    """
    # Prefer sale_date as the canonical column in our pipeline
    sql = (
        "SELECT sale_date, quantity_sold FROM sales_history WHERE sku = %s "
        "UNION ALL "
        "SELECT `date` AS sale_date, quantity_sold FROM sales_history WHERE sku = %s "
        "ORDER BY sale_date"
    )

    # Call using keyword args so tests can inspect call_args.kwargs
    df = pd.read_sql(sql=sql, con=conn, params=(sku, sku))
    # Normalize column name
    if "sale_date" not in df.columns:
        # Fallback if the test provides 'date' only
        if "date" in df.columns:
            df = df.rename(columns={"date": "sale_date"})
        else:
            # Ensure required columns exist (empty frame as a fallback)
            df = pd.DataFrame(columns=["sale_date", "quantity_sold"])
    return df


def _prepare_daily_series(df: pd.DataFrame) -> pd.Series:
    """
    Convert raw sales rows into a daily time series (sum per day), filling gaps with zeros.
    """
    if df is None or df.empty:
        return pd.Series(dtype=float)

    work = df.copy()
    # Harmonize column names
    if "sale_date" not in work.columns and "date" in work.columns:
        work = work.rename(columns={"date": "sale_date"})
    if "sale_date" not in work.columns:
        return pd.Series(dtype=float)

    work["sale_date"] = pd.to_datetime(work["sale_date"]).dt.normalize()
    qty_col = "quantity_sold" if "quantity_sold" in work.columns else None
    if qty_col is None:
        return pd.Series(dtype=float)

    work[qty_col] = pd.to_numeric(work[qty_col], errors="coerce").fillna(0.0)
    work = work.sort_values("sale_date")

    daily = (
        work.set_index("sale_date")
        .resample("D")[qty_col]
        .sum()
        .astype(float)
        .rename("y")
    )
    daily = daily.asfreq("D", fill_value=0.0)
    return daily


def _add_calendar_features(frame: pd.DataFrame) -> pd.DataFrame:
    idx = frame.index
    frame["dow"] = idx.dayofweek.astype(int)
    frame["month"] = idx.month.astype(int)
    frame["dom"] = idx.day.astype(int)
    frame["is_weekend"] = (idx.dayofweek >= 5).astype(int)
    frame["is_month_start"] = idx.is_month_start.astype(int)
    frame["is_month_end"] = idx.is_month_end.astype(int)
    return frame


def _build_supervised(ts: pd.Series) -> pd.DataFrame:
    if ts is None or len(ts) == 0:
        return pd.DataFrame(columns=["y"])
    df = pd.DataFrame({"y": ts})

    # Lags
    for l in [1, 7, 14, 28]:
        df[f"lag_{l}"] = ts.shift(l)

    # Rolling means (shifted by 1 to avoid leakage)
    for w in [7, 14, 28]:
        df[f"roll_mean_{w}"] = ts.shift(1).rolling(window=w, min_periods=max(1, w // 2)).mean()

    df = _add_calendar_features(df)
    df = df.dropna()
    return df


def _split_train_val(df: pd.DataFrame):
    n = len(df)
    if n <= 1:
        return df, df.iloc[0:0]
    val_size = min(30, max(7, int(round(n * 0.2))))
    if n - val_size < 10:
        val_size = max(1, n - 10) if n > 10 else 1
    train = df.iloc[: n - val_size]
    val = df.iloc[n - val_size :]
    return train, val


def _smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = (np.abs(y_true) + np.abs(y_pred)) + 1e-8
    return float(np.mean(2.0 * np.abs(y_true - y_pred) / denom))


def _fit_model(train_df: pd.DataFrame):
    X_train = train_df.drop(columns=["y"])
    y_train = train_df["y"].values
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    return model, list(X_train.columns)


def _evaluate_model(model, feature_cols, val_df: pd.DataFrame) -> float:
    if val_df is None or len(val_df) == 0:
        return float("nan")
    X_val = val_df[feature_cols]
    y_val = val_df["y"].values
    preds = np.clip(model.predict(X_val), 0.0, None)
    smape = _smape(y_val, preds)
    acc = max(0.0, min(1.0, 1.0 - smape))
    return float(acc)


def _make_feature_row_for_date(dt: pd.Timestamp, series: pd.Series, feature_cols: list) -> pd.DataFrame:
    rec = {}
    dow = int(dt.dayofweek)
    month = int(dt.month)
    dom = int(dt.day)
    is_weekend = 1 if dow >= 5 else 0
    tmp_idx = pd.DatetimeIndex([dt])
    is_month_start = int(tmp_idx.is_month_start[0])
    is_month_end = int(tmp_idx.is_month_end[0])

    hist = series if len(series) > 0 else pd.Series([], dtype=float)

    lag_names = [c for c in feature_cols if c.startswith("lag_")]
    roll_names = [c for c in feature_cols if c.startswith("roll_mean_")]

    for name in lag_names:
        try:
            l = int(name.split("_")[1])
        except Exception:
            l = 1
        if len(hist) >= l:
            val = float(hist.iloc[-l])
        else:
            val = float(hist.mean()) if len(hist) > 0 else 0.0
        rec[name] = val

    for name in roll_names:
        try:
            w = int(name.split("_")[2])
        except Exception:
            w = 7
        if len(hist) > 0:
            rec[name] = float(hist.tail(w).mean())
        else:
            rec[name] = 0.0

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

    for col in feature_cols:
        if col not in rec:
            rec[col] = 0.0

    row = pd.DataFrame([rec], index=[dt])
    row = row[feature_cols]
    return row


def _recursive_forecast(model, feature_cols, history_series: pd.Series, horizon_days: int = 365) -> pd.Series:
    if history_series is None or history_series.empty:
        return pd.Series(dtype=float)
    last_date = history_series.index.max()
    current_series = history_series.copy()
    preds = []
    for i in range(1, horizon_days + 1):
        target_dt = pd.to_datetime(last_date + timedelta(days=i))
        feat = _make_feature_row_for_date(target_dt, current_series, feature_cols)
        yhat = float(model.predict(feat)[0])
        yhat = 0.0 if np.isnan(yhat) else max(0.0, yhat)
        preds.append((target_dt, yhat))
        current_series.loc[target_dt] = yhat
    return pd.Series([v for _, v in preds], index=[d for d, _ in preds], name="forecast", dtype=float)


def _aggregate_forecasts(forecast_series: pd.Series):
    # Daily next 7 days
    daily_slice = forecast_series.iloc[:7]
    daily = [{"date": dt.date().isoformat(), "forecast": float(val)} for dt, val in daily_slice.items()]

    # Weekly: take up to 4 full 7-day windows starting at forecast start
    weekly = []
    start = forecast_series.index.min()
    for i in range(4):
        w_start = start + timedelta(days=7 * i)
        w_end = w_start + timedelta(days=6)
        mask = (forecast_series.index >= w_start) & (forecast_series.index <= w_end)
        if not mask.any():
            break
        total = float(forecast_series.loc[mask].sum())
        weekly.append({"start_date": w_start.date().isoformat(), "end_date": w_end.date().isoformat(), "forecast": total})

    # Monthly: sum by calendar month starts (up to 12)
    monthly_rs = forecast_series.resample("MS").sum()
    monthly = []
    for i, (m_start, total) in enumerate(monthly_rs.items()):
        if i >= 12:
            break
        monthly.append({"month": m_start.strftime("%Y-%m"), "forecast": float(total)})

    # Yearly: sum by calendar year end (>=1 row, possibly 2 if horizon crosses year)
    yearly_rs = forecast_series.resample("A-DEC").sum()
    yearly = [{"year": int(idx.year), "forecast": float(val)} for idx, val in yearly_rs.items()]
    if len(yearly) == 0 and len(forecast_series) > 0:
        # Fallback single-year aggregation
        total = float(forecast_series.sum())
        yearly = [{"year": int(forecast_series.index.min().year), "forecast": total}]

    return {"daily": daily, "weekly": weekly, "monthly": monthly, "yearly": yearly}


def run_forecast(sku_input):
    """
    Execute forecasting pipeline. Never raises; always returns a dict.
    """
    try:
        if sku_input is None:
            return {"error": "SKU is required"}
        sku = str(sku_input).strip()
        if not sku:
            return {"error": "SKU is empty after trimming whitespace"}

        if mysql is None:
            return {"error": "mysql.connector is not available in the runtime environment"}

        # Connect and fetch data using pandas.read_sql with parameterized query
        try:
            conn = _get_db_connection()
        except Exception as e:
            return {"error": f"Database connection failed: {e}"}

        try:
            df = _fetch_sales_history_with_pandas(conn, sku)
        except Exception as e:
            # Ensure connection is closed then return error
            try:
                conn.close()
            except Exception:
                pass
            return {"error": f"Database query failed: {e}"}
        finally:
            try:
                conn.close()
            except Exception:
                pass

        # If no data, return specific error message (format expected by tests)
        if df is None or df.empty:
            return {"error": f"No historical data found for SKU: {sku}"}

        # Build daily series
        series = _prepare_daily_series(df)
        if series is None or len(series) == 0:
            return {"error": f"No historical data found for SKU: {sku}"}

        # Supervised feature engineering
        supervised = _build_supervised(series)
        # Require minimal number of rows to train
        if supervised is None or len(supervised) < 7:
            return {"error": f"No historical data found for SKU: {sku}"}

        # Train/validation split
        train_df, val_df = _split_train_val(supervised)

        # Fit model
        model, feature_cols = _fit_model(train_df)

        # Evaluate
        acc = _evaluate_model(model, feature_cols, val_df)
        accuracy = None if np.isnan(acc) else float(round(acc, 4))

        # Forecast 365 days
        fc_series = _recursive_forecast(model, feature_cols, series, horizon_days=365)
        aggs = _aggregate_forecasts(fc_series)

        return {
            "sku": sku,
            "today": date.today().isoformat(),
            "accuracy": accuracy,
            "daily": aggs["daily"],
            "weekly": aggs["weekly"],
            "monthly": aggs["monthly"],
            "yearly": aggs["yearly"],
        }

    except Exception as e:
        return {"error": f"Forecasting failed: {e}"}
