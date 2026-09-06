import os
from datetime import datetime, timedelta
import mysql.connector
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score


def run_forecast(sku_input):
    """
    Connects to MySQL, fetches sales history for the given SKU, engineers lag and rolling
    features, trains a RandomForestRegressor, performs a recursive 365-day forecast,
    and returns aggregated predictions (daily, weekly, monthly, yearly).
    Never raises exceptions; returns {'error': ...} on failure or missing data.
    """
    try:
        if sku_input is None:
            return {'error': 'SKU input is required.'}

        sku = str(sku_input).strip()
        if not sku:
            return {'error': 'SKU cannot be empty.'}

        # Database configuration from environment variables with defaults
        db_config = {
            'host': os.getenv('DB_HOST', os.getenv('MYSQL_HOST', 'localhost')),
            'user': os.getenv('DB_USER', os.getenv('MYSQL_USER', 'root')),
            'password': os.getenv('DB_PASSWORD', os.getenv('MYSQL_PASSWORD', '')),
            'database': os.getenv('DB_NAME', os.getenv('MYSQL_DATABASE', 'logix')),
            'port': int(os.getenv('DB_PORT', os.getenv('MYSQL_PORT', '3306')))
        }

        # Connect to MySQL and fetch data
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
            return {'error': f'Database connection failed: {str(db_err)}'}

        if not rows:
            return {'error': f'No historical data found for SKU: {sku}'}

        # Convert query results to DataFrame
        df = pd.DataFrame(rows)
        if 'sale_date' not in df.columns or 'quantity_sold' not in df.columns or df.empty:
            return {'error': f'No historical data found for SKU: {sku}'}

        df['sale_date'] = pd.to_datetime(df['sale_date'])
        df['quantity_sold'] = pd.to_numeric(df['quantity_sold'], errors='coerce').fillna(0.0)

        # Aggregate multiple sales on the same date
        df = df.groupby('sale_date', as_index=False)['quantity_sold'].sum().sort_values('sale_date').reset_index(drop=True)

        if df.empty:
            return {'error': f'No historical data found for SKU: {sku}'}

        # Fill missing daily dates in the historical timeline
        min_date = df['sale_date'].min()
        max_date = df['sale_date'].max()
        full_date_range = pd.date_range(start=min_date, end=max_date, freq='D')
        df = df.set_index('sale_date').reindex(full_date_range, fill_value=0.0).rename_axis('sale_date').reset_index()

        def extract_features(series):
            """Calculates lag and rolling average features from a quantity series."""
            s = pd.Series(series)
            n = len(s)
            return {
                'lag_1': s.iloc[-1] if n >= 1 else 0.0,
                'lag_7': s.iloc[-7] if n >= 7 else (s.iloc[-1] if n >= 1 else 0.0),
                'lag_14': s.iloc[-14] if n >= 14 else (s.iloc[-1] if n >= 1 else 0.0),
                'lag_30': s.iloc[-30] if n >= 30 else (s.iloc[-1] if n >= 1 else 0.0),
                'rolling_mean_7': float(s.iloc[-7:].mean()) if n >= 1 else 0.0,
                'rolling_mean_14': float(s.iloc[-14:].mean()) if n >= 1 else 0.0,
                'rolling_mean_30': float(s.iloc[-30:].mean()) if n >= 1 else 0.0,
            }

        # Build feature dataset for training
        quantities = df['quantity_sold'].tolist()
        dates = df['sale_date'].tolist()
        training_data = []

        for i in range(1, len(quantities)):
            features = extract_features(quantities[:i])
            dt = dates[i]
            features['day_of_week'] = dt.dayofweek
            features['day_of_month'] = dt.day
            features['month'] = dt.month
            features['target'] = quantities[i]
            training_data.append(features)

        if not training_data:
            # Fallback for single data point
            features = extract_features(quantities)
            dt = dates[0]
            features['day_of_week'] = dt.dayofweek
            features['day_of_month'] = dt.day
            features['month'] = dt.month
            features['target'] = quantities[0]
            training_data.append(features)

        train_df = pd.DataFrame(training_data)
        feature_cols = [
            'lag_1', 'lag_7', 'lag_14', 'lag_30',
            'rolling_mean_7', 'rolling_mean_14', 'rolling_mean_30',
            'day_of_week', 'day_of_month', 'month'
        ]

        X = train_df[feature_cols]
        y = train_df['target']

        # Train Random Forest model
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)

        # Calculate model accuracy (R2 Score bounded [0, 1])
        y_pred = model.predict(X)
        try:
            r2 = r2_score(y, y_pred)
            accuracy = float(round(max(0.0, min(1.0, r2)), 4)) if not np.isnan(r2) else 0.0
        except Exception:
            accuracy = 0.0

        # Perform recursive 365-day forecast
        current_series = list(quantities)
        last_date = dates[-1]
        forecast_records = []

        for step in range(1, 366):
            next_date = last_date + timedelta(days=step)
            features = extract_features(current_series)
            features['day_of_week'] = next_date.dayofweek
            features['day_of_month'] = next_date.day
            features['month'] = next_date.month

            X_step = pd.DataFrame([features])[feature_cols]
            pred_qty = float(model.predict(X_step)[0])
            pred_qty = max(0.0, pred_qty)

            forecast_records.append({
                'date': next_date,
                'quantity': round(pred_qty, 2)
            })
            current_series.append(pred_qty)

        forecast_df = pd.DataFrame(forecast_records)

        # 1. Daily Bucket: Next 7 days
        daily_df = forecast_df.head(7)
        daily = [
            {'date': row['date'].strftime('%Y-%m-%d'), 'quantity': round(float(row['quantity']), 2)}
            for _, row in daily_df.iterrows()
        ]

        # 2. Weekly Bucket: Next 4 weeks (<= 4 rows)
        forecast_df['week_index'] = forecast_df.index // 7
        weekly_df = forecast_df.groupby('week_index', as_index=False).agg({
            'date': 'first',
            'quantity': 'sum'
        }).head(4)
        weekly = [
            {'date': row['date'].strftime('%Y-%m-%d'), 'quantity': round(float(row['quantity']), 2)}
            for _, row in weekly_df.iterrows()
        ]

        # 3. Monthly Bucket: <= 12 rows
        forecast_df['year_month'] = forecast_df['date'].dt.to_period('M')
        monthly_df = forecast_df.groupby('year_month', as_index=False).agg({
            'date': 'first',
            'quantity': 'sum'
        }).head(12)
        monthly = [
            {'date': row['date'].strftime('%Y-%m-%d'), 'quantity': round(float(row['quantity']), 2)}
            for _, row in monthly_df.iterrows()
        ]

        # 4. Yearly Bucket: >= 1 row
        forecast_df['year'] = forecast_df['date'].dt.year
        yearly_df = forecast_df.groupby('year', as_index=False).agg({
            'date': 'first',
            'quantity': 'sum'
        })
        yearly = [
            {'date': row['date'].strftime('%Y-%m-%d'), 'quantity': round(float(row['quantity']), 2)}
            for _, row in yearly_df.iterrows()
        ]

        today_str = datetime.now().strftime('%Y-%m-%d')

        return {
            'sku': sku,
            'accuracy': accuracy,
            'today': today_str,
            'daily': daily,
            'weekly': weekly,
            'monthly': monthly,
            'yearly': yearly
        }

    except Exception as err:
        return {'error': f'Forecast generation failed: {str(err)}'}
