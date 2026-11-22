# Instalação e execução

## Ambiente local

Python 3.12 ou superior é obrigatório.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
Copy-Item .env.example .env
```

Preencha pelo menos `GROQ_API_KEY` e `MCP_SERVER_URL`.

## Executar

```powershell
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Teste:

```powershell
curl.exe http://localhost:8000/health
```

Resposta esperada:

```json
{"status":"ok","service":"ocean-agent-api"}
```

## Dependências

Obrigatórias:

- chave da API Groq;
- servidor MCP compatível com Streamable HTTP.

Opcionais:

- Redis;
- Langfuse;
- Prometheus;
- Grafana;
- Docker e Docker Compose.
