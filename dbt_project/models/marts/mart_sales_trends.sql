-- Advanced SQL showcase #1: window functions for time-series trend analysis.
-- Everything here is computed in pure SQL (no pandas) -- moving averages,
-- period-over-period growth, and cumulative (YTD-style) revenue, all via
-- window functions with explicit frame clauses.
with daily as (
    select * from {{ ref('mart_daily_sales') }}
)

select
    order_date,
    gross_revenue,

    -- 7-day trailing moving average (rolling window frame)
    round(avg(gross_revenue) over (
        order by order_date
        rows between 6 preceding and current row
    ), 2) as revenue_7d_moving_avg,

    -- 30-day trailing moving average
    round(avg(gross_revenue) over (
        order by order_date
        rows between 29 preceding and current row
    ), 2) as revenue_30d_moving_avg,

    -- day-over-day growth %, using LAG to look at the previous row
    round(
        (gross_revenue - lag(gross_revenue) over (order by order_date))
        / nullif(lag(gross_revenue) over (order by order_date), 0) * 100
    , 2) as dod_growth_pct,

    -- cumulative revenue to date (running total via unbounded preceding frame)
    round(sum(gross_revenue) over (
        order by order_date
        rows between unbounded preceding and current row
    ), 2) as cumulative_revenue

from daily
order by order_date
