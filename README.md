# olist_pipeline

Pipeline dbt Core + DuckDB (dataset [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)).

📄 **Documentação completa**: [`docs/GUIA_DBT.md`](docs/GUIA_DBT.md) — explica o
que é o dbt, cada camada do projeto e cada decisão tomada.
📄 **Cola para entrevista**: [`docs/ROTEIRO_ENTREVISTA.md`](docs/ROTEIRO_ENTREVISTA.md)
— perguntas prováveis sobre dbt com respostas prontas, usando este projeto de exemplo.

## Arquitetura (medallion)

```
data/*.csv  →  raw.*  (Bronze, sources)  →  staging (Prata, views)  →  marts (Ouro, tables)
```

| Camada | Local | O que faz |
|---|---|---|
| Bronze | `raw.olist_orders_dataset`, `raw.olist_customers_dataset`, `raw.olist_order_items_dataset` | Tabelas cruas, carregadas dos CSVs via `scripts/load_raw_data.py`. Referenciadas em `models/staging/_sources.yml`. |
| Prata | `models/staging/stg_orders_delivered.sql`, `stg_customers.sql`, `stg_order_items.sql` | Views. Regra de negócio: só pedidos com `order_status = 'delivered'`. |
| Ouro | `models/marts/fct_pedidos.sql`, `fct_faturamento_por_estado.sql` | Tables. Fato de pedidos (grão `order_id`) e faturamento agregado por `customer_state`. |

## Sobre os dados

O pipeline já está rodando com o **dataset real do Kaggle** (99.441 pedidos, carregado a
partir do `archive.zip` oficial). Os arquivos usados estão em `data/`:

- `olist_orders_dataset.csv`
- `olist_customers_dataset.csv`
- `olist_order_items_dataset.csv`

Os demais CSVs do dataset (geolocation, payments, reviews, products, sellers,
category translation) não são usados nos modelos atuais, mas se você quiser
expandir o pipeline (ex.: analisar forma de pagamento, categoria de produto,
tempo de entrega vs. estimado, notas de review) é só declarar novas sources
apontando para eles e criar os `stg_*` correspondentes.

Caso queira voltar a rodar com uma amostra sintética (por exemplo, para testar
mudanças de modelo sem mexer no dado real), `scripts/generate_sample_data.py`
continua disponível e sobrescreve os CSVs em `data/` com dados fake no mesmo
formato — só rode `python3 scripts/load_raw_data.py` depois para recarregar o
DuckDB.

## Como rodar

### Linux/Mac (com venv)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install dbt-core dbt-duckdb duckdb

python3 scripts/load_raw_data.py
export DBT_PROFILES_DIR=.
dbt debug
dbt run
dbt test
dbt docs generate && dbt docs serve
```

### Windows (PowerShell, sem venv)

Se o Python do Windows estiver instalado via Microsoft Store, o `pip install`
sem alvo definido pode estourar o limite de caminho longo do Windows (o pacote
`metricflow`, dependência do dbt, tem subpastas com nomes grandes). Contorne
instalando num destino curto:

```powershell
python -m pip install dbt-core dbt-duckdb duckdb --target C:\pylibs
$env:PYTHONPATH = "C:\pylibs"
```

Como isso não cria o executável `dbt.exe`, use um script-ponte (o dbt-core não
expõe `python -m dbt` diretamente):

```powershell
Set-Content -Path run_dbt.py -Value "from dbt.cli.main import cli`nimport sys`nsys.exit(cli())"
```

> Importante: não nomeie esse arquivo `dbt_*.py` — o dbt tem um auto-loader de
> plugins que escaneia módulos com esse prefixo e vai tentar se auto-importar,
> gerando um traceback confuso no final de cada comando (inofensivo, mas feio).

A partir daí, troque `dbt` por `python run_dbt.py` em todo comando:

```powershell
python scripts\load_raw_data.py
$env:DBT_PROFILES_DIR = "."
python run_dbt.py debug
python run_dbt.py run
python run_dbt.py test
python run_dbt.py docs generate
python run_dbt.py docs serve
```

`$env:PYTHONPATH` e `$env:DBT_PROFILES_DIR` só valem para a sessão atual do
PowerShell — repita os dois toda vez que abrir um terminal novo.

`dbt init <nome>` foi usado só para criar o esqueleto inicial do projeto; não precisa
rodar de novo.

## Testes de qualidade implementados

Em `models/marts/_marts.yml`:

- `fct_pedidos.order_id`: `not_null` + `unique` (garante que a tabela Fato final não
  tem `order_id` nulo nem duplicado)
- `fct_pedidos.customer_id` / `customer_state`: `not_null`
- `fct_faturamento_por_estado.customer_state`: `not_null` + `unique`

## Perguntas de negócio respondidas (com o dataset real)

- **Faturamento por estado**: `select * from main_marts.fct_faturamento_por_estado`
  → SP lidera com R$ 5,77 milhões (40.501 pedidos entregues), seguido por RJ
  (R$ 2,05 milhões) e MG (R$ 1,82 milhão).
- **Faturamento total da base**: R$ 15.419.773,75 em 96.478 pedidos entregues.
- **Número de pedidos entregues por estado**: coluna `total_pedidos_entregues`.
- **Ticket médio por estado**: coluna `ticket_medio` — varia de ~R$ 142 (SP, o
  estado com mais volume) a mais de R$ 260 em estados do Norte/Nordeste com
  menos pedidos e frete mais caro (ex.: PB, AP, AC).

## Próximos passos sugeridos (fora do escopo mínimo do desafio)

- Adicionar `dbt seeds` ou `dbt source freshness` se a fonte virar uma tabela viva
- Adicionar teste `relationships` entre `fct_pedidos.customer_id` e `stg_customers.customer_id`
- Expandir os marts usando os outros CSVs do dataset (payments, reviews, products) para
  responder perguntas como forma de pagamento predominante, categoria mais vendida ou
  correlação entre atraso na entrega e nota de review
- Subir o projeto pro GitHub como repositório público com evidências (prints do `dbt docs`,
  do lineage graph e dos resultados das queries), como pedido no desafio
