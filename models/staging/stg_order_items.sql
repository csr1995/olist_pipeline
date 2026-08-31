with source as (

    select * from {{ source('raw', 'olist_order_items_dataset') }}

),

renamed as (

    select
        order_id,
        order_item_id,
        product_id,
        seller_id,
        price,
        freight_value,
        price + freight_value as item_total_value

    from source

)

select * from renamed
