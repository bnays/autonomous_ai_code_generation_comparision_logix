import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector
import numpy as np
import pandas as pd
from mysql.connector import Error as MySQLError
from sklearn.ensemble import RandomForestRegressor


def _get_env(keys: List[str], default: Optional[str] = None) -> Optional[str]:
    for k in keys:
        v = os.environ.get(k)
        if v is not None and str(v).strip() != "":
            return v
    return default


def _get_db_config() -> Dict[str, Any]:
    host = _get_env(["LOGIX_DB_HOST", "MYSQL_HOST", "DB_HOST", "DATABASE_HOST"], "localhost")
    user = _get_env(["LOGIX_DB_USER", "MYSQL_USER", "DB_USER", "DATABASE_USER"], None)
    password = _get_env(["LOGIX_DB_PASSWORD", "MYSQL_PASSWORD", "DB_PASSWORD", "DATABASE_PASSWORD"], None)
    database = _get_env(["LOGIX_DB_NAME", "MYSQL_DATABASE", "MYSQL_DB", "DB_NAME", "DATABASE_NAME"], None)
    port_str = _get_env(["LOGIX_DB_PORT", "MYSQL_PORT", "DB_PORT", "DATABASE_PORT"], "3306")
    try:
        port = int(str(port_str))
    except Exception:
        port = 3306
    return {"host": host, "user": user, "password": password, "database": database, "port": port}


def _fetch_sales_history(sku: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    cfg = _get_db_config()
    required_keys = ["host", "user", "password", "database", "port"]
    if any(cfg.get(k) in (None, "") for k in required_keys):
        return None, "Database configuration is incomplete. Please set DB connection environment variables."

    conn = None
    cur = None
    try:
        conn = mysql.connector.connect(
            host=cfg["host"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            port=cfg["port"],
            connection_timeout=10,
        )
        cur = conn.cursor()
        query = """
            SELECT sale_date, quantity_sold
            FROM sales_history
            WHERE sku = %s
            ORDER BY sale_date ASC
        """
        cur.execute(query, (sku,))
        rows = cur.fetchall()
        if not rows:
            return None, f"No historical sales data found for SKU '{sku}'."

        df = pd.DataFrame(rows, columns=["sale_date", "quantity_sold"])
        # Normalize and clean
        df["sale_date"] = pd.to_datetime(df["sale_date"]).dt.date
        # Aggregate by date in case there are multiple entries per day
        df = df.groupby("sale_date", as_index=False)["quantity_sold"].sum()
        # Ensure numeric and non-negative
        df["quantity_sold"] = pd.to_numeric(df["quantity_sold"], errors="coerce").fillna(0.0).clip(lower=0.0)
        return df, None
    except MySQLError as e:
        return None, f"Database error: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error retrieving sales history: {str(e)}"
    finally:
        try:
            if cur is not None:
                cur.close()
        except Exception:
            pass
        try:
            if conn is not None and conn.is_connected():
                conn.close()
        except Exception:
            pass


def _daily_series(df: pd.DataFrame) -> pd.DataFrame:
    # Build a continuous daily time series from min to max sale_date
    start = df["sale_date"].min()
    end = df["sale_date"].max()
    idx = pd.date_range(start=start, end=end, freq="D")
    s = (
        df.set_index(pd.to_datetime(df["sale_date"]))["quantity_sold"]
        .asfreq("D")
        .reindex(idx)
        .fillna(0.0)
        .clip(lower=0.0)
    )
    daily = pd.DataFrame({"date": idx, "y": s.values})
    daily["date"] = pd.to_datetime(daily["date"])
    return daily


def _select_feature_windows(n_days: int) -> Tuple[List[int], List[int]]:
    # Choose lags and rolling windows based on available history
    if n_days >= 60:
        lags = [1, 2, 3, 7, 14, 21, 28]
        rolls = [7, 14, 28]
    elif n_days >= 28:
        lags = [1, 2, 3, 7, 14, 21]
        rolls = [7, 14]
    elif n_days >= 14:
        lags = [1, 2, 3, 7]
        rolls = [7]
    else:
        lags, rolls = [], []
    return lags, rolls


def _add_calendar_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    dti = pd.to_datetime(df[date_col])
    iso_calendar = dti.isocalendar()
    df = df.copy()
    df["day_of_week"] = dti.dt.dayofweek.astype(int)  # 0=Mon..6=Sun
    df["week_of_year"] = iso_calendar.week.astype(int)
    df["month"] = dti.dt.month.astype(int)
    df["day_of_month"] = dti.dt.day.astype(int)
    df["is_month_start"] = dti.dt.is_month_start.astype(int)
    df["is_month_end"] = dti.dt.is_month_end.astype(int)
    return df


def _build_training_frame(daily: pd.DataFrame, lags: List[int], rolls: List[int]) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    df = daily.copy()
    df = _add_calendar_features(df, "date")

    # Lag features
    for l in lags:
        df[f"lag_{l}"] = df["y"].shift(l)

    # Rolling means using only past values (shift by 1 to avoid leakage)
    for w in rolls:
        df[f"roll_mean_{w}"] = df["y"].shift(1).rolling(window=w, min_periods=w).mean()

    # Drop rows with NaNs due to lags/rollings
    feature_cols = (
        ["day_of_week", "week_of_year", "month", "day_of_month", "is_month_start", "is_month_end"]
        + [f"lag_{l}" for l in lags]
        + [f"roll_mean_{w}" for w in rolls]
    )
    df_model = df.dropna(subset=feature_cols + ["y"]).reset_index(drop=True)

    X = df_model[feature_cols].astype(float)
    y = df_model["y"].astype(float)
    return X, y, feature_cols


def _safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.maximum(1.0, np.abs(y_true))
    mape = np.mean(np.abs((y_true - y_pred) / denom))
    if np.isnan(mape) or np.isinf(mape):
        return 1.0
    return float(mape)


def _make_feature_row(
    next_dt: pd.Timestamp,
    history: List[float],
    lags: List[int],
    rolls: List[int],
) -> Dict[str, float]:
    # Calendar features
    dti = pd.to_datetime(next_dt)
    iso_cal = dti.isocalendar()
    feats = {
        "day_of_week": float(dti.dayofweek),
        "week_of_year": float(int(iso_cal.week)),
        "month": float(dti.month),
        "day_of_month": float(dti.day),
        "is_month_start": float(int(dti.is_month_start)),
        "is_month_end": float(int(dti.is_month_end)),
    }
    # Lag features
    n = len(history)
    for l in lags:
        val = history[-l] if l <= n else 0.0
        feats[f"lag_{l}"] = float(val)
    # Rolling means
    for w in rolls:
        if n >= w:
            feats[f"roll_mean_{w}"] = float(np.mean(history[-w:]))
        else:
            feats[f"roll_mean_{w}"] = float(np.mean(history)) if n > 0 else 0.0
    return feats


def _recursive_forecast(
    model: RandomForestRegressor,
    last_date: pd.Timestamp,
    history: List[float],
    lags: List[int],
    rolls: List[int],
    feature_cols: List[str],
    horizon_days: int = 365,
) -> List[Tuple[pd.Timestamp, float]]:
    preds: List[Tuple[pd.Timestamp, float]] = []
    hist = list(history)  # copy
    current_date = last_date
    for _ in range(horizon_days):
        next_date = current_date + pd.Timedelta(days=1)
        feat_map = _make_feature_row(next_date, hist, lags, rolls)
        # Ensure column order and presence
        X_row = np.array([[feat_map.get(col, 0.0) for col in feature_cols]], dtype=float)
        y_hat = float(model.predict(X_row)[0])
        y_hat = max(0.0, y_hat)  # no negative sales
        preds.append((next_date, y_hat))
        hist.append(y_hat)
        current_date = next_date
    return preds


def _aggregate_buckets(preds: List[Tuple[pd.Timestamp, float]]) -> Dict[str, List[Dict[str, Any]]]:
    # Daily: next 7 days
    daily7 = []
    for dt, val in preds[:7]:
        daily7.append({"date": dt.date().isoformat(), "quantity": float(val)})

    # Weekly: up to 4 weeks (chunks of 7 days sequentially)
    weekly = []
    for i in range(0, min(28, len(preds)), 7):
        chunk = preds[i : i + 7]
        if not chunk:
            break
        start_dt = chunk[0][0].date()
        end_dt = chunk[-1][0].date()
        total = float(np.sum([v for _, v in chunk]))
        weekly.append(
            {
                "week_start": start_dt.isoformat(),
                "week_end": end_dt.isoformat(),
                "quantity": total,
            }
        )
        if len(weekly) >= 4:
            break

    # Monthly: group by calendar month within horizon
    dfp = pd.DataFrame({"date": [dt for dt, _ in preds], "quantity": [v for _, v in preds]})
    dfp["year"] = dfp["date"].dt.year
    dfp["month"] = dfp["date"].dt.month
    monthly_list = []
    for (yy, mm), grp in dfp.groupby(["year", "month"], sort=True):
        start_dt = grp["date"].min().date()
        end_dt = grp["date"].max().date()
        total = float(grp["quantity"].sum())
        monthly_list.append(
            {
                "year": int(yy),
                "month": int(mm),
                "start_date": start_dt.isoformat(),
                "end_date": end_dt.isoformat(),
                "quantity": total,
            }
        )
    # Limit to 12 months
    monthly_list = monthly_list[:12]

    # Yearly: aggregate by calendar year in horizon
    yearly_list = []
    for yy, grp in dfp.groupby(dfp["date"].dt.year, sort=True):
        total = float(grp["quantity"].sum())
        start_dt = grp["date"].min().date()
        end_dt = grp["date"].max().date()
        yearly_list.append(
            {
                "year": int(yy),
                "start_date": start_dt.isoformat(),
                "end_date": end_dt.isoformat(),
                "quantity": total,
            }
        )

    return {"daily": daily7, "weekly": weekly, "monthly": monthly_list, "yearly": yearly_list}


def run_forecast(sku_input: Any) -> Dict[str, Any]:
    try:
        sku = "" if sku_input is None else str(sku_input).strip()
        if not sku:
            return {"error": "SKU is required."}

        # Fetch data
        df_raw, err = _fetch_sales_history(sku)
        if err:
            return {"error": err}

        # Prepare daily series
        daily = _daily_series(df_raw)
        n_days = len(daily)
        if n_days < 14:
            return {"error": f"Insufficient historical data to train forecast for SKU '{sku}' (need at least 14 daily records)."}

        # Feature selection based on history depth
        lags, rolls = _select_feature_windows(n_days)
        if not lags:
            return {"error": f"Insufficient historical data to engineer lag/rolling features for SKU '{sku}'."}

        # Build training data
        X, y, feature_cols = _build_training_frame(daily, lags, rolls)
        if len(X) < 2:
            return {"error": f"Insufficient feature rows after preprocessing for SKU '{sku}'."}

        # Train/test split (use last ~20% or up to 30 days as test)
        test_size = max(1, min(30, int(round(0.2 * len(X)))))
        if len(X) <= test_size:
            test_size = 1  # ensure at least one train sample if possible
        split_idx = len(X) - test_size
        if split_idx < 1:
            return {"error": f"Not enough data to split train/test for SKU '{sku}'."}

        X_train, y_train = X.iloc[:split_idx], y.iloc[:split_idx]
        X_test, y_test = X.iloc[split_idx:], y.iloc[split_idx:]

        # Train model
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)

        # Evaluate accuracy
        if len(X_test) >= 1:
            y_pred = model.predict(X_test)
            mape = _safe_mape(y_test.values, y_pred)
            accuracy = float(max(0.0, 1.0 - mape))
        else:
            accuracy = None

        # Recursive forecast 365 days ahead
        last_date = pd.to_datetime(daily["date"].max())
        history_vals = daily["y"].astype(float).tolist()
        preds = _recursive_forecast(
            model=model,
            last_date=last_date,
            history=history_vals,
            lags=lags,
            rolls=rolls,
            feature_cols=feature_cols,
            horizon_days=365,
        )

        # Aggregate into requested buckets
        agg = _aggregate_buckets(preds)

        result = {
            "sku": sku,
            "today": date.today().isoformat(),
            "accuracy": None if accuracy is None else round(accuracy, 4),
            "forecast": agg,
        }
        return result
    except Exception as e:
        # Ensure we never raise; always return an error dict.
        return {"error": f"Forecasting failed: {str(e)}"}
