"""
test_pipeline.py
-----------------
Automated tests run in CI (see .github/workflows/ci.yml) on every push:
1. Runs the pipeline fresh (extract -> load -> transform)
2. Asserts row counts, referential integrity, and value ranges on the
   resulting warehouse -- catching the kind of silent data bugs that
   dbt tests + these pytest checks together are meant to prevent.
"""
import os
import sqlite3
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(ROOT, "data", "processed", "warehouse.db")


@pytest.fixture(scope="module", autouse=True)
def run_pipeline():
    subprocess.run([sys.executable, os.path.join(ROOT, "src", "extract.py")], check=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "src", "load.py"), "--engine", "sqlite"], check=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "src", "transform_local.py")], check=True)
    yield


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(DB_PATH)
    yield c
    c.close()


def scalar(conn, sql):
    return conn.execute(sql).fetchone()[0]


def test_raw_tables_not_empty(conn):
    for t in ["raw_customers", "raw_products", "raw_orders", "raw_order_items"]:
        assert scalar(conn, f"SELECT COUNT(*) FROM {t}") > 0


def test_dim_customers_unique_pk(conn):
    total = scalar(conn, "SELECT COUNT(*) FROM dim_customers")
    distinct = scalar(conn, "SELECT COUNT(DISTINCT customer_id) FROM dim_customers")
    assert total == distinct


def test_dim_products_unique_pk(conn):
    total = scalar(conn, "SELECT COUNT(*) FROM dim_products")
    distinct = scalar(conn, "SELECT COUNT(DISTINCT product_id) FROM dim_products")
    assert total == distinct


def test_fct_order_items_no_orphan_customers(conn):
    orphans = scalar(conn, """
        SELECT COUNT(*) FROM fct_order_items f
        LEFT JOIN dim_customers c ON f.customer_id = c.customer_id
        WHERE c.customer_id IS NULL
    """)
    assert orphans == 0


def test_fct_order_items_no_orphan_products(conn):
    orphans = scalar(conn, """
        SELECT COUNT(*) FROM fct_order_items f
        LEFT JOIN dim_products p ON f.product_id = p.product_id
        WHERE p.product_id IS NULL
    """)
    assert orphans == 0


def test_no_negative_revenue(conn):
    negative = scalar(conn, "SELECT COUNT(*) FROM mart_daily_sales WHERE gross_revenue < 0")
    assert negative == 0


def test_mart_daily_sales_date_unique(conn):
    total = scalar(conn, "SELECT COUNT(*) FROM mart_daily_sales")
    distinct = scalar(conn, "SELECT COUNT(DISTINCT order_date) FROM mart_daily_sales")
    assert total == distinct


def test_customer_order_summary_matches_order_items(conn):
    summary_total = scalar(conn, "SELECT ROUND(SUM(lifetime_revenue), 0) FROM mart_customer_order_summary")
    fct_total = scalar(conn, "SELECT ROUND(SUM(line_total), 0) FROM fct_order_items WHERE order_status != 'Cancelled'")
    assert summary_total == fct_total


def test_product_ranking_starts_at_one_per_category(conn):
    bad_categories = scalar(conn, """
        SELECT COUNT(*) FROM (
            SELECT category, MIN(rank_in_category) AS min_rank
            FROM mart_product_ranking GROUP BY category
        ) WHERE min_rank != 1
    """)
    assert bad_categories == 0


def test_sales_trends_cumulative_revenue_never_decreases(conn):
    violations = scalar(conn, """
        SELECT COUNT(*) FROM (
            SELECT cumulative_revenue,
                   LAG(cumulative_revenue) OVER (ORDER BY order_date) AS prev
            FROM mart_sales_trends
        ) WHERE cumulative_revenue < prev
    """)
    assert violations == 0


def test_market_basket_pairs_have_no_self_pairs(conn):
    self_pairs = scalar(conn, "SELECT COUNT(*) FROM mart_market_basket WHERE product_a = product_b")
    assert self_pairs == 0


def test_dim_date_recursive_cte_covers_full_order_range(conn):
    date_range = scalar(conn, "SELECT COUNT(*) FROM dim_date")
    order_span = scalar(conn, "SELECT CAST(julianday(MAX(order_date)) - julianday(MIN(order_date)) AS INTEGER) + 1 FROM stg_orders")
    assert date_range == order_span
