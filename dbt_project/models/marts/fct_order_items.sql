-- Grain: one row per order line item. This is the finest-grained
-- fact table -- all other marts (daily sales, customer LTV) roll up
-- from this one, which is standard Kimball-style dimensional design.
select
    oi.order_item_id,
    oi.order_id,
    o.customer_id,
    oi.product_id,
    o.order_date,
    o.order_status,
    o.payment_method,
    oi.quantity,
    oi.unit_price,
    oi.discount_pct,
    oi.line_total,
    p.product_name,
    p.category,
    p.cost_price,
    round(oi.line_total - (p.cost_price * oi.quantity), 2) as gross_profit
from {{ ref('stg_order_items') }} oi
join {{ ref('stg_orders') }} o on oi.order_id = o.order_id
join {{ ref('stg_products') }} p on oi.product_id = p.product_id
