-- Advanced SQL showcase #2: ranking + cumulative share window functions.
-- Ranks every product within its category by revenue, and computes what
-- % of the category's total revenue each product represents -- the kind
-- of "top N per group" query that comes up constantly in DE interviews.
with product_revenue as (
    select
        product_id,
        product_name,
        category,
        sum(line_total) as total_revenue,
        sum(quantity) as total_units_sold
    from {{ ref('fct_order_items') }}
    where order_status != 'Cancelled'
    group by 1, 2, 3
)

select
    product_id,
    product_name,
    category,
    total_revenue,
    total_units_sold,

    -- rank within category (ties share the same rank, no gaps skipped -> dense_rank)
    dense_rank() over (
        partition by category order by total_revenue desc
    ) as rank_in_category,

    -- this product's revenue as a % of its category's total revenue
    round(
        total_revenue / sum(total_revenue) over (partition by category) * 100
    , 2) as pct_of_category_revenue,

    -- cumulative revenue share within category, ordered by rank
    -- (classic input to a Pareto / "80-20" analysis)
    round(
        sum(total_revenue) over (
            partition by category order by total_revenue desc
            rows between unbounded preceding and current row
        ) / sum(total_revenue) over (partition by category) * 100
    , 2) as cumulative_pct_of_category_revenue

from product_revenue
order by category, rank_in_category
