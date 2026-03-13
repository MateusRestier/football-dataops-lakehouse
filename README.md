# Football DataOps Lakehouse

> **Arquitetura de Data Lakehouse Local — Pipeline Tático Esportivo e DataOps**

Uma infraestrutura de dados ponta a ponta (E2E), orientada a eventos, com foco rigoroso em **Engenharia de Dados**, **DataOps**, **Governança** e **Infraestrutura como Código (IaC)**.

---

## Visão Geral

Diferente de projetos tradicionais de Ciência de Dados focados apenas em modelagem, este ecossistema prioriza:

- **Resiliência do pipeline** — falhas isoladas não contaminam o Data Lake
- **Imutabilidade da infraestrutura** — provisionada via código, reproduzível em qualquer ambiente
- **Qualidade garantida** — dados são validados antes de serem promovidos entre camadas

O domínio escolhido é a **análise espacial e tática de partidas de futebol** (modelagem de Expected Goals — xG, análise de campanhas de clubes), fornecendo um volume rico de dados complexos (coordenadas x,y, arrays de eventos) sem depender de web scraping instável.

Todo o ambiente simula uma **arquitetura corporativa AWS**, executado de forma **100% local e gratuita** via Docker — demonstrando proficiência em otimização de custos e design de sistemas.

---

## Fonte de Dados

| Atributo  | Detalhe |
|-----------|---------|
| **Provedor** | [StatsBomb Open Data](https://github.com/statsbomb/open-data) |
| **Formato** | Arquivos JSON estáticos |
| **Escopo padrão** | La Liga 2020/21 (~380 partidas, ~1M eventos) |
| **Conteúdo** | Telemetria granular por evento: coordenadas espaciais, pressão do adversário, parte do corpo usada, desfecho da jogada |

---

## Stack Tecnológica

| Camada | Ferramenta | Equivalente AWS |
|--------|-----------|-----------------|
| **Armazenamento (Data Lake)** | [MinIO](https://min.io/) | S3 |
| **Processamento / Consultas** | [DuckDB](https://duckdb.org/) | Athena |
| **Orquestração** | [Dagster](https://dagster.io/) | MWAA / Step Functions |
| **Qualidade de Dados** | [Great Expectations](https://greatexpectations.io/) | Deequ / Glue Data Quality |
| **IaC** | [Terraform](https://www.terraform.io/) | CloudFormation |
| **CI/CD** | [GitHub Actions](https://github.com/features/actions) | CodePipeline |

---

## Arquitetura do Pipeline (Medallion)

```
┌─────────────────────────────────────────────────────────────────┐
│               StatsBomb Open Data (GitHub JSON)                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                    1. Provisionamento (Terraform)
                    Cria buckets MinIO + políticas IAM
                               │
                    2. Extração (Dagster Assets — grupo: ingestion)
                    competitions_raw → matches_raw → events_raw
                    Lê JSONs → despeja no bucket raw-data
                               │
                    3. Validação (Great Expectations — grupo: validation)
                    events_validated
                    • event_id não nulo
                    • period não nulo
                    • loc_x ∈ [0, 120]  (mostly=0.99)
                    • loc_y ∈ [0, 80]   (mostly=0.99)
                    ✗ Falhou → pipeline interrompido (dagster.Failure)
                    ✓ Aprovado → próxima etapa
                               │
                    4. Transformação (DuckDB + Dagster — grupo: transformation)
                    events_trusted + matches_trusted
                    JSON → Parquet/ZSTD (colunar)
                    Salva no bucket trusted-data via httpfs
                               │
                    5. Consumo Analítico
                    DuckDB consulta trusted-data
                    analytics/queries.sql — xG, heatmaps, pressing, passes
```

---

## Estrutura do Repositório

```
football-dataops-lakehouse/
├── docker-compose.yml          # MinIO, PostgreSQL, Dagster webserver + daemon
├── workspace.yaml              # Ponto de entrada do Dagster
├── dagster_home/
│   └── dagster.yaml            # Backend PostgreSQL para metadados do Dagster
│
├── infra/                      # Terraform (IaC)
│   ├── main.tf                 # Buckets + IAM MinIO
│   ├── variables.tf
│   └── outputs.tf
│
├── pipeline/                   # Pacote Python instalável
│   ├── Dockerfile
│   ├── setup.py
│   └── pipeline/
│       ├── definitions.py      # Dagster Definitions (entry point)
│       ├── resources.py        # MinIOResource (ConfigurableResource)
│       ├── jobs.py             # Jobs pré-definidos
│       └── assets/
│           ├── ingestion.py    # Camada raw
│           ├── validation.py   # Great Expectations
│           └── transformation.py # Camada trusted (DuckDB → Parquet)
│
├── analytics/
│   └── queries.sql             # Consultas analíticas DuckDB prontas para uso
│
├── tests/
│   └── test_assets.py          # Testes unitários (sem Dagster/MinIO)
│
└── .github/
    └── workflows/
        └── ci.yml              # Lint + smoke test + pytest
```

---

## Como Executar

**Pré-requisitos:** Docker, Docker Compose, Terraform

### 1. Suba a infraestrutura

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/football-dataops-lakehouse.git
cd football-dataops-lakehouse

# Copie as variáveis de ambiente
cp .env.example .env

# Suba todos os serviços (MinIO, PostgreSQL, Dagster webserver + daemon)
docker-compose up -d

# Aguarde os healthchecks (uns 20s)
docker-compose ps
```

### 2. Provisione os buckets via Terraform

```bash
# Com MinIO rodando em localhost:9000
cd infra/
terraform init
terraform apply   # cria raw-data e trusted-data + IAM
```

### 3. Acesse o Dagster UI e materialize os assets

```
http://localhost:3000
```

- Navegue em **Assets** → selecione todos → **Materialize selected**
- Ou execute o job `lakehouse_full_pipeline` em **Jobs**

### 4. Consultas analíticas

```bash
# Instale o DuckDB CLI
pip install duckdb

# Abra um shell DuckDB e execute as queries
duckdb < analytics/queries.sql
```

---

## Desenvolvimento Local (sem Docker)

```bash
pip install -e pipeline/

# Variáveis necessárias
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin

# UI de desenvolvimento (recarregamento automático)
dagster dev -f pipeline/pipeline/definitions.py
```

---

## CI/CD

A cada push, o GitHub Actions executa automaticamente:

- **Linting** (`ruff`) do código Python
- **Smoke test** das Definitions do Dagster (`defs.validate_loadable()`)
- **Testes unitários** (`pytest`) sem dependências externas

---

## Decisões de Design

| Decisão | Motivação |
|---------|-----------|
| `DuckDBResource(database=":memory:")` | Cada run é stateless; a persistência vive nos Parquets no MinIO — evita lock de arquivo em runs paralelas |
| `SET s3_url_style='path'` no DuckDB | MinIO não suporta virtual-hosted style; sem isso todas as queries S3 falham com 403 |
| `mostly=0.99` nas expectations de coordenadas | ~5% dos eventos StatsBomb (Starting XI, substituições) não têm localização por definição — evita falsos positivos na validação |
| Terraform apontando para `localhost:9000` | Executado fora do Docker; dentro dos containers o hostname é `minio:9000` |
| Ingestão idempotente em `events_raw` | Checa se o objeto já existe no MinIO antes de fazer o download — re-runs não desperdiçam bandwidth |

---

## Roadmap

- [x] Provisionamento Terraform do MinIO
- [x] Pipeline Dagster raw → trusted
- [x] Suítes de validação Great Expectations
- [x] Transformações analíticas (xG, heatmaps, pressing)
- [ ] Dashboard de consumo (Evidence / Metabase)
- [ ] Asset checks nativos do Dagster (além do GX)
- [ ] Ingestão incremental por temporada via sensor
