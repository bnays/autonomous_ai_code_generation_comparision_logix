import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

try:
    import mysql.connector  # noqa: F401
    import mysql as mysql  # ensure patch path forecast.mysql.connector.connect works
except Exception:  # pragma: no cover
    mysql = None

from sklearn.ensemble import RandomForestRegressor


def _get_env(keys, default=None):
    for k in keys:
        v = os.environ.get(k)
        if v is not None and v != "":
            return v
    return default


def _smape(y_true, y_pred, eps=1e-8):
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    denom = (np.abs(y_true) + np.abs(y_pred)) + eps
    smape_vals = 2.0 * np.abs(y_pred - y_true) / denom
    smape = np.mean(smape_vals) if len(smape_vals) else 1.0
    accuracy = 1.0 - smape
    return float(max(0.0, min(1.0, accuracy)))


def _create_features(df, max_lag=28):
    """
    Given a DataFrame with index as daily DatetimeIndex and a 'quantity_sold' column,
    return a feature DataFrame X and target y after creating lag/rolling features.
    """
    data = df.copy()

    # Calendar features
    data["dow"] = data.index.dayofweek
    data["month"] = data.index.month
    data["day"] = data.index.day
    data["dayofyear"] = data.index.dayofyear
    data["is_weekend"] = (data["dow"] >= 5).astype(int)

    # Lags
    for lag in [1, 7, 14, 28]:
        data[f"lag_{lag}"] = data["quantity_sold"].shift(lag)

    # Rolling means
    data["roll_mean_7"] = data["quantity_sold"].shift(1).rolling(window=7, min_periods=1).mean()
    data["roll_mean_28"] = data["quantity_sold"].shift(1).rolling(window=28, min_periods=1).mean()

    # Drop rows where any lag is NaN (due to shifting)
    data = data.dropna()

    feature_cols = [
        "dow",
        "month",
        "day",
        "dayofyear",
        "is_weekend",
        "lag_1",
        "lag_7",
        "lag_14",
        "lag_28",
        "roll_mean_7",
        "roll_mean_28",
    ]
    X = data[feature_cols]
    y = data["quantity_sold"]
    return X, y, feature_cols


def _build_connection():
    host = _get_env(["MYSQL_HOST", "DB_HOST"], "localhost")
    port = int(_get_env(["MYSQL_PORT", "DB_PORT"], 3306))
    user = _get_env(["MYSQL_USER", "DB_USER"], "root")
    password = _get_env(["MYSQL_PASSWORD", "DB_PASSWORD"], "")
    database = _get_env(["MYSQL_DATABASE", "DB_NAME", "MYSQL_DB", "DB_DATABASE"], None)

    if mysql is None:
        raise RuntimeError("mysql-connector not available in environment")

    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        autocommit=True,
    )


def run_forecast(sku_input):
    """
    Connects to MySQL, fetches daily sales history for the given SKU, engineers lag/rolling
    features, trains a RandomForestRegressor, and produces a 365-day recursive forecast.

    Returns a dict with:
    - sku
    - today
    - accuracy
    - daily: next 7 days (7 rows)
    - weekly: next up to 4 weeks (<=4 rows)
    - monthly: next up to 12 months (<=12 rows)
    - yearly: aggregated by calendar year (>=1 row)

    On failure or if no data exists: {'error': '...'}
    """
    try:
        sku = (sku_input or "").strip()
        if not sku:
            return {"error": "SKU is required."}

        try:
            conn = _build_connection()
        except Exception as e:
            return {"error": f"Database connection failed: {e}"}

        # Use pandas read_sql with parameterized query and trimmed SKU
        try:
            sql = """
                SELECT DATE(sale_date) AS date,
                       quantity_sold
                FROM sales_history
                WHERE sku = %s
                ORDER BY date ASC
            """
            # tests expect params to be a list containing the trimmed SKU
            df = pd.read_sql(sql=sql, con=conn, params=[sku], parse_dates=["date"])
        except Exception as e:
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

        if df is None or df.empty:
            return {"error": f"No historical data found for SKU: {sku}"}

        # Ensure expected columns exist
        cols = set(df.columns.str.lower())
        if not (("date" in cols) and ("quantity_sold" in cols)):
            return {"error": "Unexpected database schema: required columns missing."}

        # Normalize and aggregate by date
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df["date"] = df["date"].dt.normalize()
        df["quantity_sold"] = pd.to_numeric(df["quantity_sold"], errors="coerce").fillna(0.0)
        df["quantity_sold"] = df["quantity_sold"].clip(lower=0.0)

        # Aggregate in case multiple records per day
        daily = (
            df.groupby("date", as_index=True)["quantity_sold"]
            .sum()
            .sort_index()
            .to_frame()
        )

        # Ensure continuous daily index
        full_index = pd.date_range(start=daily.index.min(), end=daily.index.max(), freq="D")
        daily = daily.reindex(full_index).fillna(0.0)
        daily.index.name = "date"

        # Feature engineering
        X_all, y_all, feature_cols = _create_features(daily, max_lag=28)

        # If we cannot form features (very short history), we will fall back later
        can_fit = len(X_all) > 0

        accuracy = 0.0
        rf_full = None

        if can_fit:
            # Time-based split
            N = len(X_all)
            test_days = min(30, max(1, int(round(0.2 * N))))
            split_idx = max(1, N - test_days)
            X_train, y_train = X_all.iloc[:split_idx], y_all.iloc[:split_idx]
            X_test, y_test = X_all.iloc[split_idx:], y_all.iloc[split_idx:]

            # Train
            rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
            rf.fit(X_train, y_train)

            # Evaluate
            try:
                preds_test = rf.predict(X_test) if len(X_test) > 0 else np.array([])
                accuracy = _smape(y_test.values, preds_test) if len(preds_test) > 0 else 0.0
            except Exception:
                accuracy = 0.0

            # Refit on all available feature rows
            try:
                rf_full = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
                rf_full.fit(X_all, y_all)
            except Exception:
                rf_full = rf

        # Recursive 365-day forecast
        history = daily["quantity_sold"].astype(float).tolist()
        last_date = daily.index.max().date()
        future_dates = [last_date + timedelta(days=i) for i in range(1, 366)]

        preds = []
        for d in future_dates:
            if not can_fit:
                # Fallback: naive forecast using last observed value
                yhat = float(history[-1]) if len(history) > 0 else 0.0
                yhat = max(0.0, yhat)
                preds.append((d, yhat))
                history.append(yhat)
                continue

            # Calendar features
            dt = pd.Timestamp(d)
            dow = dt.dayofweek
            month = dt.month
            day = dt.day
            dayofyear = dt.dayofyear
            is_weekend = 1 if dow >= 5 else 0

            # Lags from current history
            def lag_val(lag):
                if len(history) >= lag:
                    return history[-lag]
                else:
                    return float(np.mean(history)) if len(history) > 0 else 0.0

            lag_1 = lag_val(1)
            lag_7 = lag_val(7)
            lag_14 = lag_val(14)
            lag_28 = lag_val(28)

            # Rolling means using available history
            def rolling_mean(window):
                if len(history) == 0:
                    return 0.0
                w = int(window)
                start_idx = max(0, len(history) - w)
                return float(np.mean(history[start_idx:]))

            roll_mean_7 = rolling_mean(7)
            roll_mean_28 = rolling_mean(28)

            row = pd.DataFrame(
                {
                    "dow": [dow],
                    "month": [month],
                    "day": [day],
                    "dayofyear": [dayofyear],
                    "is_weekend": [is_weekend],
                    "lag_1": [lag_1],
                    "lag_7": [lag_7],
                    "lag_14": [lag_14],
                    "lag_28": [lag_28],
                    "roll_mean_7": [roll_mean_7],
                    "roll_mean_28": [roll_mean_28],
                }
            )
            row = row[feature_cols]
            try:
                yhat = float(rf_full.predict(row)[0]) if rf_full is not None else float(history[-1])
            except Exception:
                yhat = float(history[-1]) if len(history) > 0 else 0.0
            yhat = max(0.0, yhat)
            preds.append((d, yhat))
            history.append(yhat)

        # Build forecast DataFrame
        fc_df = pd.DataFrame(preds, columns=["date", "forecast"])
        fc_df["date"] = pd.to_datetime(fc_df["date"])

        # Aggregations
        # Daily: next 7 days
        daily_rows = [
            {"date": r["date"].date().isoformat(), "predicted_sales": float(r["forecast"])}
            for _, r in fc_df.head(7).iterrows()
        ]

        # Weekly: next up to 4 consecutive 7-day windows
        weekly_rows = []
        for k in range(4):
            start_idx = k * 7
            end_idx = start_idx + 7
            window = fc_df.iloc[start_idx:end_idx]
            if len(window) == 0:
                break
            weekly_rows.append(
                {
                    "start_date": window["date"].iloc[0].date().isoformat(),
                    "end_date": window["date"].iloc[-1].date().isoformat(),
                    "predicted_sales": float(window["forecast"].sum()),
                }
            )

        # Monthly: group by calendar month, take up to 12
        fc_df["year"] = fc_df["date"].dt.year
        fc_df["month"] = fc_df["date"].dt.month
        monthly_group = (
            fc_df.groupby(["year", "month"], as_index=False)["forecast"]
            .sum()
            .sort_values(["year", "month"])
        )
        monthly_rows = [
            {"month": f"{int(r['year']):04d}-{int(r['month']):02d}", "predicted_sales": float(r["forecast"])}
            for _, r in monthly_group.head(12).iterrows()
        ]

        # Yearly: aggregated by calendar year present in the forecast horizon
        yearly_series = fc_df.groupby(fc_df["date"].dt.year)["forecast"].sum()
        yearly_rows = [{"year": str(int(y)), "predicted_sales": float(val)} for y, val in yearly_series.items()]

        result = {
            "sku": sku,
            "today": date.today().isoformat(),
            "accuracy": float(accuracy),
            "daily": daily_rows,
            "weekly": weekly_rows,
            "monthly": monthly_rows,
            "yearly": yearly_rows,
        }
        return result

    except Exception as e:
        # Ensure this function never raises
        return {"error": f"Forecasting failed: {e}"}
