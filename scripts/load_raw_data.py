"""
Carrega os CSVs de data/ para dentro do DuckDB (olist.duckdb), no schema `raw`.
Isso simula a existencia previa das tabelas de origem que o dbt vai referenciar
como sources (camada Bronze). Rode este script ANTES de `dbt run`.

Uso:
    python3 scripts/load_raw_data.py
"""
import duckdb
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "olist.duckdb")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

FILES = {
    "olist_orders_dataset": "olist_orders_dataset.csv",
    "olist_customers_dataset": "olist_customers_dataset.csv",
    "olist_order_items_dataset": "olist_order_items_dataset.csv",
}

def main():
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw;")
    for table_name, filename in FILES.items():
        csv_path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(csv_path):
            print(f"AVISO: arquivo nao encontrado, pulando: {csv_path}")
            continue
        con.execute(f"""
            CREATE OR REPLACE TABLE raw.{table_name} AS
            SELECT * FROM read_csv_auto('{csv_path}', header=True);
        """)
        count = con.execute(f"SELECT COUNT(*) FROM raw.{table_name}").fetchone()[0]
        print(f"raw.{table_name}: {count} linhas carregadas")
    con.close()

if __name__ == "__main__":
    main()
