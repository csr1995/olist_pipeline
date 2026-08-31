-- Camada Ouro (marts)
-- Tabela Fato final, uma linha por pedido entregue (grao = order_id).
-- Une pedidos (ja filtrados por 'delivered' na staging) + clientes + itens.

{{ config(materialized='table') }}

with orders as (

    select * from {{ ref('stg_orders_delivered') }}

),

customers as (

    select * from {{ ref('stg_customers') }}

),

order_items as (

    select
        order_id,
        sum(item_total_value) as order_total_value

    from {{ ref('stg_order_items') }}
    group by order_id

)

select
    o.order_id,
    o.customer_id,
    c.customer_state,
    o.order_purchase_timestamp,
    o.order_delivered_customer_date,
    coalesce(oi.order_total_value, 0) as order_total_value

from orders o
inner join customers c
    on o.customer_id = c.customer_id
left join order_items oi
    on o.order_id = oi.order_id
