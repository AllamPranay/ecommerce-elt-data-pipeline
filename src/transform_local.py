"""
transform_local.py
-------------------
A zero-dependency runner that executes the SAME transformation logic
as the dbt models in /dbt_project/models against the SQLite warehouse,
using SQLite-compatible SQL.

Why this exists: dbt + DuckDB are the production-grade path documented
in /dbt_project (industry-standard tooling, meant to be run with
`dbt build` once you `pip install dbt-core dbt-duckdb`). This script
lets the whole pipeline be cloned and run end-to-end with just the
Python standard library -- no installs, no internet -- so you (or an
interviewer) can verify it works in 10 seconds. The star schema design
and business logic are identical between the two; only SQL dialect
syntax differs in a couple of places (e.g. dim_date uses a recursive
CTE here since SQLite has no generate_series, whereas the dbt/DuckDB
version uses generate_series directly).
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "warehouse.db")


def run():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    cur = conn.cursor()

    # ---------- staging (views -> materialized here as tables for simplicity) ----------
    cur.executescript("""
    DROP TABLE IF EXISTS stg_customers;
    CREATE TABLE stg_customers AS
    SELECT
        customer_id,
        TRIM(first_name) AS first_name,
        TRIM(last_name) AS last_name,
        TRIM(first_name) || ' ' || TRIM(last_name) AS full_name,
        LOWER(email) AS email,
        city, country,
        DATE(signup_date) AS signup_date,
        customer_segment
    FROM raw_customers;

    DROP TABLE IF EXISTS stg_products;
    CREATE TABLE stg_products AS
    SELECT
        product_id, product_name, category,
        ROUND(unit_price, 2) AS unit_price,
        ROUND(cost_price, 2) AS cost_price,
        ROUND((unit_price - cost_price) / NULLIF(unit_price, 0) * 100, 2) AS margin_pct
    FROM raw_products;

    DROP TABLE IF EXISTS stg_orders;
    CREATE TABLE stg_orders AS
    SELECT
        order_id, customer_id, order_timestamp,
        DATE(order_date) AS order_date,
        payment_method, order_status,
        ROUND(order_total, 2) AS order_total
    FROM raw_orders;

    DROP TABLE IF EXISTS stg_order_items;
    CREATE TABLE stg_order_items AS
    SELECT
        order_item_id, order_id, product_id, quantity,
        ROUND(unit_price, 2) AS unit_price,
        ROUND(discount_pct, 2) AS discount_pct,
        ROUND(line_total, 2) AS line_total
    FROM raw_order_items;
    """)

    # ---------- dim_date: RECURSIVE CTE date spine ----------
    # SQLite has no generate_series, so a recursive CTE is the portable
    # way to build a calendar dimension -- and it's the same pattern
    # that works unmodified on Postgres, SQL Server, Snowflake, etc.
    # (DuckDB gets the equivalent generate_series version -- see
    # dbt_project/models/marts/dim_date.sql.)
    cur.executescript("""
    DROP TABLE IF EXISTS dim_date;
    CREATE TABLE dim_date AS
    WITH RECURSIVE bounds AS (
        SELECT MIN(order_date) AS min_date, MAX(order_date) AS max_date
        FROM stg_orders
    ),
    date_spine(date_day) AS (
        SELECT min_date FROM bounds
        UNION ALL
        SELECT DATE(date_day, '+1 day')
        FROM date_spine, bounds
        WHERE date_day < max_date
    )
    SELECT
        date_day,
        CAST(STRFTIME('%Y', date_day) AS INTEGER) AS year,
        CAST(STRFTIME('%m', date_day) AS INTEGER) AS month,
        CASE STRFTIME('%m', date_day)
            WHEN '01' THEN 'January' WHEN '02' THEN 'February' WHEN '03' THEN 'March'
            WHEN '04' THEN 'April' WHEN '05' THEN 'May' WHEN '06' THEN 'June'
            WHEN '07' THEN 'July' WHEN '08' THEN 'August' WHEN '09' THEN 'September'
            WHEN '10' THEN 'October' WHEN '11' THEN 'November' ELSE 'December'
        END AS month_name,
        CASE STRFTIME('%w', date_day)
            WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday'
            WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday'
            ELSE 'Saturday'
        END AS day_name,
        CASE WHEN STRFTIME('%w', date_day) IN ('0', '6') THEN 1 ELSE 0 END AS is_weekend,
        ((CAST(STRFTIME('%m', date_day) AS INTEGER) - 1) / 3) + 1 AS quarter
    FROM date_spine;
    """)

    # ---------- core marts ----------
    cur.executescript("""
    DROP TABLE IF EXISTS dim_customers;
    CREATE TABLE dim_customers AS
    SELECT
        customer_id, full_name, email, city, country, signup_date, customer_segment,
        CAST(julianday('now') - julianday(signup_date) AS INTEGER) AS days_since_signup
    FROM stg_customers;

    DROP TABLE IF EXISTS dim_products;
    CREATE TABLE dim_products AS
    SELECT product_id, product_name, category, unit_price, cost_price, margin_pct
    FROM stg_products;

    DROP TABLE IF EXISTS fct_order_items;
    CREATE TABLE fct_order_items AS
    SELECT
        oi.order_item_id, oi.order_id, o.customer_id, oi.product_id,
        o.order_date, o.order_status, o.payment_method,
        oi.quantity, oi.unit_price, oi.discount_pct, oi.line_total,
        p.product_name, p.category, p.cost_price,
        ROUND(oi.line_total - (p.cost_price * oi.quantity), 2) AS gross_profit
    FROM stg_order_items oi
    JOIN stg_orders o ON oi.order_id = o.order_id
    JOIN stg_products p ON oi.product_id = p.product_id;

    DROP TABLE IF EXISTS mart_daily_sales;
    CREATE TABLE mart_daily_sales AS
    SELECT
        order_date,
        COUNT(DISTINCT order_id) AS num_orders,
        COUNT(DISTINCT customer_id) AS num_unique_customers,
        SUM(quantity) AS units_sold,
        SUM(line_total) AS gross_revenue,
        SUM(gross_profit) AS gross_profit,
        ROUND(SUM(line_total) * 1.0 / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS avg_order_value
    FROM fct_order_items
    WHERE order_status != 'Cancelled'
    GROUP BY order_date
    ORDER BY order_date;

    DROP TABLE IF EXISTS mart_customer_order_summary;
    CREATE TABLE mart_customer_order_summary AS
    SELECT
        c.customer_id, c.full_name, c.city, c.country,
        COUNT(DISTINCT f.order_id) AS total_orders,
        COALESCE(SUM(f.line_total), 0) AS lifetime_revenue,
        ROUND(AVG(f.line_total), 2) AS avg_line_value,
        MAX(f.order_date) AS last_order_date,
        CAST(julianday('now') - julianday(MAX(f.order_date)) AS INTEGER) AS days_since_last_order
    FROM dim_customers c
    LEFT JOIN fct_order_items f
        ON c.customer_id = f.customer_id AND f.order_status != 'Cancelled'
    GROUP BY c.customer_id, c.full_name, c.city, c.country;
    """)

    # ---------- advanced SQL marts (window functions, self-join, pivot) ----------
    cur.executescript("""
    DROP TABLE IF EXISTS mart_sales_trends;
    CREATE TABLE mart_sales_trends AS
    SELECT
        order_date,
        gross_revenue,
        ROUND(AVG(gross_revenue) OVER (
            ORDER BY order_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ), 2) AS revenue_7d_moving_avg,
        ROUND(AVG(gross_revenue) OVER (
            ORDER BY order_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ), 2) AS revenue_30d_moving_avg,
        ROUND(
            (gross_revenue - LAG(gross_revenue) OVER (ORDER BY order_date))
            * 100.0 / NULLIF(LAG(gross_revenue) OVER (ORDER BY order_date), 0)
        , 2) AS dod_growth_pct,
        ROUND(SUM(gross_revenue) OVER (
            ORDER BY order_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ), 2) AS cumulative_revenue
    FROM mart_daily_sales
    ORDER BY order_date;

    DROP TABLE IF EXISTS mart_product_ranking;
    CREATE TABLE mart_product_ranking AS
    WITH product_revenue AS (
        SELECT product_id, product_name, category,
               SUM(line_total) AS total_revenue,
               SUM(quantity) AS total_units_sold
        FROM fct_order_items
        WHERE order_status != 'Cancelled'
        GROUP BY product_id, product_name, category
    )
    SELECT
        product_id, product_name, category, total_revenue, total_units_sold,
        DENSE_RANK() OVER (PARTITION BY category ORDER BY total_revenue DESC) AS rank_in_category,
        ROUND(total_revenue * 100.0 / SUM(total_revenue) OVER (PARTITION BY category), 2) AS pct_of_category_revenue,
        ROUND(
            SUM(total_revenue) OVER (
                PARTITION BY category ORDER BY total_revenue DESC
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) * 100.0 / SUM(total_revenue) OVER (PARTITION BY category)
        , 2) AS cumulative_pct_of_category_revenue
    FROM product_revenue
    ORDER BY category, rank_in_category;

    DROP TABLE IF EXISTS mart_monthly_category_revenue;
    CREATE TABLE mart_monthly_category_revenue AS
    SELECT
        STRFTIME('%Y-%m', order_date) AS month,
        SUM(CASE WHEN category = 'Electronics' THEN line_total ELSE 0 END) AS electronics_revenue,
        SUM(CASE WHEN category = 'Fashion' THEN line_total ELSE 0 END) AS fashion_revenue,
        SUM(CASE WHEN category = 'Home & Kitchen' THEN line_total ELSE 0 END) AS home_kitchen_revenue,
        SUM(CASE WHEN category = 'Books' THEN line_total ELSE 0 END) AS books_revenue,
        SUM(CASE WHEN category = 'Sports' THEN line_total ELSE 0 END) AS sports_revenue,
        SUM(line_total) AS total_revenue
    FROM fct_order_items
    WHERE order_status != 'Cancelled'
    GROUP BY month
    ORDER BY month;

    DROP TABLE IF EXISTS mart_market_basket;
    CREATE TABLE mart_market_basket AS
    WITH order_products AS (
        SELECT DISTINCT order_id, product_id FROM fct_order_items
    )
    SELECT
        a.product_id AS product_a,
        b.product_id AS product_b,
        COUNT(DISTINCT a.order_id) AS times_bought_together
    FROM order_products a
    JOIN order_products b
        ON a.order_id = b.order_id AND a.product_id < b.product_id
    GROUP BY a.product_id, b.product_id
    HAVING COUNT(DISTINCT a.order_id) >= 5
    ORDER BY times_bought_together DESC;
    """)

    conn.commit()

    # ---------- data-quality checks (mirrors dbt schema tests) ----------
    checks = [
        ("dim_customers has no duplicate customer_id",
         "SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM dim_customers", 0),
        ("dim_date has no duplicate date_day",
         "SELECT COUNT(*) - COUNT(DISTINCT date_day) FROM dim_date", 0),
        ("fct_order_items has no null customer_id",
         "SELECT COUNT(*) FROM fct_order_items WHERE customer_id IS NULL", 0),
        ("every fct_order_items.product_id exists in dim_products",
         """SELECT COUNT(*) FROM fct_order_items f
            LEFT JOIN dim_products p ON f.product_id = p.product_id
            WHERE p.product_id IS NULL""", 0),
        ("mart_daily_sales has no duplicate order_date",
         "SELECT COUNT(*) - COUNT(DISTINCT order_date) FROM mart_daily_sales", 0),
        ("mart_product_ranking rank_in_category starts at 1 per category",
         """SELECT COUNT(*) FROM (
                SELECT category, MIN(rank_in_category) AS min_rank
                FROM mart_product_ranking GROUP BY category
            ) WHERE min_rank != 1""", 0),
        ("mart_sales_trends cumulative_revenue is non-decreasing",
         """SELECT COUNT(*) FROM (
                SELECT cumulative_revenue,
                       LAG(cumulative_revenue) OVER (ORDER BY order_date) AS prev
                FROM mart_sales_trends
            ) WHERE cumulative_revenue < prev""", 0),
    ]
    print("\n[transform] running data quality checks (equivalent to dbt tests)...")
    all_passed = True
    for name, sql, expected in checks:
        result = cur.execute(sql).fetchone()[0]
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] {name} (got {result}, expected {expected})")

    for tbl in ["stg_customers", "stg_products", "stg_orders", "stg_order_items",
                "dim_customers", "dim_products", "dim_date", "fct_order_items",
                "mart_daily_sales", "mart_customer_order_summary",
                "mart_sales_trends", "mart_product_ranking",
                "mart_monthly_category_revenue", "mart_market_basket"]:
        n = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"[transform] {tbl}: {n} rows")

    conn.close()
    if not all_passed:
        raise SystemExit("Data quality checks failed -- see log above.")
    print("\n[transform] all checks passed. Marts are ready in warehouse.db")


if __name__ == "__main__":
    run()
