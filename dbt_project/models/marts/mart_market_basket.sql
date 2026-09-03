-- Advanced SQL showcase #4: self-join for "frequently bought together"
-- market-basket analysis -- a classic warehouse/analytics-engineering
-- deliverable, computed entirely with a self-join + aggregation (no
-- external association-rule-mining library needed for a first pass).
with order_products as (
    select distinct order_id, product_id
    from {{ ref('fct_order_items') }}
)

select
    a.product_id as product_a,
    b.product_id as product_b,
    count(distinct a.order_id) as times_bought_together
from order_products a
join order_products b
    on a.order_id = b.order_id
    and a.product_id < b.product_id   -- avoid double-counting (A,B) and (B,A), and self-pairs
group by a.product_id, b.product_id
having count(distinct a.order_id) >= 5
order by times_bought_together desc
