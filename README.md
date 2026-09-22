# Med Robots API

Backend local para guardar pedidos de contacto da Med Robots. É uma API independente do website `paulositecopy` e **ainda não está em produção**. Nesta fase não envia emails nem altera o frontend.

## Stack e arquitetura

Python 3.14, FastAPI, Pydantic, SQLAlchemy 2, Alembic e PostgreSQL 17. O router valida a entrada e chama o serviço; o serviço chama o repositório; o repositório usa uma sessão SQLAlchemy gerida por pedido. A migração cria a tabela `contacts`. Não há autenticação, painel administrativo ou outros serviços.

```text
app/
  main.py                 aplicação, CORS, erros, logging e lifecycle
  api/router.py           router principal
  api/v1/                 health (liveness/readiness) e contacts
  core/                   configuração, logging e request id
  db/                     engine, sessão e model Contact
  schemas/                contratos de entrada e saída
  services/               lógica do pedido de contacto
  repositories/           persistência
migrations/               migração inicial Alembic
tests/unit/               schemas, configuração e engine
tests/integration/        API, health, persistência, migração e Docker
tests/security/           erros, limites, CORS e request id
```

## Configuração

Copiar `.env.example` para `.env` e adaptar os valores. `.env` está ignorado pelo Git. Nenhuma credencial real deve ser adicionada ao repositório.

| Variável | Uso |
| --- | --- |
| `APP_NAME` | Nome na documentação OpenAPI |
| `APP_VERSION` | Versão da API |
| `ENVIRONMENT` | `development`, `test` ou `production` |
| `DATABASE_URL` | URL SQLAlchemy; PostgreSQL com `psycopg` em produção |
| `CORS_ORIGINS` | Origins HTTP(S) explícitos, separados por vírgulas |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL` |
| `DB_POOL_SIZE` | Tamanho do pool de ligações (PostgreSQL); default `5` |
| `DB_MAX_OVERFLOW` | Ligações extra além do pool; default `10` |
| `DB_POOL_TIMEOUT` | Segundos à espera de uma ligação livre; default `30` |
| `DB_POOL_RECYCLE` | Segundos até reciclar uma ligação; default `1800` |

Os parâmetros de pool são ignorados em SQLite (usado apenas nos testes); aplicam-se apenas a PostgreSQL. Uma configuração inválida (ex.: `ENVIRONMENT=production` sem `DATABASE_URL`/`CORS_ORIGINS`, credenciais de desenvolvimento, origens HTTP ou valores de pool negativos) faz a aplicação falhar imediatamente no arranque, com uma mensagem de erro clara — nunca arranca em produção com defaults inseguros.

O exemplo permite `http://localhost:5173`, `http://127.0.0.1:5173` e `http://127.0.0.1:4173` para desenvolvimento. Ajustar `CORS_ORIGINS` à origem real do frontend antes de qualquer publicação. O valor `*` é rejeitado. O Docker Compose usa credenciais **apenas locais de desenvolvimento**; não as reutilizar fora do ambiente local.

Em `ENVIRONMENT=production`, definir explicitamente `DATABASE_URL` e `CORS_ORIGINS`; as origens têm de usar HTTPS e as credenciais de exemplo são rejeitadas. Os valores de desenvolvimento por defeito não são aceites como configuração implícita de produção. CORS é uma política dos browsers; clientes sem `Origin` continuam a poder chamar o endpoint público. Pedidos com `Origin` não autorizada são rejeitados.

## Execução local

Ver secção "Development" abaixo para o passo a passo local, e "Production" para os requisitos obrigatórios antes de qualquer publicação.

## Execução com Docker

Com o Docker daemon ativo, sem instalar PostgreSQL no Mac:

```bash
docker compose up --build -d
curl http://127.0.0.1:8000/api/v1/health
docker compose logs -f api
docker compose down
```

O Compose tem três serviços: `db` (PostgreSQL local), `migrate` (aplica `alembic upgrade head` uma vez e termina) e `api` (arranca só depois de `migrate` terminar com sucesso, sem migrações embutidas no comando). A API fica acessível apenas em `127.0.0.1:8000` no host. O volume `postgres_data` conserva os dados entre reinícios. Para apagar os dados locais de desenvolvimento, usar `docker compose down -v` conscientemente.

Se a porta 8000 já estiver ocupada, executar `API_PORT=8001 docker compose up --build -d` e aceder à API em `127.0.0.1:8001`.

O `Dockerfile` usa build multi-stage (dependências instaladas numa stage `builder`, imagem final sem ferramentas de build), corre como utilizador não-root, não usa `--reload` e define um `HEALTHCHECK` que chama `/api/v1/health`.

## Endpoints e documentação

- `GET /api/v1/health` → `200 {"status":"ok"}` (liveness). Não acede à base de dados; indica apenas que o processo responde. Usado pelo `HEALTHCHECK` do Docker.
- `GET /api/v1/ready` → `200 {"status":"ok","database":"ok"}` (readiness) quando a base de dados responde a `SELECT 1`; `503` com o formato de erro comum quando a base de dados está indisponível.
- `POST /api/v1/contacts` → `201` com `id`, `status` e `created_at`. Aceita `first_name`, `last_name`, `email`, `phone`, `address` e `message`. Nome, apelido, email e mensagem são obrigatórios. `phone` e `address` são opcionais. Campos desconhecidos, valores inválidos e texto vazio são rejeitados.
- `/docs`, `/redoc` e `/openapi.json` mostram o contrato OpenAPI. Ficam acessíveis em development e test; uma futura fase pode decidir restringi-los em produção, o que ainda não foi implementado por falta de uma política concreta (autenticação, rede, etc.).

Todos os pedidos e respostas incluem o cabeçalho `X-Request-ID`: se o cliente enviar um valor válido (`[A-Za-z0-9_-]{1,64}`) este é devolvido tal e qual; caso contrário é gerado um novo UUID. O mesmo identificador aparece nos logs do pedido, o que facilita correlacionar um erro reportado pelo cliente com as linhas de log correspondentes.

Exemplo local:

```bash
curl -i http://127.0.0.1:8000/api/v1/contacts \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"Ana","last_name":"Silva","email":"ana@example.com","message":"Gostaria de saber mais."}'
```

## Testes e verificações

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m compileall -q app migrations
.venv/bin/alembic upgrade head --sql
```

Os testes usam SQLite temporário para serem rápidos e determinísticos, sem serviços externos. A migração é também validada numa base limpa; para confirmar o comportamento específico de PostgreSQL, executar o Docker Compose e fazer um POST real. `alembic upgrade head --sql` gera SQL de PostgreSQL sem se ligar à base.

## Development, Test e Production

### Development

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
# Ajustar DATABASE_URL para o PostgreSQL local
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

`--reload` só deve ser usado em desenvolvimento. `ENVIRONMENT=development` aceita os defaults do `.env.example` (credenciais locais, CORS em HTTP).

### Test

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m compileall -q app migrations
```

A suite usa `ENVIRONMENT=test` com SQLite temporário (ver `tests/conftest.py`); não depende de PostgreSQL nem de rede.

### Production

Com `ENVIRONMENT=production`, a aplicação falha no arranque (não apenas num pedido) se qualquer uma destas condições não for cumprida:

- `DATABASE_URL` tem de ser fornecida explicitamente (não pode usar o default);
- tem de apontar para PostgreSQL com `psycopg` (SQLite é rejeitado);
- as credenciais não podem ser as de desenvolvimento (`medrobots`/`medrobots`);
- `CORS_ORIGINS` tem de ser fornecido explicitamente;
- todas as origens têm de usar HTTPS (`*` e HTTP são rejeitados).

Executar com `uvicorn app.main:app --host 0.0.0.0 --port 8000` (sem `--reload`). Para escalar horizontalmente no futuro, correr várias instâncias/workers atrás de um load balancer; a aplicação já é stateless ao nível da base de dados, mas ver a limitação de rate limiting abaixo antes de o fazer. As migrações (`alembic upgrade head`) devem correr como um passo explícito antes de arrancar novas instâncias da aplicação (ver `docker-compose.yml`, serviço `migrate`), nunca embutidas no comando de arranque de cada réplica — evita condições de corrida quando há múltiplas instâncias a arrancar em simultâneo.

### Current limitations

Esta fase (Production Readiness) prepara a aplicação, mas as seguintes áreas pertencem a fases seguintes e **não** foram implementadas:

- infraestrutura AWS (ECS/Fargate, VPC, load balancer, etc.);
- PostgreSQL gerido de produção;
- backups e política de retenção;
- gestor de secrets (AWS Secrets Manager ou equivalente);
- serviço de email para processar os contactos recebidos;
- monitorização/observabilidade (métricas, tracing, alerting);
- pipeline de CI/CD;
- ambiente de staging;
- integração com o frontend real;
- armazenamento partilhado do rate limiting (ver abaixo);
- configuração de proxies de confiança (`trusted proxy`) para aceitar `X-Forwarded-For` de forma segura.

## Health

- `GET /api/v1/health` — liveness. Responde `200 {"status":"ok"}` sempre que o processo está vivo; não acede à base de dados. Usado pelo `HEALTHCHECK` do Docker.
- `GET /api/v1/ready` — readiness. Responde `200 {"status":"ok","database":"ok"}` quando a base de dados responde a `SELECT 1`; responde `503` (formato de erro comum, sem detalhes internos) quando a base de dados está indisponível.

## Segurança e próximos passos

A API limita o corpo do pedido a 16 KiB durante a leitura, valida tipos e comprimentos, rejeita campos extra, restringe CORS e devolve erros sem stack traces ou dados internos. Os logs registam método, caminho, estado, duração e `request_id`, sem guardar a mensagem ou o email do contacto. A resposta de criação não devolve os dados pessoais enviados. As respostas incluem `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` e `X-Request-ID`. Não se aplica CSP global porque a documentação interativa precisa de scripts e estilos próprios.

Erros de base de dados são registados apenas pelo tipo de exceção (nunca pela mensagem, que pode conter parâmetros com dados pessoais); erros inesperados são registados com traceback completo nos logs internos (nunca devolvidos ao cliente), correlacionados pelo `request_id`.

O `POST /api/v1/contacts` aceita até 5 pedidos por minuto por endereço remoto. O `slowapi` usa armazenamento em memória local ao processo: vários workers ou instâncias terão contadores independentes — esta é uma limitação conhecida desta fase. Antes de um deployment multi-instância, configurar armazenamento partilhado (ex.: Redis) ou um limite no gateway; isso pertence a uma fase seguinte. A aplicação usa `request.client.host`; cabeçalhos de proxy só devem alterar esse endereço após configurar proxies de confiança no servidor ASGI.

Antes da produção: configurar credenciais e origins reais, alojar PostgreSQL com backups, estabelecer política de retenção e proteção contra abuso, integrar o frontend, definir o processamento dos contactos e um serviço de email, e configurar observabilidade e deployment. Estas etapas não fazem parte desta fase.
