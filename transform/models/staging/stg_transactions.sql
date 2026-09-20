with source as (
    select * from {{ source('raw', 'transactions') }}
)

select
    batch_id,
    source_row,
    nullif(trim(transaction_id), '')           as transaction_id,
    nullif(trim(account_id), '')               as account_id,
    nullif(trim(counterparty_account_id), '')  as counterparty_account_id,

    case when pg_input_is_valid(amount, 'numeric(18,2)')
         then amount::numeric(18,2) end        as amount,

    upper(trim(currency))                      as currency,
    lower(trim(transaction_type))              as transaction_type,
    upper(trim(country))                       as country,

    case when transaction_timestamp ~ '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'
          and pg_input_is_valid(transaction_timestamp, 'timestamp')
         then transaction_timestamp::timestamp end as transaction_ts,

    -- valeurs brutes conservées pour expliquer les rejets
    amount                as amount_raw,
    transaction_timestamp as transaction_timestamp_raw,
    ingested_at
from source