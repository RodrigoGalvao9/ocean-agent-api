# Docker e deploy

## Docker

```powershell
docker build -t ocean-agent-api .
docker run --env-file .env -p 8000:8000 ocean-agent-api
```

O Docker Compose disponibiliza Redis, worker, Redis Insight, Prometheus e Grafana:

```powershell
docker compose up -d
docker compose --profile api up -d
```

No Compose, a API usa:

```text
REDIS_URL=redis://redis:6379/0
MCP_SERVER_URL=http://host.docker.internal:8001/mcp
```

## Render

Publique primeiro o servidor MCP e depois esta API.

Em produção:

- `MCP_SERVER_URL` deve usar HTTPS;
- `MCP_AUTH_TOKEN` é obrigatório;
- o token deve ser igual ao configurado no MCP;
- `CONVERSATION_SESSION_SECRET` deve ser um segredo forte;
- `ENVIRONMENT=production`;
- `METRICS_TOKEN` deve proteger `/metrics`, quando utilizado.
- `OPENROUTER_API_KEY` ativa o refinador opcional da pergunta;
- `OPENROUTER_REFINER_MODEL` define o modelo barato usado pelo refinador.
- `OPENROUTER_VALIDATOR_MODEL` define o modelo usado para revisar consultas complexas.
