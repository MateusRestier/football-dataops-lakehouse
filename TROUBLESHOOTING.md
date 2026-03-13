# Troubleshooting

Problemas conhecidos, causas e soluções. Atualizado a cada bug encontrado e corrigido.

---

## Dagster

### Dagster UI não abre em `localhost:3000`

**Sintoma:** Página não carrega ou retorna erro de conexão.

**Causas e soluções:**

1. **Serviços ainda subindo** — aguarde ~20s após `docker-compose up -d` e verifique:
   ```bash
   docker-compose ps
   # todos devem estar "healthy", não "starting"
   ```

2. **PostgreSQL não ficou healthy** — o webserver depende do postgres. Verifique:
   ```bash
   docker-compose logs postgres
   ```

3. **`workspace.yaml` não encontrado** — o bind-mount do repositório inteiro precisa estar correto. Verifique se você rodou `docker-compose up` a partir da raiz do repositório (onde está o `docker-compose.yml`).

---

### Dagster não encontra as Definitions / location falha ao carregar

**Sintoma:** UI abre mas mostra erro na location `football_pipeline`.

**Causa mais comum:** Erro de importação no código Python.

**Diagnóstico:**
```bash
docker-compose logs dagster-webserver | grep -i error
```

Ou teste fora do Docker:
```bash
pip install -e pipeline/
python -c "from pipeline.definitions import defs; defs.validate_loadable()"
```

O erro Python aparecerá diretamente no terminal.

---

### Schedule não dispara automaticamente

**Sintoma:** Schedule configurado mas runs não são criados.

**Causa:** `dagster-daemon` não está rodando ou não consegue conectar ao PostgreSQL.

```bash
docker-compose logs dagster-daemon
docker-compose ps dagster-daemon   # deve estar "Up"
```

Se o daemon reiniciou várias vezes, verifique a conexão com o postgres.

---

## MinIO

### Buckets não existem após `docker-compose up`

**Sintoma:** Assets falham com erro de bucket não encontrado.

**Causa:** O Terraform precisa ser rodado **após** o MinIO subir, e **antes** de materializar os assets.

```bash
cd infra/
terraform init
terraform apply
```

Confirme que os buckets foram criados acessando o console MinIO: `http://localhost:9001` (usuário: `minioadmin`, senha: `minioadmin`).

**Alternativa sem Terraform:** O `MinIOResource` tem o método `ensure_bucket()` chamado no início dos assets de escrita — se preferir, pode deixar o pipeline criar os buckets automaticamente e não usar o Terraform na primeira execução.

---

### Erro de conexão ao MinIO dentro do Docker (`minio:9000`)

**Sintoma:** Assets falham com `Connection refused` ou `Failed to establish connection`.

**Causa:** O hostname `minio:9000` só funciona **dentro da rede Docker**. Fora do Docker (desenvolvimento local), use `localhost:9000`.

```bash
# desenvolvimento local
export MINIO_ENDPOINT=localhost:9000

# dentro do docker-compose, já está configurado como minio:9000
```

---

## DuckDB / Transformação

### `Unknown extension: httpfs`

**Sintoma:** Asset `events_trusted` ou `matches_trusted` falha com este erro.

**Causa:** A versão do DuckDB instalada não inclui a extensão `httpfs` por padrão, ou a extensão não pôde ser baixada (sem acesso à internet no container).

**Solução 1 — forçar instalação com extensão:**
Em `pipeline/setup.py`, trocar:
```
duckdb>=0.10
```
por:
```
duckdb[httpfs]>=0.10
```
Depois reconstruir o container: `docker-compose build --no-cache dagster-webserver dagster-daemon`.

**Solução 2 — pre-instalar no Dockerfile:**
```dockerfile
RUN pip install --no-cache-dir -e . && \
    python -c "import duckdb; conn = duckdb.connect(); conn.execute('INSTALL httpfs')"
```

---

### Erro `403 Forbidden` ao ler/escrever no MinIO via DuckDB

**Sintoma:** Query SQL com `read_parquet('s3://...')` ou `COPY ... TO 's3://...'` retorna 403.

**Causa mais comum:** `s3_url_style` não configurado para `path`. MinIO não suporta o estilo virtual-hosted (padrão da AWS).

**Verificação:**
```sql
-- deve estar assim antes de qualquer query S3
SET s3_url_style='path';
SET s3_use_ssl=false;
```

Esse SET já está em `_configure_s3()` dentro de `transformation.py`. Se estiver rodando queries manuais no DuckDB CLI, não esqueça de executar o bloco completo de configuração do `analytics/queries.sql`.

---

### `read_json_auto` falha com erro de schema

**Sintoma:** `events_trusted` falha com erro de tipo ou schema incompatível ao ler os JSONs.

**Causa:** Eventos StatsBomb têm schemas heterogêneos — cada tipo de evento tem campos extras diferentes. O parâmetro `union_by_name=true` resolve isso.

**Verificação no código** (`transformation.py`):
```sql
FROM read_json_auto('s3://raw-data/statsbomb/events/*.json', union_by_name=true, ...)
```

Se o parâmetro estiver ausente, adicione-o.

---

## Great Expectations

### `AttributeError` ao rodar `events_validated`

**Sintoma:** Stack trace com `AttributeError` em métodos do GX.

**Causa:** A API do Great Expectations mudou entre versões. O projeto usa a API do GX 1.x (`mode="ephemeral"`, `ValidationDefinition.run()`). Versões anteriores (0.18.x) têm API diferente.

**Verificação:**
```bash
pip show great-expectations
# deve ser >= 1.0.0
```

Se a versão for 0.18.x, atualize:
```bash
pip install "great-expectations>=1.0,<2.0"
```

---

### Validação sempre falha nas expectations de coordenadas

**Sintoma:** `events_validated` falha com erro sobre `loc_x` ou `loc_y` fora dos bounds, mesmo com dados corretos.

**Causa:** Eventos administrativos do StatsBomb (Starting XI, substituições, etc.) não têm campo `location` — esses eventos representam ~5% do total e geram `loc_x = null`. Se `mostly` não estiver configurado, a expectation exige 100% de conformidade e sempre falha.

**Verificação no código** (`validation.py`):
```python
gx.expectations.ExpectColumnValuesToBeBetween(
    column="loc_x", min_value=0.0, max_value=120.0, mostly=0.99  # ← deve estar aqui
)
```

---

## GitHub Actions / CI

### CI falha no passo de lint (`ruff`)

**Sintoma:** Workflow falha com erros de estilo de código.

**Solução local antes de commitar:**
```bash
pip install ruff
ruff check pipeline/pipeline/ tests/
ruff check --fix pipeline/pipeline/ tests/   # corrige automaticamente o que for possível
```

---

### CI falha no smoke test das Definitions

**Sintoma:** `python -c "from pipeline.definitions import defs; defs.validate_loadable()"` falha no workflow.

**Causa mais comum:** Erro de importação no código Python — algum módulo não encontrado ou syntax error.

O workflow define variáveis de ambiente mínimas:
```yaml
env:
  MINIO_ENDPOINT: "localhost:9000"
  MINIO_ACCESS_KEY: "minioadmin"
  MINIO_SECRET_KEY: "minioadmin"
```

Se as Definitions tentarem conectar ao MinIO no import time (não deveriam — `ConfigurableResource` conecta só na execução), o CI vai falhar. Verifique se nenhum código de conexão está sendo executado fora de métodos.
