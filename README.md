# Ocean Agent API

Ocean Agent API is a FastAPI backend for conversational AI orchestration. It uses
LangGraph to run an agent, Groq for model inference, and the MCP Python SDK to
discover and invoke tools on an independently hosted MCP server.

## Requirements

- Python 3.12+
- A Groq API key for chat requests
- The URL of the remotely hosted MCP Streamable HTTP server

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
cp .env.example .env
```

Set at least `GROQ_API_KEY` and `MCP_SERVER_URL` in `.env`. MCP authentication
is optional; set `MCP_AUTH_TOKEN` when the server requires a bearer token.

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The health endpoint does not connect to Groq or MCP:

```bash
curl http://localhost:8000/health
```

Send a chat message:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hello"}'
```

Continue a conversation by reusing the returned `conversation_id`:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Summarize the previous answer","conversation_id":"CONVERSATION_ID"}'
```

List, retrieve, or delete conversations:

```bash
curl http://localhost:8000/api/v1/conversations
curl http://localhost:8000/api/v1/conversations/CONVERSATION_ID
curl -X DELETE http://localhost:8000/api/v1/conversations/CONVERSATION_ID
```

## Tests

```bash
pytest -q
```

## Architecture

- `src/api`: FastAPI routes, schemas, and request middleware
- `src/agent`: LangGraph graph, state, and system prompt
- `src/llm`: replaceable Groq provider initialization
- `src/mcp`: reusable Streamable HTTP MCP client and LangChain tool adapters
- `src/conversations`: conversation models and an abstract, in-memory repository
- `src/security`: message/tool validation and initial safety guardrails
- `src/observability`: structured JSON-style logging and request metadata

The MCP server is queried for tools at runtime; this project does not define
retrieval tools or recreate ingestion or vector database functionality.

## Separation from `ocean-rag-mcp`

`ocean-rag-mcp` remains the source of truth for knowledge infrastructure:

- FastMCP server and the registered `get_fleet_state`, `buscar_conhecimento`,
  `listar_topicos`, and `set_speed` tools
- Qdrant access, dense Cloudflare embeddings, sparse BM25 embeddings, hybrid
  retrieval, ingestion, and document metadata
- Fleet state, optimistic version checks, and idempotent speed updates

This repository owns the responsibilities that were previously coupled to the
interactive LangGraph application: HTTP entrypoints, Groq configuration,
conversation history, agent prompts and workflow, guardrails, and execution
tracing. The API connects to the MCP server through Streamable HTTP and never
connects directly to Qdrant or Cloudflare embeddings.

The original multi-step maritime graph is not silently recreated here. Its
decision nodes and prompts are the migration source for future API workflows;
the current API provides a safe general-purpose ReAct foundation while that
workflow is ported and tested. Keep `ocean-rag-mcp` independently deployable
until the port is complete.

### Environment ownership

| Variable | Owner |
|---|---|
| `GROQ_API_KEY`, `GROQ_MODEL` | `ocean-agent-api` |
| `MCP_SERVER_URL`, `MCP_AUTH_TOKEN` | `ocean-agent-api` |
| `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION` | `ocean-rag-mcp` |
| Cloudflare embedding credentials/model | `ocean-rag-mcp` |

The MCP server exposes `/health` independently and remains deployable on
Render. Configure its bearer token in the API as `MCP_AUTH_TOKEN`; do not copy
Qdrant or embedding credentials into this project.

## Docker

```bash
docker build -t ocean-agent-api .
docker run --env-file .env -p 8000:8000 ocean-agent-api
```

## Security limitations

The included checks are initial guardrails, not complete prompt-injection
protection. MCP results and retrieved documents must remain untrusted reference
data. API errors do not expose credentials or internal exception details.
## Proteção do chat público

- **Limite por IP** (`RATE_LIMIT_CHAT_PER_MINUTE`, `RATE_LIMIT_CHAT_PER_DAY`), **limite global**
  (`RATE_LIMIT_GLOBAL_PER_MINUTE`, protege a cota do Groq) e limite de leitura. Excedeu: `429` com
  `Retry-After`. Com `REDIS_URL` o contador é compartilhado e sobrevive a deploys; se o Redis cair,
  o limite continua em memória.
- O IP vem do `X-Forwarded-For` conforme `TRUSTED_PROXY_HOPS` (Render = 1). O `X-Client-Id` **não**
  entra no limite, só isola as conversas.
- **Conversas isoladas**: o frontend envia `X-Client-Id` (UUID guardado no navegador); cada cliente
  só lista, abre, apaga e continua as próprias conversas.
- Teto de tamanho do corpo, de mensagens por conversa, de conversas em memória e de histórico
  enviado ao LLM.
- **CORS** só para `CORS_ORIGINS`.

## Observabilidade

- **Langfuse**: defina `LANGFUSE_PUBLIC_KEY` e `LANGFUSE_SECRET_KEY`. Cada pergunta vira um trace
  `ocean-chat` (sessão = conversa, usuário = hash do cliente) com o classificador, o agente e as
  ferramentas aninhados, e a nota `scope_in_scope` (1/0) da decisão de escopo.
- **Prometheus/Grafana**: `GET /metrics` (`Authorization: Bearer $METRICS_TOKEN`). Séries principais:
  `ocean_http_requests_total`, `ocean_scope_decisions_total`, `ocean_chat_outcomes_total`,
  `ocean_mcp_calls_total`, `ocean_rate_limit_rejections_total`, `ocean_redis_errors_total`.
