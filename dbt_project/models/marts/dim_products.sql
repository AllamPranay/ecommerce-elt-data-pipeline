select
    product_id,
    product_name,
    category,
    unit_price,
    cost_price,
    margin_pct
from {{ ref('stg_products') }}
