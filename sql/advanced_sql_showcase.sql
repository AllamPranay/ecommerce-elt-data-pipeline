-- ============================================================================
-- advanced_sql_showcase.sql
-- ============================================================================
-- Standalone, heavily-commented reference of the advanced SQL techniques
-- used in this pipeline (see dbt_project/models/marts/ for the versions
-- wired into the actual pipeline, and src/transform_local.py for the
-- SQLite-compatible versions you can run right now).
--
-- Run against data/processed/warehouse.db after running the pipeline:
--   sqlite3 data/processed/warehouse.db < sql/advanced_sql_showcase.sql
--
-- This file exists so you can quickly review/practice these patterns
-- before an interview -- each one is a technique that comes up constantly
-- in SQL screening rounds.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. WINDOW FUNCTIONS: running total + moving average with explicit frames
-- ----------------------------------------------------------------------------
-- ROWS BETWEEN ... AND CURRENT ROW defines exactly which rows are included
-- in each window -- this is what separates a "moving" average from a
-- full-partition average.
SELECT
    order_date,
    gross_revenue,
    SUM(gross_revenue) OVER (
        ORDER BY order_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_total,
    AVG(gross_revenue) OVER (
        ORDER BY order_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS moving_avg_7d
FROM mart_daily_sales
ORDER BY order_date;


-- ----------------------------------------------------------------------------
-- 2. LAG/LEAD: period-over-period comparison without a self-join
-- ----------------------------------------------------------------------------
-- LAG(x, n) looks n rows behind the current row in the specified order --
-- this is the standard way to compute period-over-period deltas in SQL
-- (the alternative, a self-join on date - 1, is far more verbose).
SELECT
    order_date,
    gross_revenue,
    LAG(gross_revenue, 1) OVER (ORDER BY order_date) AS prev_day_revenue,
    gross_revenue - LAG(gross_revenue, 1) OVER (ORDER BY order_date) AS day_over_day_change
FROM mart_daily_sales
ORDER BY order_date;


-- ----------------------------------------------------------------------------
-- 3. RANK / DENSE_RANK / ROW_NUMBER -- know the difference
-- ----------------------------------------------------------------------------
-- ROW_NUMBER: always unique, arbitrary tiebreak.
-- RANK: ties share a rank, next rank skips (1,1,3).
-- DENSE_RANK: ties share a rank, next rank does NOT skip (1,1,2).
SELECT
    product_name,
    category,
    total_revenue,
    ROW_NUMBER() OVER (PARTITION BY category ORDER BY total_revenue DESC) AS row_num,
    RANK()       OVER (PARTITION BY category ORDER BY total_revenue DESC) AS rnk,
    DENSE_RANK() OVER (PARTITION BY category ORDER BY total_revenue DESC) AS dense_rnk
FROM mart_product_ranking;


-- ----------------------------------------------------------------------------
-- 4. NTILE: bucket rows into N equal-sized groups (e.g. quartiles)
-- ----------------------------------------------------------------------------
SELECT
    customer_id,
    lifetime_revenue,
    NTILE(4) OVER (ORDER BY lifetime_revenue DESC) AS revenue_quartile
FROM mart_customer_order_summary
WHERE total_orders > 0;


-- ----------------------------------------------------------------------------
-- 5. RECURSIVE CTE: generate a date spine without a calendar table
-- ----------------------------------------------------------------------------
-- Portable to any SQL engine (Postgres, SQL Server, Snowflake, SQLite) --
-- unlike generate_series(), which is DuckDB/Postgres-specific.
WITH RECURSIVE date_spine(d) AS (
    SELECT DATE('2026-01-01')
    UNION ALL
    SELECT DATE(d, '+1 day') FROM date_spine WHERE d < DATE('2026-01-31')
)
SELECT d AS calendar_date FROM date_spine;


-- ----------------------------------------------------------------------------
-- 6. SELF-JOIN: market basket analysis (frequently bought together)
-- ----------------------------------------------------------------------------
-- Join the same table to itself on order_id to find every pair of
-- products that appear in the same order. The a.product_id < b.product_id
-- guard avoids counting (A,B) and (B,A) separately and excludes self-pairs.
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
ORDER BY times_bought_together DESC
LIMIT 10;


-- ----------------------------------------------------------------------------
-- 7. SQL-ONLY PIVOT via conditional aggregation
-- ----------------------------------------------------------------------------
-- Turns long-format rows into wide-format columns without a native PIVOT
-- keyword -- works on every SQL engine.
SELECT
    STRFTIME('%Y-%m', order_date) AS month,
    SUM(CASE WHEN category = 'Electronics' THEN line_total ELSE 0 END) AS electronics,
    SUM(CASE WHEN category = 'Fashion'     THEN line_total ELSE 0 END) AS fashion,
    SUM(CASE WHEN category = 'Books'       THEN line_total ELSE 0 END) AS books
FROM fct_order_items
GROUP BY month
ORDER BY month;


-- ----------------------------------------------------------------------------
-- 8. CTE vs SUBQUERY -- same logic, readability comparison
-- ----------------------------------------------------------------------------
-- Subquery version (harder to read as logic grows):
SELECT customer_id, lifetime_revenue
FROM (
    SELECT customer_id, SUM(line_total) AS lifetime_revenue
    FROM fct_order_items
    WHERE order_status != 'Cancelled'
    GROUP BY customer_id
) sub
WHERE lifetime_revenue > 50000;

-- Equivalent CTE version (named, referenceable, easier to chain):
WITH customer_revenue AS (
    SELECT customer_id, SUM(line_total) AS lifetime_revenue
    FROM fct_order_items
    WHERE order_status != 'Cancelled'
    GROUP BY customer_id
)
SELECT customer_id, lifetime_revenue
FROM customer_revenue
WHERE lifetime_revenue > 50000;


-- ----------------------------------------------------------------------------
-- 9. HAVING vs WHERE -- filtering on an aggregate
-- ----------------------------------------------------------------------------
-- WHERE filters rows BEFORE aggregation; HAVING filters groups AFTER
-- aggregation -- a very common interview gotcha question.
SELECT category, COUNT(*) AS num_products, AVG(unit_price) AS avg_price
FROM dim_products
GROUP BY category
HAVING AVG(unit_price) > 1000;
