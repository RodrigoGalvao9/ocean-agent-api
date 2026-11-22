# Ocean Agent API

API HTTP FastAPI que orquestra o agente marítimo brasileiro, gerencia conversas e consulta ferramentas MCP somente leitura.

O projeto usa FastAPI, LangGraph, Groq, MCP Streamable HTTP e observabilidade opcional com Langfuse, Prometheus e Grafana.

## Ecossistema

| Repositório | Responsabilidade |
|---|---|
| [`ocean-agent-api`](https://github.com/RodrigoGalvao9/ocean-agent-api) | API, agente, conversas, segurança e observabilidade |
| [`Ocean-MCP-Ingestor`](https://github.com/RodrigoGalvao9/Ocean-MCP-Ingestor) | Fontes marítimas, ingestão, PostgreSQL, Qdrant, Redis e ferramentas MCP |
| [`ocean-frontend`](https://github.com/RodrigoGalvao9/ocean-frontend) | Interface web React/TypeScript |

```text
frontend -> Agent API -> servidor MCP
                           ├── PostgreSQL
                           ├── Qdrant
                           └── Redis
```

## Início rápido

Python 3.12 ou superior, chave Groq e URL de um servidor MCP são necessários para o chat.

```powershell
.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
python -m pip install -e ".[test]"
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Endpoints principais:

- `GET /health`
- `POST /api/v1/chat`
- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`
- `DELETE /api/v1/conversations/{conversation_id}`

Exemplo:

```bash
curl -c cookies.txt -b cookies.txt \
  -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Como está o mar em Recife agora?"}'
```

## Documentação

- [Instalação e execução](docs/getting-started.md)
- [Configuração e variáveis de ambiente](docs/configuration.md)
- [Endpoints da API](docs/api.md)
- [Segurança e limites](docs/security.md)
- [Fluxo do agente e ferramentas MCP](docs/mcp.md)
- [Arquitetura](docs/architecture.md)
- [Worker em segundo plano](docs/worker.md)
- [Observabilidade](docs/observability.md)
- [Testes](docs/testing.md)
- [Docker e deploy](docs/deployment.md)
- [Limitações conhecidas](docs/limitations.md)

## Estrutura resumida

```text
src/
├── agent/          Agente LangGraph e classificação de escopo
├── api/            Rotas, schemas e middleware
├── conversations/  Histórico em memória
├── core/           Configuração, fontes e exceções
├── llm/            Integração Groq
├── mcp/            Cliente e adaptação das ferramentas
├── observability/  Logs, métricas e Langfuse
├── security/       Guardrails e limites
└── worker/         Worker ARQ e cache
```
