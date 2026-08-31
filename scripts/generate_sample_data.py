"""
Gera uma AMOSTRA sintetica no formato do Brazilian E-Commerce Public Dataset (Olist)
para permitir rodar o pipeline dbt de ponta a ponta sem depender de download do Kaggle.

IMPORTANTE: isso NAO e o dataset real. Para o desafio valendo, baixe o dataset completo em
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce e substitua os arquivos em data/
mantendo os mesmos nomes de coluna.
"""
import csv
import random
from datetime import datetime, timedelta

random.seed(42)

STATES = ["SP", "RJ", "MG", "RS", "PR", "BA", "SC", "PE"]
CITIES = {
    "SP": "sao paulo", "RJ": "rio de janeiro", "MG": "belo horizonte",
    "RS": "porto alegre", "PR": "curitiba", "BA": "salvador",
    "SC": "florianopolis", "PE": "recife",
}
STATUSES = ["delivered", "delivered", "delivered", "delivered", "shipped", "canceled", "processing", "invoiced"]

N_CUSTOMERS = 40
N_ORDERS = 80

# ---- customers ----
customers = []
for i in range(1, N_CUSTOMERS + 1):
    state = random.choice(STATES)
    customers.append({
        "customer_id": f"cust_{i:04d}",
        "customer_unique_id": f"uniq_{i:04d}",
        "customer_zip_code_prefix": random.randint(10000, 99000),
        "customer_city": CITIES[state],
        "customer_state": state,
    })

with open("data/olist_customers_dataset.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(customers[0].keys()))
    w.writeheader()
    w.writerows(customers)

# ---- orders ----
base_date = datetime(2018, 1, 1)
orders = []
order_ids = []
for i in range(1, N_ORDERS + 1):
    order_id = f"order_{i:05d}"
    order_ids.append(order_id)
    customer = random.choice(customers)
    status = random.choice(STATUSES)
    purchase = base_date + timedelta(days=random.randint(0, 300), hours=random.randint(0, 23))
    approved = purchase + timedelta(hours=random.randint(1, 48))
    delivered_customer = ""
    delivered_carrier = ""
    if status == "delivered":
        delivered_carrier = (purchase + timedelta(days=random.randint(1, 3))).isoformat(sep=" ")
        delivered_customer = (purchase + timedelta(days=random.randint(4, 15))).isoformat(sep=" ")
    estimated = purchase + timedelta(days=random.randint(10, 25))
    orders.append({
        "order_id": order_id,
        "customer_id": customer["customer_id"],
        "order_status": status,
        "order_purchase_timestamp": purchase.isoformat(sep=" "),
        "order_approved_at": approved.isoformat(sep=" "),
        "order_delivered_carrier_date": delivered_carrier,
        "order_delivered_customer_date": delivered_customer,
        "order_estimated_delivery_date": estimated.isoformat(sep=" "),
    })

# injeta 1 order_id duplicado propositalmente para o teste de qualidade eventualmente pegar
# regressao (comentado por padrao - deixe comentado para o pipeline passar limpo)
# orders.append(dict(orders[0]))

with open("data/olist_orders_dataset.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(orders[0].keys()))
    w.writeheader()
    w.writerows(orders)

# ---- order_items ----
items = []
for order_id in order_ids:
    n_items = random.randint(1, 3)
    for item_seq in range(1, n_items + 1):
        items.append({
            "order_id": order_id,
            "order_item_id": item_seq,
            "product_id": f"prod_{random.randint(1, 200):04d}",
            "seller_id": f"seller_{random.randint(1, 30):03d}",
            "price": round(random.uniform(19.9, 899.9), 2),
            "freight_value": round(random.uniform(7.5, 45.0), 2),
        })

with open("data/olist_order_items_dataset.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(items[0].keys()))
    w.writeheader()
    w.writerows(items)

print(f"OK: {len(customers)} customers, {len(orders)} orders, {len(items)} order_items")
