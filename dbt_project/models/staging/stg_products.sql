with source as (
    select * from {{ source('raw', 'products') }}
)

select
    product_id,
    product_name,
    category,
    cast(unit_price as decimal(10,2)) as unit_price,
    cast(cost_price as decimal(10,2)) as cost_price,
    round(
        (cast(unit_price as decimal(10,2)) - cast(cost_price as decimal(10,2)))
        / nullif(cast(unit_price as decimal(10,2)), 0) * 100, 2
    ) as margin_pct
from source
