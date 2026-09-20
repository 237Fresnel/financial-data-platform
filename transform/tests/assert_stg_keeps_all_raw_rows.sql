-- échoue si le staging perd ou crée des lignes
select 1
where (select count(*) from {{ source('raw', 'transactions') }})
   <> (select count(*) from {{ ref('stg_transactions') }})