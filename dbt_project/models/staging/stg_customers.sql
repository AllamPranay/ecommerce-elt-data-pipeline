-- Staging: light cleanup/renaming only. No business logic here.
with source as (
    select * from {{ source('raw', 'customers') }}
)

select
    customer_id,
    trim(first_name) as first_name,
    trim(last_name) as last_name,
    trim(first_name) || ' ' || trim(last_name) as full_name,
    lower(email) as email,
    city,
    country,
    cast(signup_date as date) as signup_date,
    customer_segment
from source
