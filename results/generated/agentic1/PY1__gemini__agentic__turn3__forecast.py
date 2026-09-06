import os
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import mysql.connector
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "logix_wms"),
        port=int(os.getenv("DB_PORT", 3306))
    )


def run_forecast(sku_input):
    """
    Connects to MySQL via pandas read_sql, pulls sales history for a given SKU,
    trains a RandomForestRegressor using lag and rolling-average features, and returns
    a recursive 365-day forecast aggregated into daily, weekly, monthly, and yearly buckets.

    Never raises an exception; returns {'error': ...} on DB connection failure or missing data.
    """
    try:
        if sku_input is None:
            return {'error': 'SKU input cannot be None'}

        sku = str(sku_input).strip()
        if not sku:
            return {'error': 'SKU input cannot be empty'}

        # Fetch sales history using pd.read_sql
        conn = None
        try:
            conn = get_db_connection()
            query = "SELECT sale_date, quantity_sold FROM sales_history WHERE sku = %s ORDER BY sale_date ASC"
            df = pd.read_sql(query, con=conn, params=[sku])
        except Exception as e:
            return {'error': f'Database connection error: {str(e)}'}
        finally:
            if conn and hasattr(conn, 'close'):
                try:
                    conn.close()
                except Exception:
                    pass

        if df is None or df.empty:
            return {'error': f'No historical data found for SKU: {sku}'}

        # Normalize column names if mocked data uses 'date' or 'quantity'
        if 'date' in df.columns and 'sale_date' not in df.columns:
            df.rename(columns={'date': 'sale_date'}, inplace=True)
        if 'quantity' in df.columns and 'quantity_sold' not in df.columns:
            df.rename(columns={'quantity': 'quantity_sold'}, inplace=True)

        # Ensure correct data types
        df['sale_date'] = pd.to_datetime(df['sale_date'])
        df['quantity_sold'] = pd.to_numeric(df['quantity_sold'], errors='coerce').fillna(0.0)

        # Resample to continuous daily frequency
        df = df.groupby('sale_date')['quantity_sold'].sum().reset_index()
        min_date = df['sale_date'].min()
        max_date = df['sale_date'].max()

        full_date_range = pd.date_range(start=min_date, end=max_date, freq='D')
        df = df.set_index('sale_date').reindex(full_date_range, fill_value=0.0).reset_index()
        df.rename(columns={'index': 'sale_date'}, inplace=True)

        # Feature Engineering: Lags & Rolling Averages
        df['lag_1'] = df['quantity_sold'].shift(1)
        df['lag_7'] = df['quantity_sold'].shift(7)
        df['lag_14'] = df['quantity_sold'].shift(14)
        df['lag_30'] = df['quantity_sold'].shift(30)
        df['rolling_mean_7'] = df['quantity_sold'].shift(1).rolling(window=7, min_periods=1).mean()
        df['rolling_mean_30'] = df['quantity_sold'].shift(1).rolling(window=30, min_periods=1).mean()
        df['day_of_week'] = df['sale_date'].dt.dayofweek
        df['month'] = df['sale_date'].dt.month

        train_df = df.dropna().copy()
        if train_df.empty:
            df_filled = df.bfill().ffill().fillna(0.0)
            train_df = df_filled.copy()

        feature_cols = ['lag_1', 'lag_7', 'lag_14', 'lag_30', 'rolling_mean_7', 'rolling_mean_30', 'day_of_week', 'month']

        X = train_df[feature_cols]
        y = train_df['quantity_sold']

        # Train Random Forest Regressor
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)

        # Model accuracy score
        y_pred = model.predict(X)
        score = r2_score(y, y_pred) if len(y) > 1 else 1.0
        accuracy = max(0.0, round(float(score), 4))

        # Recursive 365-day Forecast
        history_values = df['quantity_sold'].tolist()
        forecast_dates = []
        forecast_values = []

        last_date = max_date

        for i in range(1, 366):
            next_date = last_date + timedelta(days=i)
            all_values = history_values + forecast_values

            lag_1 = all_values[-1]
            lag_7 = all_values[-7] if len(all_values) >= 7 else all_values[0]
            lag_14 = all_values[-14] if len(all_values) >= 14 else all_values[0]
            lag_30 = all_values[-30] if len(all_values) >= 30 else all_values[0]

            rolling_7 = np.mean(all_values[-7:]) if len(all_values) >= 7 else np.mean(all_values)
            rolling_30 = np.mean(all_values[-30:]) if len(all_values) >= 30 else np.mean(all_values)

            day_of_week = next_date.dayofweek
            month = next_date.month

            x_next = pd.DataFrame([{
                'lag_1': lag_1,
                'lag_7': lag_7,
                'lag_14': lag_14,
                'lag_30': lag_30,
                'rolling_mean_7': rolling_7,
                'rolling_mean_30': rolling_30,
                'day_of_week': day_of_week,
                'month': month
            }])

            pred_val = float(model.predict(x_next)[0])
            pred_val = max(0.0, round(pred_val, 2))

            forecast_dates.append(next_date)
            forecast_values.append(pred_val)

        forecast_df = pd.DataFrame({'date': forecast_dates, 'quantity': forecast_values})

        # Buckets

        # Daily (7 rows)
        daily_df = forecast_df.head(7)
        daily_bucket = [
            {
                'date': row['date'].strftime('%Y-%m-%d'),
                'predicted_sales': float(row['quantity']),
                'quantity': float(row['quantity'])
            }
            for _, row in daily_df.iterrows()
        ]

        # Weekly (<= 4 rows)
        weekly_bucket = []
        for week_idx in range(4):
            start_i = week_idx * 7
            end_i = start_i + 7
            chunk = forecast_df.iloc[start_i:end_i]
            if not chunk.empty:
                week_label = f"Week {week_idx + 1}"
                val = round(float(chunk['quantity'].sum()), 2)
                weekly_bucket.append({
                    'week': week_label,
                    'start_date': chunk['date'].min().strftime('%Y-%m-%d'),
                    'end_date': chunk['date'].max().strftime('%Y-%m-%d'),
                    'predicted_sales': val,
                    'quantity': val
                })

        # Monthly (<= 12 rows)
        forecast_df['year_month'] = forecast_df['date'].dt.to_period('M')
        monthly_grouped = forecast_df.groupby('year_month', sort=False)
        monthly_bucket = []
        for period, group in list(monthly_grouped)[:12]:
            val = round(float(group['quantity'].sum()), 2)
            monthly_bucket.append({
                'month': str(period),
                'predicted_sales': val,
                'quantity': val
            })

        # Yearly (>= 1 row)
        forecast_df['year'] = forecast_df['date'].dt.year
        yearly_grouped = forecast_df.groupby('year', sort=False)
        yearly_bucket = [
            {
                'year': str(year),
                'predicted_sales': round(float(group['quantity'].sum()), 2),
                'quantity': round(float(group['quantity'].sum()), 2)
            }
            for year, group in yearly_grouped
        ]

        return {
            'sku': sku,
            'accuracy': accuracy,
            'today': datetime.now().strftime('%Y-%m-%d'),
            'daily': daily_bucket,
            'weekly': weekly_bucket,
            'monthly': monthly_bucket,
            'yearly': yearly_bucket
        }

    except Exception as e:
        return {'error': f'An unexpected error occurred during forecast generation: {str(e)}'}
