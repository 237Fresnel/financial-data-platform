with source as (
    select * from {{ source('raw', 'customers') }}
)

select
    nullif(trim(customer_id), '')  as customer_id,
    upper(trim(country))           as country,
    lower(trim(segment))           as segment,
    case when pg_input_is_valid(created_at, 'date')
         then created_at::date end as created_at,
    ingested_at
from source