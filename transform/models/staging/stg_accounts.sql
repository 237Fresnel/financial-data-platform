with source as (
    select * from {{ source('raw', 'accounts') }}
)

select
    nullif(trim(account_id), '')   as account_id,
    nullif(trim(customer_id), '')  as customer_id,
    upper(trim(currency))          as currency,
    lower(trim(status))            as status,
    case when pg_input_is_valid(created_at, 'date')
         then created_at::date end as created_at,
    ingested_at
from source