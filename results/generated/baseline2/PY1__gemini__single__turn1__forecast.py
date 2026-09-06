import os
import mysql.connector
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error


def run_forecast(sku_input):
    """
    Connects to MySQL sales_history table, fetches historical sales for the given SKU,
    engineers lag/rolling features, trains a RandomForestRegressor, and returns a 365-day
    recursive forecast aggregated into daily, weekly, monthly, and yearly buckets.

    Never raises exceptions; returns {'error': ...} if DB connection fails or no data exists.
    """
    try:
        if sku_input is None:
            return {'error': 'Invalid SKU: Input cannot be None'}

        sku = str(sku_input).strip()
        if not sku:
            return {'error': 'Invalid SKU: Input cannot be empty'}

        # Fetch environment variables for DB config with standard defaults
        db_config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD', ''),
            'database': os.getenv('MYSQL_DATABASE', 'logix'),
            'port': int(os.getenv('MYSQL_PORT', 3306))
        }

        try:
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
        except Exception as db_err:
            return {'error': f'Database connection or query failed: {str(db_err)}'}

        if not rows:
            return {'error': f'No historical data found for SKU: {sku}'}

        df = pd.DataFrame(rows)
        if df.empty or 'sale_date' not in df.columns or 'quantity_sold' not in df.columns:
            return {'error': f'No historical data found for SKU: {sku}'}

        df['sale_date'] = pd.to_datetime(df['sale_date'])
        df['quantity_sold'] = pd.to_numeric(df['quantity_sold'], errors='coerce').fillna(0.0)

        # Aggregate daily sales
        df = df.groupby('sale_date', as_index=False)['quantity_sold'].sum()

        # Reindex to complete daily range
        min_date = df['sale_date'].min()
        max_date = df['sale_date'].max()
        full_range = pd.date_range(start=min_date, end=max_date, freq='D')
        df = df.set_index('sale_date').reindex(full_range, fill_value=0.0).reset_index()
        df.rename(columns={'index': 'sale_date'}, inplace=True)

        # Feature engineering
        df['lag_1'] = df['quantity_sold'].shift(1)
        df['lag_7'] = df['quantity_sold'].shift(7).fillna(df['lag_1'])
        df['lag_14'] = df['quantity_sold'].shift(14).fillna(df['lag_7'])
        df['lag_30'] = df['quantity_sold'].shift(30).fillna(df['lag_14'])

        df['rolling_7'] = df['quantity_sold'].shift(1).rolling(window=7, min_periods=1).mean()
        df['rolling_14'] = df['quantity_sold'].shift(1).rolling(window=14, min_periods=1).mean()
        df['rolling_30'] = df['quantity_sold'].shift(1).rolling(window=30, min_periods=1).mean()

        df['dayofweek'] = df['sale_date'].dt.dayofweek
        df['day'] = df['sale_date'].dt.day
        df['month'] = df['sale_date'].dt.month

        train_df = df.dropna(subset=['lag_1']).copy()
        if train_df.empty:
            train_df = df.copy().fillna(0.0)

        feature_cols = [
            'lag_1', 'lag_7', 'lag_14', 'lag_30',
            'rolling_7', 'rolling_14', 'rolling_30',
            'dayofweek', 'day', 'month'
        ]
        X = train_df[feature_cols].fillna(0.0)
        y = train_df['quantity_sold']

        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)

        # Calculate accuracy metric
        y_pred = model.predict(X)
        mae = mean_absolute_error(y, y_pred)
        mean_actual = float(np.mean(y))
        if mean_actual > 0:
            accuracy = max(0.0, min(100.0, 100.0 * (1.0 - (mae / mean_actual))))
        else:
            accuracy = 100.0 if mae == 0 else 0.0

        # Recursive 365-day forecast
        forecast_records = []
        series = list(df['quantity_sold'].values)
        last_date = df['sale_date'].iloc[-1]

        for i in range(1, 366):
            current_date = last_date + timedelta(days=i)

            l1 = series[-1]
            l7 = series[-7] if len(series) >= 7 else series[0]
            l14 = series[-14] if len(series) >= 14 else series[0]
            l30 = series[-30] if len(series) >= 30 else series[0]

            r7 = float(np.mean(series[-7:])) if len(series) >= 7 else float(np.mean(series))
            r14 = float(np.mean(series[-14:])) if len(series) >= 14 else float(np.mean(series))
            r30 = float(np.mean(series[-30:])) if len(series) >= 30 else float(np.mean(series))

            dow = current_date.dayofweek
            day = current_date.day
            month = current_date.month

            X_step = np.array([[l1, l7, l14, l30, r7, r14, r30, dow, day, month]])
            pred_qty = float(model.predict(X_step)[0])
            pred_qty = max(0.0, pred_qty)

            series.append(pred_qty)
            forecast_records.append({
                'date': current_date,
                'forecast_quantity': pred_qty
            })

        forecast_df = pd.DataFrame(forecast_records)

        # Daily bucket (7 rows)
        daily_df = forecast_df.head(7)
        daily = [
            {
                'date': row['date'].strftime('%Y-%m-%d'),
                'forecast_quantity': round(float(row['forecast_quantity']), 2)
            }
            for _, row in daily_df.iterrows()
        ]

        # Weekly bucket (<= 4 rows, first 4 weeks)
        weekly = []
        for w in range(4):
            w_df = forecast_df.iloc[w * 7 : (w + 1) * 7]
            if not w_df.empty:
                weekly.append({
                    'week': w + 1,
                    'start_date': w_df['date'].min().strftime('%Y-%m-%d'),
                    'end_date': w_df['date'].max().strftime('%Y-%m-%d'),
                    'forecast_quantity': round(float(w_df['forecast_quantity'].sum()), 2)
                })

        # Monthly bucket (<= 12 rows)
        forecast_df['year_month'] = forecast_df['date'].dt.to_period('M')
        monthly_grouped = forecast_df.groupby('year_month', as_index=False)['forecast_quantity'].sum().head(12)
        monthly = [
            {
                'month': str(row['year_month']),
                'forecast_quantity': round(float(row['forecast_quantity']), 2)
            }
            for _, row in monthly_grouped.iterrows()
        ]

        # Yearly bucket (>= 1 row)
        forecast_df['year'] = forecast_df['date'].dt.year
        yearly_grouped = forecast_df.groupby('year', as_index=False)['forecast_quantity'].sum()
        yearly = [
            {
                'year': int(row['year']),
                'forecast_quantity': round(float(row['forecast_quantity']), 2)
            }
            for _, row in yearly_grouped.iterrows()
        ]

        return {
            'sku': sku,
            'accuracy': round(float(accuracy), 2),
            'today': datetime.now().strftime('%Y-%m-%d'),
            'daily': daily,
            'weekly': weekly,
            'monthly': monthly,
            'yearly': yearly
        }

    except Exception as e:
        return {'error': str(e)}
