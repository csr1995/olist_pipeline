# Guia do projeto — dbt Core + DuckDB (dataset Olist)

Este documento explica o que é o dbt, como este projeto está organizado e por que
cada decisão foi tomada. Serve tanto como documentação técnica quanto como material
de estudo (primeira vez usando dbt).

## 1. O que o dbt faz (e o que ele não faz)

dbt (**d**ata **b**uild **t**ool) é uma ferramenta de **transformação**. Ela não
extrai dado de sistemas de origem e não carrega dado em um banco — isso é feito por
outra camada (no nosso caso, um script Python simples: `scripts/load_raw_data.py`,
usando a lib `duckdb`, sem nada de dbt envolvido). O dbt entra depois: quando os
dados já estão dentro de um banco/warehouse, ele organiza e versiona as
transformações que viram esse dado cru em tabelas prontas para análise.

Na prática, o dbt é uma camada em cima de arquivos `.sql`. Cada arquivo é um
`SELECT`. O dbt:

1. Lê todos os `.sql` do projeto e identifica as dependências entre eles;
2. Monta um grafo de execução (DAG — *Directed Acyclic Graph*);
3. Executa cada `SELECT`, na ordem certa, e materializa o resultado como
   **view** ou **table**;
4. Roda testes de qualidade sobre esse resultado;
5. Gera documentação e o gráfico de dependências automaticamente.

## 2. Arquitetura do projeto (medallion: bronze / prata / ouro)

```
data/*.csv  →  raw.*  (Bronze)  →  staging (Prata, views)  →  marts (Ouro, tables)
```

### Bronze — `raw.*` (fora do dbt, carregado por `scripts/load_raw_data.py`)

Tabelas cruas, exatamente como vieram dos CSVs do Kaggle, sem nenhum tratamento.
O dbt não cria essas tabelas — ele apenas as **declara** como fontes de dado
(`source`), em `models/staging/_sources.yml`:

```yaml
sources:
  - name: raw
    database: olist
    schema: raw
    tables:
      - name: olist_orders_dataset
      - name: olist_customers_dataset
      - name: olist_order_items_dataset
```

Declarar como `source` (em vez de referenciar a tabela crua direto no meio de um
`SELECT`) tem duas vantagens: (1) o dbt consegue testar a origem — por exemplo
`dbt source freshness`, para checar se a tabela está desatualizada — e (2) o
gráfico de linhagem (lineage graph) mostra de onde cada dado veio.

### Prata — `models/staging/` (views)

Primeira limpeza/padronização, um modelo por tabela de origem:

| Arquivo | O que faz |
|---|---|
| `stg_orders_delivered.sql` | Filtra `order_status = 'delivered'` — regra de negócio: só pedidos entregues geram faturamento reconhecido. Faz cast de datas. |
| `stg_customers.sql` | Padroniza texto (`trim`, `upper` no estado). |
| `stg_order_items.sql` | Calcula `item_total_value = price + freight_value`. |

Materializados como **view**: não guardam dado fisicamente, recalculam a cada
consulta. Faz sentido porque staging é passo intermediário — ninguém consulta
direto, e não vale a pena gastar espaço/tempo de escrita guardando um resultado
que só serve de insumo pro próximo passo.

### Ouro — `models/marts/` (tables)

| Arquivo | O que faz |
|---|---|
| `fct_pedidos.sql` | Tabela fato. Grão = 1 linha por pedido entregue. Junta as 3 staging views. |
| `fct_faturamento_por_estado.sql` | Agrega `fct_pedidos` por `customer_state`: faturamento total, número de pedidos, ticket médio. |

Materializados como **table**: o resultado é gravado fisicamente. Mais lento de
criar (recalcula tudo a cada `dbt run`), muito mais rápido de consultar — e é
exatamente o que um dashboard ou analista vai bater com frequência.

## 3. `ref()` e `source()` — por que o dbt existe

Nenhum modelo escreve o nome físico de outra tabela. Em vez de
`select * from stg_customers`, o `fct_pedidos.sql` escreve:

```sql
select * from {{ ref('stg_customers') }}
```

E a staging, em vez de `select * from raw.olist_customers_dataset`, escreve:

```sql
select * from {{ source('raw', 'olist_customers_dataset') }}
```

`ref()` e `source()` são o motivo de existir o dbt. Ao usá-los, o autor do modelo
não está apontando pro nome físico da tabela — está declarando uma dependência.
O dbt lê todas essas chamadas no projeto inteiro, monta o DAG e decide sozinho a
ordem de execução. Consequências práticas:

- Se você renomear um modelo, todo `ref()` que apontava pra ele quebra **na hora
  de compilar**, antes de virar um erro em produção.
- O dbt paraleliza automaticamente o que não depende um do outro (por isso
  `stg_customers`, `stg_order_items` e `stg_orders_delivered` rodam ao mesmo
  tempo no `dbt run` — repare no log, threads diferentes).
- O `dbt docs generate` consegue desenhar o gráfico de linhagem sem você
  desenhar nada manualmente.

## 4. Materialização: view vs. table

Configurado em `dbt_project.yml`:

```yaml
models:
  olist_pipeline:
    staging:
      +materialized: view
    marts:
      +materialized: table
```

| | View | Table |
|---|---|---|
| O que o dbt gera | `CREATE VIEW ... AS SELECT ...` | `CREATE TABLE ... AS SELECT ...` |
| Armazena dado fisicamente? | Não | Sim |
| Criação | Rápida | Mais lenta (recalcula tudo) |
| Consulta | Recalcula toda vez (mais lenta) | Lê dado já pronto (mais rápida) |
| Quando usar | Passos intermediários (staging) | Modelos finais consultados com frequência (marts) |

Existem outras estratégias de materialização (`incremental`, para tabelas
grandes que você não quer recalcular do zero a cada rodada; `ephemeral`, que
nem chega a virar objeto no banco, é inlinado como CTE) — não usadas aqui, mas
valem menção numa entrevista.

## 5. Testes de qualidade

Em `models/marts/_marts.yml`:

```yaml
models:
  - name: fct_pedidos
    columns:
      - name: order_id
        tests: [not_null, unique]
      - name: customer_id
        tests: [not_null]
      - name: customer_state
        tests: [not_null]
  - name: fct_faturamento_por_estado
    columns:
      - name: customer_state
        tests: [not_null, unique]
```

`not_null` e `unique` são **testes genéricos** que já vêm prontos no dbt (existem
outros: `accepted_values`, `relationships`). O dbt também suporta **testes
singulares** — um arquivo `.sql` na pasta `tests/` que deve retornar zero linhas
para passar (por exemplo: "nenhum pedido pode ter valor negativo"). Não usamos
nenhum singular aqui, mas é bom saber que existe.

O motivo de ter teste não é burocracia: é o que separa "eu escrevi um SQL" de
"eu tenho um pipeline em que confio". Se um JOIN mal feito duplicar linhas, o
teste `unique` falha no `dbt test` — antes do dado errado virar um número errado
em um dashboard.

## 6. Jinja e macros

Os arquivos `.sql` do dbt não são SQL puro — são SQL com **Jinja**, a mesma
engine de template usada em Flask/Django no Python. `{{ ref(...) }}`,
`{{ source(...) }}` e `{{ config(...) }}` são chamadas de função Jinja que o
dbt "compila" para SQL puro antes de mandar pro banco (dá pra ver o SQL
compilado em `target/compiled/`, depois de um `dbt run`). Isso é o que permite
criar **macros** — funções SQL reutilizáveis — em vez de copiar e colar lógica
em vários modelos. Não criamos nenhuma macro custom neste projeto, mas o dbt já
vem com várias prontas (como as dos testes genéricos).

## 7. Estrutura de arquivos do projeto

```
olist_pipeline/
├── dbt_project.yml       # configuração do projeto (nome, materializações por pasta)
├── profiles.yml          # como conectar no banco (aqui: arquivo DuckDB local)
├── data/                 # CSVs de origem (dataset real da Olist)
├── scripts/
│   ├── generate_sample_data.py  # gera dado sintético (fallback, nao usado agora)
│   └── load_raw_data.py         # carrega os CSVs para dentro do DuckDB (schema raw)
├── models/
│   ├── staging/
│   │   ├── _sources.yml          # declaração das sources (bronze)
│   │   ├── stg_customers.sql
│   │   ├── stg_order_items.sql
│   │   └── stg_orders_delivered.sql
│   └── marts/
│       ├── _marts.yml            # documentação + testes dos marts
│       ├── fct_pedidos.sql
│       └── fct_faturamento_por_estado.sql
├── macros/                # vazio neste projeto (macros customizadas ficariam aqui)
├── seeds/                 # vazio (dbt seed é para CSVs pequenos versionados no git)
├── snapshots/             # vazio (snapshots capturam mudanças de dados ao longo do tempo — SCD tipo 2)
└── tests/                 # vazio (testes singulares customizados ficariam aqui)
```

## 8. Comandos usados neste projeto

| Comando | O que faz |
|---|---|
| `dbt debug` | Testa a conexão com o banco e a configuração do projeto. Não roda nenhum modelo. |
| `dbt run` | Executa os `SELECT`s dos modelos e materializa como view/table, na ordem do DAG. |
| `dbt test` | Roda os testes de qualidade declarados nos `.yml`. |
| `dbt build` | Roda `run` + `test` juntos, respeitando a ordem do DAG (se um teste falhar num modelo, os modelos que dependem dele nem chegam a rodar). Não usado nas conversas anteriores, mas é o comando mais comum no dia a dia. |
| `dbt docs generate` | Gera a documentação estática (HTML) e o `catalog.json`/`manifest.json`. |
| `dbt docs serve` | Sobe um servidor local com a documentação navegável e o lineage graph. |
| `dbt compile` | Só compila o Jinja para SQL puro, sem executar nada no banco. Útil pra debugar o que o `ref()`/`source()` realmente geram. |

## 9. Resultado com o dataset real

Com os 99.441 pedidos do dataset oficial do Kaggle
(<https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>):

- 96.478 pedidos entregues (`fct_pedidos`)
- Faturamento total: R$ 15.419.773,75
- SP concentra a maior fatia: R$ 5,77 milhões (40.501 pedidos)
- 6 de 6 testes de qualidade passando

## 10. Próximos passos possíveis (fora do escopo mínimo)

- Adicionar `dbt source freshness` se a origem virar uma tabela viva (atualizada
  periodicamente) em vez de um CSV estático.
- Adicionar teste `relationships` entre `fct_pedidos.customer_id` e
  `stg_customers.customer_id` (garante integridade referencial).
- Criar uma macro customizada para a lógica de `item_total_value`, se ela
  precisar ser reaproveitada em mais de um modelo.
- Expandir os marts usando os outros CSVs do dataset Olist (payments, reviews,
  products) — forma de pagamento predominante, categoria mais vendida, relação
  entre atraso na entrega e nota de review.
- Trocar a materialização de `fct_pedidos` para `incremental` se o volume de
  pedidos crescer muito e recalcular tudo do zero a cada `dbt run` ficar caro.
