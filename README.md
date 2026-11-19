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

## Docker

```bash
docker build -t ocean-agent-api .
docker run --env-file .env -p 8000:8000 ocean-agent-api
```

## Security limitations

The included checks are initial guardrails, not complete prompt-injection
protection. MCP results and retrieved documents must remain untrusted reference
data. API errors do not expose credentials or internal exception details.