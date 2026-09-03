"""
sales_forecast.py
------------------
Small but genuine ML component: forecasts next 14 days of gross
revenue using mart_daily_sales (the same table Power BI reads from).

Kept deliberately simple and explainable for an interview:
  - Feature engineering: day-of-week, rolling 7-day average, trend index
  - Model: RandomForestRegressor (scikit-learn) -- robust to the
    non-linear weekend/festive seasonality baked into the synthetic
    data, and easy to explain feature importance for.
  - Evaluation: time-based train/test split (never shuffle time series!)
    with MAE and MAPE reported.
  - Output: forecast_output.csv + a PNG chart, both saved to ml/,
    so they can be dropped straight into the Power BI report or the
    resume/portfolio README as a screenshot.
"""
import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "warehouse.db")
OUT_DIR = os.path.dirname(__file__)
FORECAST_HORIZON = 14


def load_daily_sales():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM mart_daily_sales ORDER BY order_date", conn)
    conn.close()
    df["order_date"] = pd.to_datetime(df["order_date"])
    return df


def engineer_features(df):
    df = df.copy()
    df["day_of_week"] = df["order_date"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["day_index"] = np.arange(len(df))  # captures overall trend
    df["rolling_7d_avg"] = df["gross_revenue"].rolling(7, min_periods=1).mean().shift(1)
    df["rolling_7d_avg"] = df["rolling_7d_avg"].bfill()
    df["lag_1"] = df["gross_revenue"].shift(1).bfill()
    df["lag_7"] = df["gross_revenue"].shift(7).bfill()
    return df


FEATURES = ["day_of_week", "is_weekend", "day_index", "rolling_7d_avg", "lag_1", "lag_7"]
TARGET = "gross_revenue"


def train_and_evaluate(df):
    split_idx = int(len(df) * 0.85)  # time-based split -- no shuffling
    train, test = df.iloc[:split_idx], df.iloc[split_idx:]

    model = RandomForestRegressor(n_estimators=300, max_depth=6, random_state=42)
    model.fit(train[FEATURES], train[TARGET])

    preds = model.predict(test[FEATURES])
    mae = mean_absolute_error(test[TARGET], preds)
    mape = mean_absolute_percentage_error(test[TARGET], preds) * 100

    print(f"[ml] Test MAE:  ₹{mae:,.2f}")
    print(f"[ml] Test MAPE: {mape:.2f}%")

    importances = pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False)
    print("[ml] Feature importances:")
    for feat, imp in importances.items():
        print(f"     {feat}: {imp:.3f}")

    return model, test, preds, mae, mape


def forecast_future(model, df, horizon=FORECAST_HORIZON):
    """Recursive multi-step forecast: predict one day, feed it back in
    as a lag feature to predict the next, etc. -- standard approach
    for tree-based models on time series without native multi-step support."""
    history = df.copy()
    future_rows = []
    last_date = history["order_date"].max()

    for step in range(1, horizon + 1):
        next_date = last_date + pd.Timedelta(days=step)
        row = {
            "order_date": next_date,
            "day_of_week": next_date.dayofweek,
            "is_weekend": int(next_date.dayofweek >= 5),
            "day_index": history["day_index"].max() + step,
            "rolling_7d_avg": history["gross_revenue"].tail(7).mean(),
            "lag_1": history["gross_revenue"].iloc[-1],
            "lag_7": history["gross_revenue"].iloc[-7] if len(history) >= 7 else history["gross_revenue"].mean(),
        }
        pred = model.predict(pd.DataFrame([row])[FEATURES])[0]
        row["gross_revenue"] = pred
        future_rows.append(row)
        history = pd.concat([history, pd.DataFrame([row])], ignore_index=True)

    return pd.DataFrame(future_rows)[["order_date", "gross_revenue"]]


def plot_forecast(historical, forecast, path):
    plt.figure(figsize=(11, 5))
    plt.plot(historical["order_date"].tail(60), historical["gross_revenue"].tail(60),
              label="Actual (last 60 days)", color="#2563eb")
    plt.plot(forecast["order_date"], forecast["gross_revenue"],
              label=f"Forecast (next {FORECAST_HORIZON} days)", color="#f97316",
              linestyle="--", marker="o", markersize=3)
    plt.title("Daily Gross Revenue -- Actual vs. Forecast")
    plt.xlabel("Date")
    plt.ylabel("Gross Revenue (₹)")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    print(f"[ml] chart saved -> {path}")


def run():
    df = load_daily_sales()
    df = engineer_features(df)
    model, test, preds, mae, mape = train_and_evaluate(df)
    forecast = forecast_future(model, df)

    forecast_path = os.path.join(OUT_DIR, "forecast_output.csv")
    forecast.to_csv(forecast_path, index=False)
    print(f"[ml] forecast saved -> {forecast_path}")

    plot_forecast(df, forecast, os.path.join(OUT_DIR, "forecast_chart.png"))

    with open(os.path.join(OUT_DIR, "model_metrics.txt"), "w") as f:
        f.write(f"Test MAE: {mae:.2f}\nTest MAPE: {mape:.2f}%\n")


if __name__ == "__main__":
    run()
