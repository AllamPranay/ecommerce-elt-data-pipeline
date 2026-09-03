-- Generated date spine covering the full order history range.
-- A dim_date table is a standard-practice star-schema component --
-- it lets BI tools do calendar-aware slicing (weekday, quarter, etc.)
-- without recomputing it in every report.
with bounds as (
    select
        min(order_date) as min_date,
        max(order_date) as max_date
    from {{ ref('stg_orders') }}
),
spine as (
    select unnest(generate_series(
        (select min_date from bounds),
        (select max_date from bounds),
        interval 1 day
    )) as date_day
)

select
    date_day,
    extract(year from date_day) as year,
    extract(month from date_day) as month,
    strftime(date_day, '%B') as month_name,
    strftime(date_day, '%A') as day_name,
    extract(dow from date_day) in (0, 6) as is_weekend,
    extract(quarter from date_day) as quarter
from spine
