# Power BI Dashboard — Build Guide

The pipeline exports star-schema-ready CSVs to `dashboards/powerbi_data/`.
Build a real dashboard on top of them in ~30 minutes:

## 1. Load data
Power BI Desktop → **Get Data → Folder** → select `dashboards/powerbi_data/`
→ **Combine & Transform** is *not* needed here (each file is its own table) →
instead use **Get Data → Text/CSV** once per file, or select all and
choose "Load" individually so each becomes its own table:
`dim_customers`, `dim_products`, `dim_date`, `fct_order_items`,
`mart_daily_sales`, `mart_customer_order_summary`, `mart_sales_trends`,
`mart_product_ranking`, `mart_monthly_category_revenue`, `mart_market_basket`.

The last four (`mart_sales_trends`, `mart_product_ranking`,
`mart_monthly_category_revenue`, `mart_market_basket`) are already computed
in SQL (moving averages, rankings, pivots, basket pairs) — load them as
standalone tables and build visuals straight off them without needing extra
DAX measures for that logic.

## 2. Build the model (Model view)
Create these relationships (drag field → field):
- `fct_order_items[customer_id]` → `dim_customers[customer_id]` (many-to-one)
- `fct_order_items[product_id]` → `dim_products[product_id]` (many-to-one)
- `fct_order_items[order_date]` → `dim_date[date_day]` (many-to-one)
- `mart_daily_sales[order_date]` → `dim_date[date_day]` (many-to-one)

This is a proper star schema — fact table in the middle, dimensions
around it. Mention this explicitly in the interview; it's exactly how
production BI semantic models are built.

## 3. Key DAX measures to add
```
Total Revenue        = SUM(fct_order_items[line_total])
Total Profit          = SUM(fct_order_items[gross_profit])
Profit Margin %       = DIVIDE([Total Profit], [Total Revenue])
Orders                = DISTINCTCOUNT(fct_order_items[order_id])
Avg Order Value        = DIVIDE([Total Revenue], [Orders])
Revenue MoM Growth %  = 
    VAR CurrMonth = [Total Revenue]
    VAR PrevMonth = CALCULATE([Total Revenue], DATEADD(dim_date[date_day], -1, MONTH))
    RETURN DIVIDE(CurrMonth - PrevMonth, PrevMonth)
```

## 4. Suggested pages
1. **Executive Overview** — KPI cards (Revenue, Profit, Orders, AOV),
   revenue trend line by `dim_date`, revenue by category (donut).
2. **Customer Analytics** — customer segment breakdown, top-20
   customers by lifetime revenue (from `mart_customer_order_summary`), city/country
   map visual, days-since-last-order histogram (churn-risk signal).
3. **Product Performance** — revenue & margin by category/product,
   discount impact analysis (`discount_pct` vs `line_total`).
4. **Forecast** — import `ml/forecast_output.csv` as a 7th table, plot
   actual `mart_daily_sales[gross_revenue]` alongside the forecast on
   one line chart to show the ML output feeding back into BI.

## 5. Publish
Save as `dashboards/ecommerce_dashboard.pbix`. If you have a Power BI
Service license, publish and screenshot it for your resume/portfolio —
a live dashboard link is a strong interview talking point.

## Alternative: live connection (no static CSV refresh needed)
Power BI Desktop can connect directly to DuckDB via its ODBC driver, or
to `warehouse.db` via the community SQLite connector, so the dashboard
auto-refreshes whenever the pipeline reruns — mention this as the
"production" version of the setup above if asked how you'd operationalize it.
