# Contexto do Projeto — Football DataOps Lakehouse

> Documento de continuidade: registra decisões de arquitetura, estado atual e próximos passos para retomada do trabalho.

---

## O que é o projeto

Data Lakehouse local 100% open source que simula uma arquitetura AWS corporativa para análise tática de futebol. Usa dados do [StatsBomb Open Data](https://github.com/statsbomb/open-data) (JSONs no GitHub). O foco é **DataOps, Engenharia de Dados e IaC** — não Data Science.

---

## Stack

| Camada | Ferramenta | Equivalente AWS |
|--------|-----------|-----------------|
| Armazenamento | MinIO | S3 |
| Processamento | DuckDB | Athena |
| Orquestração | Dagster 1.7+ | MWAA |
| Qualidade | Great Expectations 1.x | Deequ |
| IaC | Terraform (provider `aminueza/minio ~> 2.0`) | CloudFormation |
| CI/CD | GitHub Actions | CodePipeline |

---

## Estrutura de arquivos

```
football-dataops-lakehouse/
├── docker-compose.yml          ← 4 serviços: postgres, minio, dagster-webserver, dagster-daemon
├── workspace.yaml              ← aponta para pipeline.definitions
├── dagster_home/dagster.yaml   ← backend PostgreSQL via EnvVar
├── .env.example
│
├── infra/                      ← Terraform
│   ├── main.tf                 ← buckets raw-data + trusted-data + IAM user "pipeline"
│   ├── variables.tf
│   └── outputs.tf
│
├── pipeline/
│   ├── Dockerfile              ← python:3.11-slim, instala setup.py
│   ├── setup.py                ← pacote instalável "pipeline"
│   └── pipeline/
│       ├── resources.py        ← MinIOResource(ConfigurableResource) usando minio-py
│       ├── definitions.py      ← Definitions com dg.EnvVar("MINIO_*") + DuckDBResource(":memory:")
│       ├── jobs.py             ← lakehouse_full_pipeline + ingestion_only
│       └── assets/
│           ├── ingestion.py    ← competitions_raw → matches_raw → events_raw (idempotente)
│           ├── validation.py   ← events_validated (GX 1.x ephemeral context)
│           └── transformation.py ← events_trusted + matches_trusted (DuckDB httpfs)
│
├── analytics/queries.sql       ← queries prontas: xG, heatmap, pressing, pass network
├── tests/test_assets.py        ← testes unitários sem dependências externas
├── docs/contexto.md            ← este arquivo
└── .github/workflows/ci.yml    ← ruff lint + defs.validate_loadable() + pytest
```

---

## Fluxo de dados (Medallion)

```
StatsBomb GitHub JSON
  → [Dagster: ingestion] → MinIO raw-data/statsbomb/{competitions,matches,events}/
  → [Dagster: validation] → Great Expectations (non-null, coordenadas em bounds)
  → [Dagster: transformation] → MinIO trusted-data/statsbomb/{events,matches}/*.parquet
  → [DuckDB CLI] → analytics/queries.sql
```

**Escopo padrão:** La Liga 2020/21 — `TARGET_COMPETITION_ID = 11`, `TARGET_SEASON_ID = 90`
(constantes em `pipeline/pipeline/assets/ingestion.py`)

---

## Decisões técnicas críticas

### 1. `SET s3_url_style='path'` no DuckDB
MinIO não suporta virtual-hosted style (padrão AWS). Sem esse SET, todas as queries S3 via DuckDB httpfs falham com 403. Definido em `_configure_s3()` dentro de `transformation.py`.

### 2. `SET s3_use_ssl=false`
O docker-compose roda sem TLS. Omitir causa erro de handshake SSL.

### 3. `mostly=0.99` nas GX expectations de coordenadas
~5% dos eventos StatsBomb (Starting XI, substituições, referee ball-drop) não têm campo `location` por design. Usar `mostly=1.0` sempre reprovaria a validação. Definido em `validation.py`.

### 4. `DuckDBResource(database=":memory:")`
Cada run de asset é stateless; a persistência fica nos Parquets no MinIO. Um banco em disco causaria conflito de lock em runs paralelas.

### 5. `minio.ensure_bucket()` nos assets de escrita
Garante que o bucket existe antes de escrever, mesmo que o `terraform apply` não tenha sido rodado.

### 6. Ingestão idempotente em `events_raw`
O asset verifica `minio.object_exists()` antes de baixar cada arquivo de eventos. Re-runs não desperdiçam bandwidth nem sobrescrevem dados existentes.

### 7. Terraform aponta para `localhost:9000`
Terraform é executado fora do Docker. Dentro dos containers, o hostname do MinIO é `minio:9000`. Por isso `MINIO_ENDPOINT=minio:9000` no docker-compose, mas `minio_server = "localhost:9000"` no `variables.tf`.

### 8. `dagster_home/dagster.yaml` dentro do repo
Bind-mounted no container via `/opt/dagster/app`. Evita o problema de o named Docker volume estar vazio no primeiro boot, o que impediria o Dagster de achar o arquivo de configuração de backend.

---

## Como rodar (sequência exata)

```bash
# 1. Variáveis de ambiente
cp .env.example .env

# 2. Subir todos os serviços
docker-compose up -d
# aguardar healthchecks (~20s) — verificar com: docker-compose ps

# 3. Provisionar buckets e IAM no MinIO via Terraform
cd infra/
terraform init
terraform apply
cd ..

# 4. Acessar o Dagster UI e materializar os assets
# http://localhost:3000
# Assets → selecionar todos → Materialize selected
# OU: Jobs → lakehouse_full_pipeline → Launch run
```

**Desenvolvimento local sem Docker:**
```bash
pip install -e pipeline/
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin
dagster dev -f pipeline/pipeline/definitions.py
```

**Queries analíticas (após pipeline rodar):**
```bash
duckdb
# colar o bloco de SET statements de analytics/queries.sql e executar as queries
```

---

## Estado atual

**Criado em:** 2026-03-13
**Status:** Todos os arquivos implementados. **Ainda não foi executado/testado.**

### Próxima sessão deve:
1. Subir os serviços com `docker-compose up -d` e verificar healthchecks
2. Rodar `terraform apply` para criar os buckets
3. Materializar os assets no Dagster UI e validar o fluxo end-to-end
4. Testar as queries em `analytics/queries.sql` com DuckDB CLI
5. Ajustar API do GX 1.x se necessário — os imports de `ValidationDefinition` e `Checkpoint` em `validation.py` podem precisar de ajuste dependendo da versão exata instalada (`great-expectations>=1.0,<2.0`)

---

## Roadmap

- [ ] Dashboard de consumo (Evidence.dev ou Metabase)
- [ ] Asset checks nativos do Dagster (complementar GX)
- [ ] Sensor de ingestão incremental por temporada
- [ ] Cobertura de mais competições StatsBomb (Champions League, WSL, etc.)
- [ ] Modelo de xG simples com scikit-learn integrado ao pipeline
