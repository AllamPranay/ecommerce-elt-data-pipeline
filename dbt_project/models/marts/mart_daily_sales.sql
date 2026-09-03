-- Aggregated daily sales -- the primary table the Power BI dashboard
-- and the ML forecasting model both read from.
select
    order_date,
    count(distinct order_id) as num_orders,
    count(distinct customer_id) as num_unique_customers,
    sum(quantity) as units_sold,
    sum(line_total) as gross_revenue,
    sum(gross_profit) as gross_profit,
    round(sum(line_total) / nullif(count(distinct order_id), 0), 2) as avg_order_value
from {{ ref('fct_order_items') }}
where order_status != 'Cancelled'
group by 1
order by 1
