# Interview Prep — Talking Points & Likely Questions

Read this once before your interview. Every answer here is grounded in a
real design decision you actually made in this repo — don't memorize
verbatim, understand the *reasoning* so you can handle follow-ups.

## The 30-second pitch
"I built an end-to-end ELT pipeline for e-commerce sales data. It extracts
transactional data, loads it into a warehouse, transforms it into a star
schema using dbt with automated tests, and serves that to both a Power BI
dashboard and a scikit-learn forecasting model. It's orchestrated with
Airflow and runs through CI on every push. I focused on making it something
that actually runs end-to-end and is tested, not just a notebook."

## Architecture & design decisions

**Q: Why ELT instead of ETL?**
Modern warehouses (DuckDB, Snowflake, BigQuery) are fast enough to
transform data *after* loading it raw, using SQL. That keeps the raw
layer as an unmodified source of truth you can always re-derive marts
from, and lets the transformation logic live in version-controlled SQL
(dbt) instead of scattered Python scripts.

**Q: Why dbt instead of just writing SQL scripts?**
dbt gives you dependency management (`ref()` builds a DAG automatically),
built-in testing (`unique`, `not_null`, `relationships`), documentation,
and the ability to materialize as views vs. tables per model. Writing raw
SQL scripts means manually tracking execution order and reinventing all
of that.

**Q: Why DuckDB and not Postgres/Snowflake?**
DuckDB is an embedded, columnar OLAP engine — no server to run, fast for
analytical (aggregate-heavy) queries, and it's become the default choice
for "local-first" / small-to-medium data engineering work in the last
couple of years. For a real multi-user production warehouse I'd move to
Postgres, Snowflake, or BigQuery — the dbt models wouldn't need to change,
just the `profiles.yml` connection.

**Q: Why is there both a SQLite path and a DuckDB path?**
Practical constraint: I wanted the repo to run instantly for anyone who
clones it with zero installs (SQLite is stdlib), while still documenting
the actual production-grade path (dbt + DuckDB). It's also a legitimate
engineering pattern — develop against a lightweight local engine, swap
the connection for production.

**Q: What's the grain of your fact table?**
`fct_order_items` is one row per order line item — the finest grain
available. Every other mart (`mart_daily_sales`, `mart_product_ranking`)
aggregates up from it. Picking the finest grain up front means you can
always aggregate up later without re-deriving from raw data.

**Q: How would you handle late-arriving or updated data?**
Right now it's a full-refresh pattern (drop and recreate tables each run)
— fine for this data volume. At real scale I'd move to incremental dbt
models (`materialized='incremental'`) that only process new/changed rows,
using a watermark column like `order_timestamp`, plus `dbt snapshot` for
tracking slowly-changing dimensions like customer attributes over time.

**Q: How would you scale this to real streaming/high-volume data?**
Swap the batch extract for a CDC tool (Debezium) or event stream (Kafka/
Kinesis) landing in a bronze layer continuously, partition the warehouse
tables by date, move orchestration to a managed Airflow, and add
incremental dbt models instead of full-refresh ones.

## SQL — be ready to write these live

**Q: Explain your `mart_product_ranking` query.**
Walk through: CTE aggregates revenue per product, then `DENSE_RANK() OVER
(PARTITION BY category ORDER BY total_revenue DESC)` ranks within each
category without skipping numbers on ties, and a windowed `SUM()` with a
`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` frame computes running
cumulative revenue share — this is standard Pareto ("what % of revenue
comes from the top N products") analysis.

**Q: RANK vs DENSE_RANK vs ROW_NUMBER — what's the difference?**
`ROW_NUMBER()` always gives unique sequential numbers regardless of ties.
`RANK()` gives ties the same rank but skips the next number (1,1,3).
`DENSE_RANK()` gives ties the same rank without skipping (1,1,2). See
`sql/advanced_sql_showcase.sql` section 3 for a side-by-side query.

**Q: Why a recursive CTE for the date dimension instead of a loop in Python?**
Portability — a recursive CTE is standard ANSI SQL that works unmodified
on Postgres, SQL Server, Snowflake, and SQLite. `generate_series()` is
DuckDB/Postgres-specific. Doing it in SQL also means the date dimension is
part of the queryable warehouse, not a side artifact.

**Q: Write a query to find the second-highest value per group.**
```sql
SELECT * FROM (
    SELECT *, DENSE_RANK() OVER (PARTITION BY category ORDER BY total_revenue DESC) AS rnk
    FROM mart_product_ranking
) WHERE rnk = 2;
```

**Q: HAVING vs WHERE?**
`WHERE` filters rows before aggregation; `HAVING` filters groups after
aggregation. You can't reference an aggregate function in `WHERE`.

**Q: How does your market basket query avoid double-counting pairs?**
The self-join condition `a.product_id < b.product_id` — this ensures
each unordered pair (A,B) is counted once instead of twice (as both
(A,B) and (B,A)), and excludes a product pairing with itself.

## ML component (keep this modest and honest)

**Q: Why RandomForest and not ARIMA/Prophet for time series?**
RandomForest handles the non-linear weekend/seasonal pattern well, is
easy to explain via feature importance, and doesn't require the
stationarity assumptions classical time-series models do. For a more
rigorous production forecast I'd compare it against Prophet or SARIMA as
a baseline.

**Q: How did you validate the model?**
Time-based train/test split (last ~15% of days held out) — never shuffle
time series data, since that leaks future information into training. I
report MAE and MAPE on the untouched holdout period.

**Q: What's a recursive multi-step forecast?**
To predict 14 days ahead with lag features, you predict day 1, then feed
that prediction back in as `lag_1` to predict day 2, and so on. Error can
compound over the horizon — worth mentioning as a known limitation.

## Testing & CI

**Q: What happens if a data quality test fails?**
The pipeline raises and stops (see `transform_local.py`'s exit code, and
dbt's own test failures) — bad data never silently reaches the dashboard
or the ML model. In CI, a failed test fails the GitHub Actions run.

**Q: What's the difference between your dbt tests and your pytest suite?**
dbt tests (`schema.yml`) check the models dbt itself builds — uniqueness,
not-null, referential integrity, accepted values. The pytest suite
(`tests/test_pipeline.py`) is engine-agnostic — it runs the whole pipeline
fresh and asserts on the resulting SQLite database, which is what CI
actually executes since dbt/DuckDB aren't installed there by default.

## If they ask about your other two projects
Be upfront about the split: this project is the *infrastructure* story
(how you move, model, and test data at scale). Your job-market-analysis
project is a *data analysis* story. Your customer-retention project is
an *ML/analytics* story. Three different skill sets, deliberately not
overlapping — that's a stronger portfolio than three variations on the
same theme.
