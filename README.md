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
| **Conteúdo** | Telemetria granular por evento: coordenadas espaciais, pressão do adversário, parte do corpo usada, desfecho da jogada |

---

## Stack Tecnológica

A arquitetura substitui serviços gerenciados em nuvem por equivalentes Open Source de alto desempenho:

| Camada | Ferramenta | Equivalente AWS |
|--------|-----------|-----------------|
| **Armazenamento (Data Lake)** | [MinIO](https://min.io/) | S3 |
| **Processamento / Consultas** | [DuckDB](https://duckdb.org/) | Athena |
| **Orquestração** | [Dagster](https://dagster.io/) | MWAA / Step Functions |
| **Qualidade de Dados** | [Great Expectations](https://greatexpectations.io/) | Deequ / Glue Data Quality |
| **IaC** | [Terraform](https://www.terraform.io/) | CloudFormation |
| **CI/CD** | [GitHub Actions](https://github.com/features/actions) | CodePipeline |

> **Nota de design:** Ferramentas de catálogo (ex: DataHub) foram intencionalmente excluídas desta iteração para manter a arquitetura enxuta e concentrar recursos nas camadas de ingestão, validação e transformação.

---

## Arquitetura do Pipeline (Medallion)

```
┌─────────────────────────────────────────────────────────────────┐
│                        StatsBomb JSON                           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                    1. Provisionamento (Terraform)
                    Cria buckets MinIO + políticas IAM
                               │
                    2. Extração (Dagster Asset)
                    Lê JSONs → despeja no bucket raw-data
                               │
                    3. Validação (Great Expectations)
                    Ex: coordenadas (x,y) não nulas,
                    dentro dos limites do campo (120×80)
                    ✗ Falhou → pipeline interrompido
                    ✓ Aprovado → próxima etapa
                               │
                    4. Transformação (DuckDB + Dagster)
                    JSON → Parquet (colunar)
                    Salva no bucket trusted-data
                               │
                    5. Consumo Analítico
                    DuckDB consulta o bucket trusted
                    SQL complexo / mapas de calor / modelos ML
```

---

## Como Executar

**Pré-requisitos:** Docker, Docker Compose, Terraform

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/football-dataops-lakehouse.git
cd football-dataops-lakehouse

# 2. Suba a infraestrutura (MinIO, Dagster, DuckDB)
docker-compose up -d

# 3. Provisione os buckets e políticas via Terraform
cd infra/
terraform init && terraform apply

# 4. Acesse o Dagster UI e materialize os assets
# http://localhost:3000
```

---

## CI/CD

A cada push, o GitHub Actions executa automaticamente:

- Linting do código Python (`ruff` / `flake8`)
- Testes estruturais dos assets Dagster
- Validação das suítes do Great Expectations

---

## Roadmap

- [ ] Ingestão inicial dos dados StatsBomb
- [ ] Provisionamento Terraform do MinIO
- [ ] Pipeline Dagster (raw → trusted)
- [ ] Suítes de validação Great Expectations
- [ ] Transformações analíticas (xG, mapas de calor)
- [ ] Dashboard de consumo (Metabase / Evidence)
