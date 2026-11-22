# Testes

## Executar tudo

```powershell
.venv\Scripts\python.exe -m pytest
```

## Execuções específicas

```powershell
.venv\Scripts\python.exe -m pytest tests/api
.venv\Scripts\python.exe -m pytest tests/security
.venv\Scripts\python.exe -m pytest tests/observability
.venv\Scripts\python.exe -m pytest tests/worker
.venv\Scripts\python.exe -m pytest tests/mcp
.venv\Scripts\python.exe -m pytest tests/core
```

A suíte cobre limites, fallback do Redis, isolamento de conversas, validação, MCP, proveniência das fontes, recusas, tracing e worker.

Os testes não exigem credenciais externas. O workflow GitHub Actions executa a suíte no Python 3.12.
