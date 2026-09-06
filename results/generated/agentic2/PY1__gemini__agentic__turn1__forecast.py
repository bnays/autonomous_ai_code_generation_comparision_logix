import datetime
import os
import mysql.connector
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor


def run_forecast(sku_input):
    """Generates a 365-day recursive sales forecast for a given SKU.

    Connects to MySQL, extracts sales history, engineers lag and rolling
    features, trains a RandomForestRegressor, and aggregates forecasts into
    daily, weekly, monthly, and yearly buckets.

    Never raises exceptions; returns {'error': ...} on failure or missing
    data.
    """
    try:
        if sku_input is None:
            return {"error": "SKU input is required."}

        sku = str(sku_input).strip()
        if not sku:
            return {"error": "SKU input cannot be empty."}

        # Database connection configuration
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
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT sale_date, quantity_sold 
            FROM sales_history 
            WHERE sku = %s 
            ORDER BY sale_date ASC
        """
        cursor.execute(query, (sku,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            return {"error": f"No historical data found for SKU: {sku}"}

        # Load data into pandas
        df = pd.DataFrame(rows)
        if (
            df.empty
            or "sale_date" not in df.columns
            or "quantity_sold" not in df.columns
        ):
            return {"error": f"No historical data found for SKU: {sku}"}

        df["sale_date"] = pd.to_datetime(df["sale_date"])
        df["quantity_sold"] = (
            df["quantity_sold"].astype(float).fillna(0.0)
        )

        # Aggregate by day in case of duplicate entries on the same date
        df_daily = (
            df.groupby("sale_date")["quantity_sold"].sum().reset_index()
        )
        df_daily = df_daily.sort_values("sale_date")

        # Fill missing dates in the sequence with 0 quantity
        full_date_range = pd.date_range(
            start=df_daily["sale_date"].min(),
            end=df_daily["sale_date"].max(),
            freq="D",
        )
        df_daily = (
            df_daily.set_index("sale_date")
            .reindex(full_date_range, fill_value=0.0)
            .reset_index()
        )
        df_daily.rename(columns={"index": "sale_date"}, inplace=True)

        # Feature engineering
        lags = [1, 7, 14, 30]
        rolling_windows = [7, 30]

        feat_df = df_daily.copy()
        for lag in lags:
            feat_df[f"lag_{lag}"] = feat_df["quantity_sold"].shift(lag)

        for w in rolling_windows:
            feat_df[f"rolling_mean_{w}"] = (
                feat_df["quantity_sold"].shift(1).rolling(window=w).mean()
            )
            feat_df[f"rolling_std_{w}"] = (
                feat_df["quantity_sold"].shift(1).rolling(window=w).std()
            )

        feat_df["dayofweek"] = feat_df["sale_date"].dt.dayofweek
        feat_df["month"] = feat_df["sale_date"].dt.month
        feat_df["day"] = feat_df["sale_date"].dt.day

        # Clean NaNs created by lag and rolling calculations
        clean_df = feat_df.dropna().reset_index(drop=True)

        if clean_df.empty:
            # Fallback for short historical series
            feat_df = df_daily.copy()
            lags = [1, 2, 3]
            rolling_windows = [2]
            for lag in lags:
                feat_df[f"lag_{lag}"] = feat_df["quantity_sold"].shift(lag)
            for w in rolling_windows:
                feat_df[f"rolling_mean_{w}"] = (
                    feat_df["quantity_sold"].shift(1).rolling(window=w).mean()
                )
                feat_df[f"rolling_std_{w}"] = (
                    feat_df["quantity_sold"].shift(1).rolling(window=w).std()
                )
            feat_df["dayofweek"] = feat_df["sale_date"].dt.dayofweek
            feat_df["month"] = feat_df["sale_date"].dt.month
            feat_df["day"] = feat_df["sale_date"].dt.day
            clean_df = feat_df.dropna().reset_index(drop=True)

            if clean_df.empty:
                # Minimum fallback if dataset is extremely small
                clean_df = df_daily.copy()
                clean_df["dayofweek"] = clean_df["sale_date"].dt.dayofweek
                clean_df["month"] = clean_df["sale_date"].dt.month
                clean_df["day"] = clean_df["sale_date"].dt.day
                lags = []
                rolling_windows = []

        feature_cols = [
            c
            for c in clean_df.columns
            if c not in ["sale_date", "quantity_sold"]
        ]
        X = clean_df[feature_cols]
        y = clean_df["quantity_sold"]

        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)

        # Model accuracy (R^2 score bounded to [0.0, 1.0])
        score = model.score(X, y) if len(X) > 1 else 0.0
        accuracy = round(float(max(0.0, min(1.0, score))), 4) if not np.isnan(score) else 0.0

        # Recursive 365-day forecast
        history_dict = df_daily.set_index("sale_date")["quantity_sold"].to_dict()
        last_date = df_daily["sale_date"].max()
        today_str = datetime.date.today().isoformat()

        forecast_dates = [
            last_date + datetime.timedelta(days=i) for i in range(1, 366)
        ]
        forecast_values = []
        full_series = history_dict.copy()

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
                    float(np.std(past_vals)) if past_vals else 0.0
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
                sum_qty = round(float(chunk["quantity"].sum()), 2)
                weekly_bucket.append(
                    {
                        "week": i + 1,
                        "start_date": start_str,
                        "end_date": end_str,
                        "quantity": sum_qty,
                    }
                )

        # Monthly Bucket (<=12 rows)
        forecast_df["year_month"] = forecast_df["date"].dt.to_period("M")
        monthly_grouped = (
            forecast_df.groupby("year_month")["quantity"].sum().reset_index()
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
            forecast_df.groupby("year")["quantity"].sum().reset_index()
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
