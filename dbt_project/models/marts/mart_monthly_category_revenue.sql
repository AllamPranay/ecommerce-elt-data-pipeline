-- Advanced SQL showcase #3: SQL-only pivot via conditional aggregation.
-- Turns long-format (one row per order item) into wide-format
-- (one row per month, one column per category) without any pivot
-- extension -- portable to any SQL engine including ones without a
-- native PIVOT keyword.
select
    strftime(order_date, '%Y-%m') as month,
    sum(case when category = 'Electronics' then line_total else 0 end) as electronics_revenue,
    sum(case when category = 'Fashion' then line_total else 0 end) as fashion_revenue,
    sum(case when category = 'Home & Kitchen' then line_total else 0 end) as home_kitchen_revenue,
    sum(case when category = 'Books' then line_total else 0 end) as books_revenue,
    sum(case when category = 'Sports' then line_total else 0 end) as sports_revenue,
    sum(line_total) as total_revenue
from {{ ref('fct_order_items') }}
where order_status != 'Cancelled'
group by 1
order by 1
