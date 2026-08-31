-- Camada Ouro (marts)
-- Agrega o fato de pedidos (fct_pedidos) por customer_state, respondendo
-- diretamente a pergunta de negocio "quanto eu tenho de faturamento, por estado?".

{{ config(materialized='table') }}

select
    customer_state,
    count(distinct order_id)         as total_pedidos_entregues,
    sum(order_total_value)           as faturamento_total,
    round(avg(order_total_value), 2) as ticket_medio

from {{ ref('fct_pedidos') }}
group by customer_state
order by faturamento_total desc
