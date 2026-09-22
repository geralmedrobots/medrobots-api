# Med Robots API

Backend local para guardar pedidos de contacto da Med Robots. É uma API independente do website `paulositecopy` e **ainda não está em produção**. Nesta fase não envia emails nem altera o frontend.

## Stack e arquitetura

Python 3.14, FastAPI, Pydantic, SQLAlchemy 2, Alembic e PostgreSQL 17. O router valida a entrada e chama o serviço; o serviço chama o repositório; o repositório usa uma sessão SQLAlchemy gerida por pedido. A migração cria a tabela `contacts`. Não há autenticação, painel administrativo ou outros serviços.

```text
app/
  main.py                 aplicação, CORS, erros, logging e lifecycle
  api/router.py           router principal
  api/v1/                 health e contacts
  core/                   configuração e logging
  db/                     engine, sessão e model Contact
  schemas/                contratos de entrada e saída
  services/               lógica do pedido de contacto
  repositories/           persistência
migrations/               migração inicial Alembic
tests/unit/               schemas e configuração
tests/integration/        API, persistência e migração
tests/security/           erros, limites e CORS
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

O exemplo permite `http://localhost:5173`, `http://127.0.0.1:5173` e `http://127.0.0.1:4173` para desenvolvimento. Ajustar `CORS_ORIGINS` à origem real do frontend antes de qualquer publicação. O valor `*` é rejeitado. O Docker Compose usa credenciais **apenas locais de desenvolvimento**; não as reutilizar fora do ambiente local.

Em `ENVIRONMENT=production`, definir explicitamente `DATABASE_URL` e `CORS_ORIGINS`; as origens têm de usar HTTPS e as credenciais de exemplo são rejeitadas. Os valores de desenvolvimento por defeito não são aceites como configuração implícita de produção. CORS é uma política dos browsers; clientes sem `Origin` continuam a poder chamar o endpoint público. Pedidos com `Origin` não autorizada são rejeitados.

## Execução local

Com Python 3.14 e PostgreSQL disponível:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
# Ajustar DATABASE_URL para o PostgreSQL local
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

## Execução com Docker

Com o Docker daemon ativo, sem instalar PostgreSQL no Mac:

```bash
docker compose up --build -d
curl http://127.0.0.1:8000/api/v1/health
docker compose logs -f api
docker compose down
```

O serviço `api` aguarda a saúde do PostgreSQL, aplica `alembic upgrade head` e inicia o Uvicorn. A API fica acessível apenas em `127.0.0.1:8000` no host. O volume `postgres_data` conserva os dados entre reinícios. Para apagar os dados locais de desenvolvimento, usar `docker compose down -v` conscientemente.

Se a porta 8000 já estiver ocupada, executar `API_PORT=8001 docker compose up --build -d` e aceder à API em `127.0.0.1:8001`.

## Endpoints e documentação

- `GET /api/v1/health` → `200 {"status":"ok"}`. Indica apenas que a aplicação responde; não testa a base de dados.
- `POST /api/v1/contacts` → `201` com `id`, `status` e `created_at`. Aceita `first_name`, `last_name`, `email`, `phone`, `address` e `message`. Nome, apelido, email e mensagem são obrigatórios. `phone` e `address` são opcionais. Campos desconhecidos, valores inválidos e texto vazio são rejeitados.
- `/docs`, `/redoc` e `/openapi.json` mostram o contrato OpenAPI.

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

## Segurança e próximos passos

A API limita o corpo do pedido a 16 KiB durante a leitura, valida tipos e comprimentos, rejeita campos extra, restringe CORS e devolve erros sem stack traces ou dados internos. Os logs registam método, caminho, estado e duração, sem guardar a mensagem ou o email do contacto. A resposta de criação não devolve os dados pessoais enviados. As respostas incluem `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` e `Referrer-Policy: no-referrer`. Não se aplica CSP global porque a documentação interativa precisa de scripts e estilos próprios.

O `POST /api/v1/contacts` aceita até 5 pedidos por minuto por endereço remoto. O `slowapi` usa armazenamento em memória local ao processo: vários workers ou instâncias terão contadores independentes. Antes de um deployment multi-instância, configurar armazenamento partilhado ou um limite no gateway. A aplicação usa `request.client.host`; cabeçalhos de proxy só devem alterar esse endereço após configurar proxies de confiança no servidor ASGI.

Antes da produção: configurar credenciais e origins reais, alojar PostgreSQL com backups, estabelecer política de retenção e proteção contra abuso, integrar o frontend, definir o processamento dos contactos e um serviço de email, e configurar observabilidade e deployment. Estas etapas não fazem parte desta fase.
