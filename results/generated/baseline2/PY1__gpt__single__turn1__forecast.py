import os
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from pandas.tseries.offsets import MonthEnd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

try:
    import mysql.connector
except Exception:  # pragma: no cover
    mysql = None  # Will handle in run_forecast by returning an error


def _connect_mysql():
    """
    Create a MySQL connection using environment variables:
      DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
    """
    if mysql is None:
        raise RuntimeError("mysql.connector is not available")

    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "")

    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        autocommit=False,
    )


def _fetch_sales_history(cnx, sku):
    """
    Fetch sale_date and quantity_sold for the given SKU from sales_history.
    Returns a pandas DataFrame with columns: ['sale_date', 'quantity_sold'].
    """
    query = """
        SELECT sale_date, quantity_sold
        FROM sales_history
        WHERE sku = %s
        ORDER BY sale_date ASC
    """
    cur = cnx.cursor()
    try:
        cur.execute(query, (sku,))
        rows = cur.fetchall()
        if not rows:
            return pd.DataFrame(columns=["sale_date", "quantity_sold"])
        df = pd.DataFrame(rows, columns=["sale_date", "quantity_sold"])
        return df
    finally:
        cur.close()


def _prepare_time_series(df_raw):
    """
    Prepare a continuous daily time series from raw df with columns: sale_date, quantity_sold.
    Returns a DataFrame indexed by date with a single column 'y' (quantity).
    """
    df = df_raw.copy()
    # Coerce dates and quantities
    df["sale_date"] = pd.to_datetime(df["sale_date"]).dt.normalize()
    df["quantity_sold"] = pd.to_numeric(df["quantity_sold"], errors="coerce").fillna(0.0)

    # Aggregate in case multiple records per day
    daily = df.groupby("sale_date", as_index=True)["quantity_sold"].sum().sort_index()

    # Reindex to ensure continuous daily series (fill missing with 0)
    full_range = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily_full = daily.reindex(full_range, fill_value=0.0)
    daily_full.index.name = "date"

    return pd.DataFrame({"y": daily_full})


def _add_features(df):
    """
    Add lag and rolling features to the time series df with index 'date' and column 'y'.
    Returns a new dataframe with feature columns and target 'y'.
    """
    out = df.copy()
    # Time-based calendar features
    out["dow"] = out.index.dayofweek.astype(int)  # 0=Mon
    out["dom"] = out.index.day.astype(int)
    out["month"] = out.index.month.astype(int)
    out["is_month_start"] = out.index.is_month_start.astype(int)
    out["is_month_end"] = out.index.is_month_end.astype(int)

    # Lags
    for lag in [1, 7, 14, 28]:
        out[f"lag_{lag}"] = out["y"].shift(lag)

    # Rolling means (shifted by 1 to avoid leakage)
    for win in [7, 14, 28]:
        out[f"rmean_{win}"] = out["y"].shift(1).rolling(window=win, min_periods=1).mean()

    # Drop initial rows with NaNs from lags to ensure consistent training
    needed_cols = [c for c in out.columns if c != "y"]
    out = out.dropna(subset=[c for c in needed_cols if c.startswith("lag_")])
    return out


def _compute_features_for_date(series_y, target_dt):
    """
    Compute a single feature row for the given target date using past 'series_y' (pd.Series indexed by date).
    Assumes series_y contains continuous daily history up to target_dt - 1.
    Returns a dict of features in the same shape as training.
    """
    # Calendar features
    feats = {
        "dow": target_dt.weekday(),
        "dom": target_dt.day,
        "month": target_dt.month,
        "is_month_start": int(target_dt.day == 1),
        "is_month_end": int((target_dt + timedelta(days=1)).day == 1),
    }

    # Lags from past actual/predicted series
    def get_lag(days):
        past_dt = target_dt - timedelta(days=days)
        return float(series_y.get(past_dt, 0.0))

    for lag in [1, 7, 14, 28]:
        feats[f"lag_{lag}"] = get_lag(lag)

    # Rolling means: mean of previous k days
    def rolling_mean(k):
        start_dt = target_dt - timedelta(days=k)
        end_dt = target_dt - timedelta(days=1)
        window = series_y.loc[(series_y.index >= start_dt) & (series_y.index <= end_dt)]
        if len(window) == 0:
            return 0.0
        return float(window.mean())

    for win in [7, 14, 28]:
        feats[f"rmean_{win}"] = rolling_mean(win)

    return feats


def _to_float(x):
    try:
        return float(x)
    except Exception:
        return float(np.nan)


def run_forecast(sku_input):
    """
    Main entrypoint.
    - Connects to MySQL and fetches historical daily sales for the given SKU.
    - Engineers lag/rolling features.
    - Trains RandomForestRegressor(n_estimators=100, random_state=42).
    - Produces a recursive 365-day forecast.
    - Aggregates forecast into:
        daily (7 rows),
        weekly (<=4 rows),
        monthly (<=12 rows),
        yearly (>=1 row).
    - Returns a dict with keys: sku, today, accuracy, daily, weekly, monthly, yearly
      or {'error': '...'} on failure (no raises).
    """
    try:
        sku = (str(sku_input).strip() if sku_input is not None else "")
        if not sku:
            return {"error": "SKU is required"}

        # Connect and fetch data
        try:
            cnx = _connect_mysql()
        except Exception as e:
            return {"error": f"Database connection failed: {str(e)}"}

        try:
            df_raw = _fetch_sales_history(cnx, sku)
        finally:
            try:
                cnx.close()
            except Exception:
                pass

        if df_raw.empty:
            return {"error": f"No historical data found for SKU '{sku}'"}

        # Prepare time series
        ts_df = _prepare_time_series(df_raw)  # index=date, col 'y'

        # Feature engineering
        feat_df = _add_features(ts_df)  # contains features + 'y'

        # If, after feature creation, nothing left to train
        if feat_df.empty:
            return {"error": f"Not enough historical data to train model for SKU '{sku}'"}

        # Split train/validation chronologically
        # Reserve up to last 30 days (but at least 1 and at most 20% of data)
        n = len(feat_df)
        val_days = min(30, max(1, int(round(0.2 * n))))
        train_df = feat_df.iloc[:-val_days] if n > 1 else feat_df
        val_df = feat_df.iloc[-val_days:] if n > 1 else feat_df.iloc[0:0]

        feature_cols = [c for c in feat_df.columns if c != "y"]
        X_train = train_df[feature_cols]
        y_train = train_df["y"].values
        X_val = val_df[feature_cols]
        y_val = val_df["y"].values

        # Train model
        rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        # If training set is empty (extreme edge), bail out
        if X_train.empty:
            return {"error": f"Not enough data to train model for SKU '{sku}'"}
        rf.fit(X_train, y_train)

        # Compute validation accuracy (MAPE-based accuracy)
        accuracy = None
        if len(y_val) > 0:
            y_pred_val = rf.predict(X_val)
            denom = np.maximum(np.abs(y_val), 1e-8)
            mape = float(np.mean(np.abs((y_val - y_pred_val) / denom)))
            # Accuracy as (1 - MAPE); clip to [0, 1]
            accuracy = float(np.clip(1.0 - mape, 0.0, 1.0))

        # Recursive 365-day forecast
        last_hist_date = ts_df.index.max()
        horizon_days = 365
        future_dates = [last_hist_date + timedelta(days=i) for i in range(1, horizon_days + 1)]

        # Series with historical data to append predictions to
        series_y = ts_df["y"].copy()

        preds = []
        for d in future_dates:
            feats = _compute_features_for_date(series_y, d)
            x_row = pd.DataFrame([feats], columns=feature_cols)
            y_hat = float(rf.predict(x_row)[0])
            # Clip negatives to zero
            y_hat = max(0.0, y_hat)
            preds.append(y_hat)
            # Append to series for subsequent lags/rollings
            series_y.loc[d] = y_hat

        forecast_df = pd.DataFrame({"date": future_dates, "forecast": preds})
        # Ensure types are clean
        forecast_df["date"] = pd.to_datetime(forecast_df["date"]).dt.normalize()
        forecast_df["forecast"] = forecast_df["forecast"].astype(float)

        # Build aggregations
        # Daily: next 7 days
        daily_rows = []
        for _, r in forecast_df.head(7).iterrows():
            daily_rows.append(
                {
                    "date": r["date"].date().isoformat(),
                    "forecast": _to_float(r["forecast"]),
                }
            )

        # Weekly: aggregate first 28 days into up to 4 weeks (Mon-Sun weeks)
        df_28 = forecast_df.head(28).copy()
        if not df_28.empty:
            # Compute week start (Monday)
            df_28["week_start"] = df_28["date"].dt.normalize() - pd.to_timedelta(
                df_28["date"].dt.weekday, unit="D"
            )
            weekly_grouped = (
                df_28.groupby("week_start", as_index=True)["forecast"].sum().sort_index()
            )
            weekly_rows = []
            for wk_start, total in weekly_grouped.head(4).items():
                wk_start_dt = pd.to_datetime(wk_start).date()
                wk_end_dt = (wk_start_dt + timedelta(days=6))
                weekly_rows.append(
                    {
                        "start": wk_start_dt.isoformat(),
                        "end": wk_end_dt.isoformat(),
                        "forecast": _to_float(total),
                    }
                )
        else:
            weekly_rows = []

        # Monthly: next up to 12 months
        m_series = (
            forecast_df.set_index("date")["forecast"]
            .resample("MS")
            .sum()
            .sort_index()
            .head(12)
        )
        monthly_rows = []
        for m_start, total in m_series.items():
            m_start_dt = pd.to_datetime(m_start).date()
            m_end_dt = (pd.to_datetime(m_start) + MonthEnd(1)).date()
            monthly_rows.append(
                {
                    "start": m_start_dt.isoformat(),
                    "end": m_end_dt.isoformat(),
                    "forecast": _to_float(total),
                }
            )

        # Yearly: aggregate horizon into calendar years (>=1 row)
        y_series = (
            forecast_df.set_index("date")["forecast"]
            .resample("YS")  # Year start
            .sum()
            .sort_index()
        )
        yearly_rows = []
        for y_start, total in y_series.items():
            y_start_dt = pd.to_datetime(y_start).date()
            # Year end is start of next year minus one day
            next_year_start = date(y_start_dt.year + 1, 1, 1)
            y_end_dt = next_year_start - timedelta(days=1)
            yearly_rows.append(
                {
                    "start": y_start_dt.isoformat(),
                    "end": y_end_dt.isoformat(),
                    "forecast": _to_float(total),
                }
            )

        result = {
            "sku": sku,
            "today": date.today().isoformat(),
            "accuracy": None if accuracy is None else float(accuracy),
            "daily": daily_rows,
            "weekly": weekly_rows,
            "monthly": monthly_rows,
            "yearly": yearly_rows,
        }
        return result

    except Exception as e:  # Catch-all to ensure function never raises
        return {"error": f"Forecast failed: {str(e)}"}
