"""
export_for_powerbi.py
----------------------
Exports the mart-layer tables to CSV so Power BI (or Excel, or any
BI tool) can import them directly via "Get Data > Text/CSV" -- no
ODBC driver setup required. This is the hand-off point between the
data engineering side and the BI/analytics side of the project.

(For a live/refreshable connection instead of static CSVs, Power BI
can also connect straight to DuckDB via its ODBC driver, or to the
SQLite file via the community SQLite connector -- see
dashboards/PowerBI_instructions.md.)
"""
import os
import sqlite3
import csv

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "warehouse.db")
EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboards", "powerbi_data")

MART_TABLES = [
    "dim_customers", "dim_products", "dim_date",
    "fct_order_items", "mart_daily_sales", "mart_customer_order_summary",
    "mart_sales_trends", "mart_product_ranking",
    "mart_monthly_category_revenue", "mart_market_basket",
]


def run():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for table in MART_TABLES:
        cur.execute(f"SELECT * FROM {table}")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        out_path = os.path.join(EXPORT_DIR, f"{table}.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            writer.writerows(rows)
        print(f"[export] {table}: {len(rows)} rows -> {out_path}")

    conn.close()
    print(f"\n[export] all mart tables exported to {os.path.abspath(EXPORT_DIR)}")
    print("[export] open Power BI Desktop -> Get Data -> Folder -> point at that directory")


if __name__ == "__main__":
    run()
