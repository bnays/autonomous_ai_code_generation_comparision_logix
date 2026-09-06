import datetime
import os
import mysql.connector
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor


def run_forecast(sku_input):
    """Generates a 365-day recursive sales forecast for a given SKU.

    Connects to MySQL, extracts sales history using pandas read_sql, engineers lag
    and rolling features, trains a RandomForestRegressor, and aggregates forecasts
    into daily, weekly, monthly, and yearly buckets.

    Never raises exceptions; returns {'error': ...} on failure or missing data.
    """
    try:
        if sku_input is None:
            return {"error": "SKU input is required."}

        sku = str(sku_input).strip()
        if not sku:
            return {"error": "SKU input cannot be empty."}

        db_config = {
            "host": os.getenv("DB_HOST", os.getenv("MYSQL_HOST", "localhost")),
            "user": os.getenv("DB_USER", os.getenv("MYSQL_USER", "root")),
            "password": os.getenv(
                "DB_PASSWORD", os.getenv("MYSQL_PASSWORD", "")
            ),
            "database": os.getenv(
                "DB_NAME", os.getenv("MYSQL_DATABASE", "logix")
            ),
            "port": int(os.getenv("DB_PORT", os.getenv("MYSQL_PORT", "3306"))),
        }

        conn = mysql.connector.connect(**db_config)
        query = (
            "SELECT sale_date, quantity_sold FROM sales_history "
            "WHERE sku = %s ORDER BY sale_date ASC"
        )
        try:
            df = pd.read_sql(query, conn, params=[sku])
        finally:
            try:
                conn.close()
            except Exception:
                pass

        if df is None or df.empty or len(df) == 0:
            return {"error": f"No historical data found for SKU: {sku}"}

        if "sale_date" not in df.columns or "quantity_sold" not in df.columns:
            return {"error": f"No historical data found for SKU: {sku}"}

        df["sale_date"] = pd.to_datetime(df["sale_date"])
        df["quantity_sold"] = (
            pd.to_numeric(df["quantity_sold"], errors="coerce").fillna(0.0)
        )

        # Aggregate daily sales
        df_daily = (
            df.groupby("sale_date")["quantity_sold"].sum().reset_index()
        )
        df_daily = df_daily.sort_values("sale_date")

        # Reindex full date range from min to max date
        min_date = df_daily["sale_date"].min()
        max_date = df_daily["sale_date"].max()
        full_date_range = pd.date_range(start=min_date, end=max_date, freq="D")
        df_daily = (
            df_daily.set_index("sale_date")
            .reindex(full_date_range, fill_value=0.0)
            .reset_index()
        )
        df_daily.rename(columns={"index": "sale_date"}, inplace=True)

        # Lag and rolling features
        lags = [1, 7, 14, 30]
        rolling_windows = [7, 30]

        for lag in lags:
            df_daily[f"lag_{lag}"] = (
                df_daily["quantity_sold"].shift(lag).fillna(0.0)
            )

        for w in rolling_windows:
            df_daily[f"rolling_mean_{w}"] = (
                df_daily["quantity_sold"]
                .shift(1)
                .rolling(window=w, min_periods=1)
                .mean()
                .fillna(0.0)
            )
            df_daily[f"rolling_std_{w}"] = (
                df_daily["quantity_sold"]
                .shift(1)
                .rolling(window=w, min_periods=1)
                .std()
                .fillna(0.0)
            )

        df_daily["dayofweek"] = df_daily["sale_date"].dt.dayofweek
        df_daily["month"] = df_daily["sale_date"].dt.month
        df_daily["day"] = df_daily["sale_date"].dt.day

        feature_cols = [
            c
            for c in df_daily.columns
            if c not in ["sale_date", "quantity_sold"]
        ]
        X = df_daily[feature_cols]
        y = df_daily["quantity_sold"]

        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)

        score = model.score(X, y) if len(X) > 1 else 0.0
        if np.isnan(score):
            score = 0.0
        accuracy = round(float(max(0.0, min(1.0, score))), 4)

        # 365-day recursive forecasting
        history_series = df_daily.set_index("sale_date")["quantity_sold"].to_dict()
        last_date = df_daily["sale_date"].max()
        today_str = datetime.date.today().isoformat()

        forecast_dates = [
            last_date + datetime.timedelta(days=i) for i in range(1, 366)
        ]
        forecast_values = []
        full_series = history_series.copy()

        for cur_date in forecast_dates:
            row_dict = {}
            for lag in lags:
                target_date = cur_date - datetime.timedelta(days=lag)
                row_dict[f"lag_{lag}"] = full_series.get(target_date, 0.0)

            for w in rolling_windows:
                past_vals = [
                    full_series.get(cur_date - datetime.timedelta(days=i), 0.0)
                    for i in range(1, w + 1)
                ]
                row_dict[f"rolling_mean_{w}"] = (
                    float(np.mean(past_vals)) if past_vals else 0.0
                )
                row_dict[f"rolling_std_{w}"] = (
                    float(np.std(past_vals)) if len(past_vals) > 1 else 0.0
                )

            row_dict["dayofweek"] = cur_date.dayofweek
            row_dict["month"] = cur_date.month
            row_dict["day"] = cur_date.day

            feat_row = pd.DataFrame([row_dict])[feature_cols]
            pred = float(model.predict(feat_row)[0])
            pred = max(0.0, round(pred, 2))

            forecast_values.append(pred)
            full_series[cur_date] = pred

        forecast_df = pd.DataFrame(
            {"date": forecast_dates, "quantity": forecast_values}
        )

        # Daily Bucket (7 rows)
        daily_bucket = [
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "quantity": float(row["quantity"]),
            }
            for _, row in forecast_df.head(7).iterrows()
        ]

        # Weekly Bucket (<=4 rows)
        weekly_bucket = []
        for i in range(4):
            chunk = forecast_df.iloc[i * 7 : (i + 1) * 7]
            if not chunk.empty:
                start_str = chunk.iloc[0]["date"].strftime("%Y-%m-%d")
                end_str = chunk.iloc[-1]["date"].strftime("%Y-%m-%d")
                weekly_bucket.append(
                    {
                        "week": i + 1,
                        "start_date": start_str,
                        "end_date": end_str,
                        "quantity": round(float(chunk["quantity"].sum()), 2),
                    }
                )

        # Monthly Bucket (<=12 rows)
        forecast_df["year_month"] = forecast_df["date"].dt.to_period("M")
        monthly_grouped = (
            forecast_df.groupby("year_month", sort=False)["quantity"]
            .sum()
            .reset_index()
        )
        monthly_bucket = [
            {
                "month": str(row["year_month"]),
                "quantity": round(float(row["quantity"]), 2),
            }
            for _, row in monthly_grouped.head(12).iterrows()
        ]

        # Yearly Bucket (>=1 row)
        forecast_df["year"] = forecast_df["date"].dt.year
        yearly_grouped = (
            forecast_df.groupby("year", sort=False)["quantity"]
            .sum()
            .reset_index()
        )
        yearly_bucket = [
            {
                "year": int(row["year"]),
                "quantity": round(float(row["quantity"]), 2),
            }
            for _, row in yearly_grouped.iterrows()
        ]

        return {
            "sku": sku,
            "today": today_str,
            "accuracy": accuracy,
            "daily": daily_bucket,
            "weekly": weekly_bucket,
            "monthly": monthly_bucket,
            "yearly": yearly_bucket,
        }

    except Exception as e:
        return {"error": str(e)}
