# Configuração

As configurações vêm de variáveis de ambiente e podem ser mantidas no arquivo `.env`.
Não registre valores reais ou credenciais no repositório.

## Integrações obrigatórias

| Variável | Padrão | Descrição |
|---|---|---|
| `GROQ_API_KEY` | vazio | Chave da API Groq |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Modelo usado pelo agente |
| `MCP_SERVER_URL` | `http://localhost:8001/mcp` | Endpoint MCP |
| `MCP_AUTH_TOKEN` | vazio | Bearer enviado ao MCP |
| `ALLOWED_TOOLS` | lista padrão | Ferramentas MCP liberadas |

## MCP

| Variável | Padrão | Descrição |
|---|---|---|
| `REQUEST_TIMEOUT_SECONDS` | `30` | Timeout com servidor considerado acordado |
| `MCP_COLD_START_TIMEOUT_SECONDS` | `60` | Tempo adicional na primeira chamada após pausa |
| `MCP_WARM_WINDOW_SECONDS` | `600` | Período em que o MCP é considerado acordado |
| `MCP_TOOLS_CACHE_TTL_SECONDS` | `300` | Validade da lista de ferramentas |
| `MAX_TOOL_OUTPUT_CHARS` | `12000` | Limite de saída enviada ao modelo |

## Aplicação e CORS

| Variável | Padrão | Descrição |
|---|---|---|
| `API_HOST` | `0.0.0.0` | Interface HTTP |
| `API_PORT` | `8000` | Porta HTTP |
| `LOG_LEVEL` | `INFO` | Nível de logs |
| `ENVIRONMENT` | `development` | Ambiente de execução |
| `CORS_ORIGINS` | `http://localhost:5173` | Origens separadas por vírgula |
| `TRUSTED_PROXY_HOPS` | `1` | Quantidade de proxies confiáveis |

## Redis e conversas

| Variável | Padrão | Descrição |
|---|---|---|
| `REDIS_URL` | vazio | Redis compartilhado |
| `CONVERSATION_SESSION_SECRET` | vazio em development | Assinatura do cookie de conversas |
| `RATE_LIMIT_ENABLED` | `true` | Habilita limites |
| `RATE_LIMIT_CHAT_PER_MINUTE` | `8` | Limite por IP por minuto |
| `RATE_LIMIT_CHAT_PER_DAY` | `100` | Limite por IP por dia |
| `RATE_LIMIT_GLOBAL_PER_MINUTE` | `60` | Limite global por minuto |
| `RATE_LIMIT_READ_PER_MINUTE` | `60` | Limite de operações de leitura |
| `MAX_REQUEST_BODY_BYTES` | `16384` | Tamanho máximo do corpo |
| `MAX_HISTORY_MESSAGES` | `12` | Histórico enviado ao modelo |
| `MAX_MESSAGES_PER_CONVERSATION` | `60` | Mensagens por conversa |
| `MAX_CONVERSATIONS` | `1000` | Conversas mantidas em memória |

Sem Redis, os limites são mantidos somente na instância local.
