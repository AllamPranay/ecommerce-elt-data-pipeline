select
    customer_id,
    full_name,
    email,
    city,
    country,
    signup_date,
    customer_segment,
    date_diff('day', signup_date, current_date) as days_since_signup
from {{ ref('stg_customers') }}
