"""
load.py
-------
Load layer: takes the raw CSVs ("bronze" landing zone) and loads them
as-is into the analytical warehouse's raw schema. No transformation
happens here on purpose -- that is dbt's job (see /dbt_project). This
keeps the pipeline's responsibilities cleanly separated (EL, then T),
which is the standard modern ELT pattern.

Supports two engines via --engine:
  sqlite  (default) - zero extra dependencies, so the pipeline runs
                       end-to-end on any machine with just Python.
  duckdb             - the production-grade target (fast, columnar,
                       plays natively with dbt-duckdb + Power BI's
                       ODBC connector). Requires `pip install duckdb`.

Swapping the warehouse later (e.g. to Postgres/Snowflake/BigQuery)
only means changing this connection layer + the dbt profiles.yml --
the extract/transform logic doesn't change. That separation is the
whole point of the ELT architecture.
"""
import argparse
import csv
import os
import sqlite3

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
WAREHOUSE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

TABLES = {
    "customers": ["customer_id", "first_name", "last_name", "email", "city",
                  "country", "signup_date", "customer_segment"],
    "products": ["product_id", "product_name", "category", "unit_price", "cost_price"],
    "orders": ["order_id", "customer_id", "order_timestamp", "order_date",
               "payment_method", "order_status", "order_total"],
    "order_items": ["order_item_id", "order_id", "product_id", "quantity",
                     "unit_price", "discount_pct", "line_total"],
}

NUMERIC_COLS = {
    "customer_id", "product_id", "order_id", "order_item_id", "quantity",
    "unit_price", "cost_price", "discount_pct", "line_total", "order_total",
}


def read_csv_rows(name):
    path = os.path.join(RAW_DIR, f"{name}.csv")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cast(value, col):
    if col not in NUMERIC_COLS:
        return value
    try:
        f = float(value)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return value


def load_sqlite():
    os.makedirs(WAREHOUSE_DIR, exist_ok=True)
    db_path = os.path.join(WAREHOUSE_DIR, "warehouse.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE SCHEMA IF NOT EXISTS raw" if False else "SELECT 1")  # sqlite has no schemas; use table prefix

    for table, cols in TABLES.items():
        rows = read_csv_rows(table)
        raw_table = f"raw_{table}"
        cur.execute(f"DROP TABLE IF EXISTS {raw_table}")
        col_defs = ", ".join(f'"{c}"' for c in cols)
        cur.execute(f"CREATE TABLE {raw_table} ({col_defs})")
        placeholders = ", ".join(["?"] * len(cols))
        values = [[cast(r[c], c) for c in cols] for r in rows]
        cur.executemany(f"INSERT INTO {raw_table} VALUES ({placeholders})", values)
        print(f"[load:sqlite] {raw_table}: {len(values)} rows")

    conn.commit()
    conn.close()
    print(f"[load:sqlite] warehouse ready at {os.path.abspath(db_path)}")


def load_duckdb():
    import duckdb  # imported lazily so sqlite path never needs it installed
    os.makedirs(WAREHOUSE_DIR, exist_ok=True)
    db_path = os.path.join(WAREHOUSE_DIR, "warehouse.duckdb")
    con = duckdb.connect(db_path)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    for table in TABLES:
        csv_path = os.path.join(RAW_DIR, f"{table}.csv")
        con.execute(f"DROP TABLE IF EXISTS raw.{table}")
        con.execute(
            f"CREATE TABLE raw.{table} AS SELECT * FROM read_csv_auto('{csv_path}')"
        )
        count = con.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
        print(f"[load:duckdb] raw.{table}: {count} rows")

    con.close()
    print(f"[load:duckdb] warehouse ready at {os.path.abspath(db_path)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["sqlite", "duckdb"], default="sqlite")
    args = parser.parse_args()

    if args.engine == "sqlite":
        load_sqlite()
    else:
        load_duckdb()
