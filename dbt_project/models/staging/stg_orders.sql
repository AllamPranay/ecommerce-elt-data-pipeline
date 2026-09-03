with source as (
    select * from {{ source('raw', 'orders') }}
)

select
    order_id,
    customer_id,
    cast(order_timestamp as timestamp) as order_timestamp,
    cast(order_date as date) as order_date,
    payment_method,
    order_status,
    cast(order_total as decimal(10,2)) as order_total
from source
