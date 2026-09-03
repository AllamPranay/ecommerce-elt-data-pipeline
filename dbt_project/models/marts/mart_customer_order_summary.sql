-- Supporting mart: per-customer order-history summary used by the BI
-- dashboard's customer page (total orders, revenue, recency). This is
-- a standard warehouse mart, not a segmentation/churn model -- that
-- kind of analysis lives in a separate project, this one just needs
-- the aggregate numbers to drive the dashboard.
select
    c.customer_id,
    c.full_name,
    c.city,
    c.country,
    count(distinct f.order_id) as total_orders,
    sum(f.line_total) as lifetime_revenue,
    round(avg(f.line_total), 2) as avg_line_value,
    max(f.order_date) as last_order_date,
    date_diff('day', max(f.order_date), current_date) as days_since_last_order
from {{ ref('dim_customers') }} c
left join {{ ref('fct_order_items') }} f on c.customer_id = f.customer_id
where f.order_status != 'Cancelled' or f.order_status is null
group by 1, 2, 3, 4
