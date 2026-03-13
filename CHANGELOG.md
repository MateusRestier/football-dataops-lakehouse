# Changelog

Todas as mudanças relevantes do projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [Unreleased]

> Itens planejados mas ainda não implementados.

### Planejado
- Dashboard de consumo (Evidence.dev ou Metabase)
- Asset checks nativos do Dagster (complementar GX)
- Sensor de ingestão incremental por temporada
- Cobertura de mais competições StatsBomb (Champions League, WSL, etc.)
- Modelo de xG simples com scikit-learn integrado ao pipeline
- Testes de integração contra MinIO + DuckDB reais

---

## [0.2.0] — 2026-03-13

### Corrigido
- **`validation.py`** — API do Great Expectations 1.x estava incorreta:
  - Trocado `gx.get_context()` por `gx.get_context(mode="ephemeral")` — sem o parâmetro `mode`, o GX tenta localizar um arquivo de configuração no disco e falha
  - Removida a camada de `Checkpoint`, desnecessária para validações simples — substituída por `ValidationDefinition.run()` diretamente
  - Corrigidos imports que apontavam para submódulos inexistentes no GX 1.x (`great_expectations.core.validation_definition`, `great_expectations.checkpoint`)
- **`ingestion.py`** — dependências entre assets declaradas como strings frágeis:
  - `deps=["raw/competitions_raw"]` → `deps=[competitions_raw]` (referência à função Python)
  - `deps=["raw/matches_raw"]` → `deps=[matches_raw]`
- **`validation.py`** — `deps=["raw/events_raw"]` → `deps=[events_raw]`
- **`transformation.py`** — `deps=["validated/events_validated"]` → `deps=[events_validated]` (ambos os assets)

### Motivo das correções de `deps`
Referências por string (`"raw/competitions_raw"`) funcionam em tempo de execução, mas são frágeis: se o asset for renomeado, o Python não detecta o erro — o grafo de dependências quebra silenciosamente. Com referências à função, o Python levanta `NameError` imediatamente.

---

## [0.1.0] — 2026-03-13

### Adicionado
- **Infraestrutura Docker** (`docker-compose.yml`): 4 serviços orquestrados — PostgreSQL (backend Dagster), MinIO (Data Lake), dagster-webserver (UI), dagster-daemon (schedules)
- **Configuração Dagster** (`dagster_home/dagster.yaml`): backend PostgreSQL via variáveis de ambiente; `workspace.yaml` aponta para `pipeline.definitions`
- **Terraform** (`infra/`): provisiona buckets `raw-data` e `trusted-data` no MinIO + usuário IAM `pipeline` com política de acesso restrita aos dois buckets. Provider `aminueza/minio ~> 2.0`
- **Pipeline Dagster** (`pipeline/`): pacote Python instalável com 3 grupos de assets:
  - `ingestion` — `competitions_raw → matches_raw → events_raw`: busca JSONs do StatsBomb Open Data (GitHub) e armazena no MinIO raw-data. Ingestão idempotente (não re-baixa arquivos já existentes)
  - `validation` — `events_validated`: valida amostra de 5 partidas com Great Expectations (non-null em `event_id`/`period`, coordenadas dentro dos limites do campo 120×80)
  - `transformation` — `events_trusted` + `matches_trusted`: transforma JSON → Parquet/ZSTD via DuckDB httpfs, escrevendo diretamente no MinIO trusted-data
- **`MinIOResource`** (`resources.py`): `ConfigurableResource` do Dagster que encapsula o cliente `minio-py`
- **Jobs** (`jobs.py`): `lakehouse_full_pipeline` (pipeline completo) e `ingestion_only`
- **Schedule**: `weekly_ingest` — toda segunda-feira às 06:00 UTC
- **Queries analíticas** (`analytics/queries.sql`): xG por time, mapa de chutes, heatmap de passes, pressão alta, distribuição de eventos — todas via DuckDB httpfs contra MinIO trusted-data
- **Testes unitários** (`tests/test_assets.py`): 5 testes para `_flatten_events()` + smoke test de `defs.validate_loadable()`
- **CI/CD** (`.github/workflows/ci.yml`): ruff lint + smoke test das Definitions + pytest, em push/PR para `main`
- **Documentação** (`docs/contexto.md`): guia de continuidade com stack, decisões técnicas, sequência de execução e roadmap
