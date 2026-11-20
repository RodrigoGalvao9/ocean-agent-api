# Ocean Agent API

Ocean Agent API é uma API HTTP construída com FastAPI para orquestrar agentes de IA especializados no domínio marítimo brasileiro. O projeto utiliza LangGraph para executar o agente, Groq para inferência dos modelos, Langfuse para rastreamento opcional e o MCP Python SDK para descobrir e executar ferramentas em um servidor MCP remoto.

O sistema foi projetado para manter os dados marítimos fora deste repositório. Por essa razão, a API consulta ferramentas fornecidas pelo servidor MCP independemente hospedado em vez de se conectar diretamente a bancos vetoriais, provedores de embeddings ou serviços de coleta.

## Responsabilidades do projeto

Este repositório contém:

- endpoints HTTP com FastAPI;
- classificação de escopo das mensagens;
- regras de segurança para ferramentas e mensagens;
- execução de agentes com LangGraph;
- histórico de conversas em memória;
- isolamento básico das conversas por cliente;
- limites de requisições com Redis opcional;
- integração com o servidor MCP;
- métricas Prometheus;
- rastreamento opcional no Langfuse;
- worker ARQ para coletas periódicas em segundo plano;
- configuração de Redis, Prometheus e Grafana para desenvolvimento local.

O projeto não contém modelos de recuperação vetorial, configuração do Qdrant ou credenciais de embedding.

## Dependências externas

### Obrigatórias para o chat

- Python 3.12 ou superior;
- chave da API Groq;
- URL de um servidor MCP compatível com Streamable HTTP.

### Opcionais

- Redis, para compartilhar contadores de limite entre instâncias;
- credenciais Langfuse, para rastreamento das execuções;
- Prometheus, para coleta de métricas;
- Grafana, para visualização das métricas;
- Docker e Docker Compose, para executar a infraestrutura local.

## Configuração do ambiente

### Ambiente local

Crie um ambiente virtual e instale o projeto com as dependências de execução e teste:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
cp .env.example .env
```

No Windows, a ativação do ambiente virtual pode ser feita com:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
Copy-Item .env.example .env
```

Preencha o arquivo `.env` antes de iniciar a API. Em particular, `GROQ_API_KEY` e `MCP_SERVER_URL` são necessários para executar o chat. `MCP_AUTH_TOKEN` só é necessário quando o servidor MCP exige autenticação bearer.

O arquivo `.env.example` contém os nomes e os valores padrão de todas as opções reconhecidas pelo projeto. Valores reais ou secretos não devem ser registrados no repositório.

### Variáveis principais

| Variável | Padrão | Descrição |
|---|---|---|
| `API_HOST` | `0.0.0.0` | Interface usada pelo processo da API |
| `API_PORT` | `8000` | Porta usada pelo processo da API |
| `GROQ_API_KEY` | vazio | Chave da API Groq |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Modelo usado pelo agente |
| `MCP_SERVER_URL` | `http://localhost:8001/mcp` | URL do endpoint MCP |
| `MCP_AUTH_TOKEN` | vazio | Token bearer enviado ao servidor MCP |
| `ALLOWED_TOOLS` | `buscar_conhecimento,listar_topicos` | Lista separada por vírgulas das ferramentas MCP permitidas |
| `REQUEST_TIMEOUT_SECONDS` | `30` | Timeout das operações MCP |
| `LOG_LEVEL` | `INFO` | Nível dos logs estruturados |
| `ENVIRONMENT` | `development` | Ambiente de execução |

### CORS e proxies

| Variável | Padrão | Descrição |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173` | Origens CORS separadas por vírgulas |
| `TRUSTED_PROXY_HOPS` | `1` | Quantidade de proxies confiáveis à frente da aplicação |

`TRUSTED_PROXY_HOPS` controla a leitura do cabeçalho `X-Forwarded-For`. Em plataformas como o Render, o valor normalmente utilizado é `1`. Em execução direta sem proxy confiável, o valor recomendado é `0`.

### Limites e Redis

| Variável | Padrão | Descrição |
|---|---|---|
| `REDIS_URL` | vazio | URL Redis; vazio ativa somente o limite em memória |
| `RATE_LIMIT_ENABLED` | `true` | Ativa ou desativa os limites |
| `RATE_LIMIT_CHAT_PER_MINUTE` | `8` | Máximo de chamadas de chat por IP por minuto |
| `RATE_LIMIT_CHAT_PER_DAY` | `100` | Máximo de chamadas de chat por IP por dia |
| `RATE_LIMIT_GLOBAL_PER_MINUTE` | `60` | Máximo global de chamadas de chat por minuto |
| `RATE_LIMIT_READ_PER_MINUTE` | `60` | Máximo de operações de leitura por IP por minuto |
| `MAX_REQUEST_BODY_BYTES` | `16384` | Tamanho máximo do corpo HTTP |
| `MAX_HISTORY_MESSAGES` | `12` | Histórico mais recente enviado ao modelo |
| `MAX_MESSAGES_PER_CONVERSATION` | `60` | Máximo de mensagens por conversa |
| `MAX_CONVERSATIONS` | `1000` | Máximo de conversas mantidas em memória |

Sem `REDIS_URL`, os contadores são mantidos somente na instância local e são reiniciados a cada processo ou deploy. Com Redis configurado, os contadores podem ser compartilhados entre instâncias. Quando o Redis falha, o limite continua funcionando temporariamente em memória.

### Langfuse

| Variável | Padrão | Descrição |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | vazio | Chave pública Langfuse |
| `LANGFUSE_SECRET_KEY` | vazio | Chave secreta Langfuse |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Endpoint Langfuse |
| `LANGFUSE_SAMPLE_RATE` | `1.0` | Taxa de amostragem |

O rastreamento fica desativado quando as duas chaves Langfuse estão vazias. É seguro deixar o ambiente de desenvolvimento sem essas credenciais.

### Métricas

| Variável | Padrão | Descrição |
|---|---|---|
| `METRICS_TOKEN` | vazio | Token bearer exigido pelo endpoint `/metrics` em produção |

Em ambiente de desenvolvimento, o endpoint `/metrics` pode ser acessado diretamente. Em produção, `ENVIRONMENT=production` exige `METRICS_TOKEN` e o cabeçalho:

```text
Authorization: Bearer <METRICS_TOKEN>
```

## Inicialização da API

### Execução direta

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Após a inicialização, os principais endpoints são:

- `GET http://localhost:8000/health`;
- `POST http://localhost:8000/api/v1/chat`;
- `GET http://localhost:8000/api/v1/conversations`;
- `GET http://localhost:8000/api/v1/conversations/{conversation_id}`;
- `DELETE http://localhost:8000/api/v1/conversations/{conversation_id}`;
- `GET http://localhost:8000/metrics`.

O endpoint `/health` não consulta Groq ou MCP.

### Execução com Docker

O Dockerfile utiliza Python 3.12 e inicia o Uvicorn na porta definida pela variável `PORT`:

```bash
docker build -t ocean-agent-api .
docker run --env-file .env -p 8000:8000 ocean-agent-api
```

O Docker Compose disponibiliza Redis, worker, Redis Insight, Prometheus e Grafana:

```bash
docker compose up -d
```

A API pode ser iniciada em container, junto com a infraestrutura, com:

```bash
docker compose --profile api up -d
```

Neste modo, o Compose utiliza `redis://redis:6379/0` para Redis e `http://host.docker.internal:8001/mcp` como URL padrão do MCP quando a API roda em um container.

## Endpoints da API

### Verificação de integridade

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{
  "status": "ok",
  "service": "ocean-agent-api"
}
```

### Envio de mensagem

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Client-Id: 550e8400-e29b-41d4-a716-446655440000' \
  -d '{"message":"Quais são as condições marítimas de Santos?"}'
```

Uma chamada sem `conversation_id` cria uma nova conversa. Para continuar uma conversa existente, reutilize o `conversation_id` retornado pela resposta:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Client-Id: 550e8400-e29b-41d4-a716-446655440000' \
  -d '{
    "message":"E amanhã?",
    "conversation_id":"CONVERSATION_ID"
  }'
```

O cabeçalho `X-Client-Id` isola as conversas no repositório em memória. Um valor válido contém entre 16 e 64 caracteres alfanuméricos, `_` ou `-`. Quando o cabeçalho não é informado ou é inválido, o proprietário é derivado do endereço IP.

### Listagem de conversas

```bash
curl -H 'X-Client-Id: 550e8400-e29b-41d4-a716-446655440000' \
  http://localhost:8000/api/v1/conversations
```

### Consulta de uma conversa

```bash
curl -H 'X-Client-Id: 550e8400-e29b-41d4-a716-446655440000' \
  http://localhost:8000/api/v1/conversations/CONVERSATION_ID
```

### Exclusão de uma conversa

```bash
curl -X DELETE \
  -H 'X-Client-Id: 550e8400-e29b-41d4-a716-446655440000' \
  http://localhost:8000/api/v1/conversations/CONVERSATION_ID
```

Um identificador pertencente a outro proprietário retorna `404`. A API não inclui o proprietário interno nas respostas.

## Proteção da API

As proteções atuais incluem:

- limite por IP por minuto;
- limite por IP por dia;
- limite global por minuto;
- limite de operações de leitura por IP;
- limite do tamanho do corpo da requisição;
- limite de mensagens por conversa;
- limite de conversas mantidas em memória;
- limite do histórico enviado ao modelo;
- isolamento de conversas por proprietário;
- validação dos nomes e argumentos das ferramentas MCP;
- lista explícita de ferramentas permitidas;
- identificador único por requisição;
- CORS limitado pelas origens configuradas.

Quando um limite é excedido, a API retorna `429 Too Many Requests` e pode incluir:

- `Retry-After`;
- `X-RateLimit-Limit`;
- `X-RateLimit-Remaining`.

O CORS permite somente os valores definidos em `CORS_ORIGINS`.

## Fluxo de execução do agente

Uma requisição de chat passa pelas seguintes etapas:

1. A mensagem é validada e sanitizada.
2. O proprietário da conversa é identificado.
3. Os limites de requisição são aplicados.
4. A conversa existente é localizada ou uma nova conversa é criada.
5. A mensagem é classificada quanto ao escopo marítimo.
6. Quando a mensagem está fora de escopo, o agente responde sem consultar ferramentas.
7. Quando está dentro do escopo, o servidor MCP é consultado.
8. Somente as ferramentas listadas em `ALLOWED_TOOLS` podem ser utilizadas.
9. O LangGraph executa o agente com o histórico recente permitido.
10. A resposta é validada e armazenada no histórico da conversa.

As ferramentas MCP e os documentos recuperados são considerados dados não confiáveis. O agente é instruído a responder somente a partir dos resultados das ferramentas e não deve recriar conhecimento diretamente no modelo.

## Worker em segundo plano

O worker utiliza ARQ sobre Redis para executar coletas programadas e armazenar resultados no cache Redis.

Arquivos principais:

- `src/worker/settings.py`: configuração do worker e agendamentos;
- `src/worker/collectors.py`: registro dos coletores;
- `src/worker/cache.py`: leitura e escrita do cache;
- `tests/worker/test_worker.py`: testes do cache e da execução dos coletores.

O worker executa `heartbeat` a cada minuto e `run_collectors` às horas 00, 15, 30 e 45 minutos. A falha de um coletor não impede a execução dos demais.

Execução direta:

```bash
python -m arq src.worker.settings.WorkerSettings
```

Verificação de saúde:

```bash
python -m arq src.worker.settings.WorkerSettings --check
```

Execução em Docker:

```bash
docker compose up -d redis worker
docker compose logs --tail 100 worker
```

Atualmente, `COLLECTORS` não possui coletores registrados. Os primeiros coletores devem ser adicionados em `src/worker/collectors.py` e testados antes do uso em produção.

Os dados coletados são armazenados com TTL no Redis usando a chave:

```text
ocean:src:<nome_do_coletor>
```

A chave `ocean:worker:heartbeat` registra o último funcionamento conhecido do worker.

## Observabilidade

### Logs

Os logs são emitidos em formato estruturado por meio de `structlog`. O nível é configurado por `LOG_LEVEL`.

### Métricas Prometheus

As métricas públicas incluem:

- `ocean_http_requests_total`;
- `ocean_http_request_duration_seconds`;
- `ocean_scope_decisions_total`;
- `ocean_chat_outcomes_total`;
- `ocean_mcp_calls_total`;
- `ocean_mcp_call_duration_seconds`;
- `ocean_rate_limit_rejections_total`;
- `ocean_redis_errors_total`.

Com Docker Compose, o Prometheus está disponível em `http://localhost:9090`. A configuração de coleta está em `monitoring/prometheus.yml`.

Quando `METRICS_TOKEN` estiver definido em produção, o Prometheus precisa usar autenticação bearer. A configuração de autenticação pode ser criada em `monitoring/metrics_token` e incluída no serviço Prometheus conforme o comentário existente em `monitoring/prometheus.yml`.

### Grafana

Com Docker Compose, o Grafana está disponível em `http://localhost:3000`.

Credenciais padrão:

- usuário: `admin`;
- senha: `admin`.

A senha pode ser substituída pela variável `GRAFANA_ADMIN_PASSWORD` no ambiente utilizado pelo Docker Compose.

O projeto provisiona automaticamente:

- fonte de dados Prometheus;
- dashboard `Ocean — visão geral`;
- renovação de dados a cada 30 segundos.

Arquivos de provisionamento:

- `monitoring/grafana/provisioning/datasources/prometheus.yml`;
- `monitoring/grafana/provisioning/dashboards/ocean.yml`;
- `monitoring/grafana/dashboards/ocean-overview.json`.

### Langfuse

Quando configurado, o Langfuse recebe um trace `ocean-chat` por requisição. O trace agrupa:

- classificador de escopo;
- execução do agente;
- chamadas às ferramentas;
- resultado da execução;
- sessão da conversa;
- usuário derivado de forma anônima;
- score `scope_in_scope`, com `1.0` dentro do escopo e `0.0` fora do escopo.

Falhas de inicialização, envio ou atualização no Langfuse não devem interromper o chat.

## Testes

Execute toda a suíte:

```bash
pytest -q
```

Execuções específicas:

```bash
pytest -q tests/api
pytest -q tests/security
pytest -q tests/observability
pytest -q tests/worker
```

Os testes cobrem, entre outros comportamentos:

- limites de chat e leitura;
- fallback do Redis;
- isolamento de conversas;
- limites de tamanho e quantidade;
- identificação do cliente;
- interação com o MCP;
- tracing Langfuse;
- cache e execução isolada dos coletores.

## Arquitetura do repositório

```text
src/
├── agent/          Orquestração LangGraph e portão de escopo
├── api/            Rotas, schemas, dependências e middleware
├── conversations/  Modelos e repositório de conversas
├── core/           Configuração e exceções
├── llm/            Inicialização do provedor Groq
├── mcp/            Cliente MCP e adaptação das ferramentas
├── observability/  Logging, métricas e Langfuse
├── security/       Limites, identificação e validações
├── worker/         Cache, coletores e worker ARQ
└── main.py         Inicialização da aplicação FastAPI
```

## Separação entre este projeto e o servidor MCP

Este repositório é responsável pela API, pela configuração do Groq, pelas conversas, pelo agente, pelas regras de segurança e pelo tracing.

O servidor MCP externo continua responsável pelas fontes marítimas e pelas ferramentas disponíveis. Não devem ser copiadas para esta API credenciais de Qdrant, Cloudflare, embeddings ou bancos de dados utilizados pelo servidor MCP.

Variáveis relacionadas ao conhecimento marítimo pertencem ao servidor MCP e não são variáveis desta API:

- `QDRANT_URL`;
- `QDRANT_API_KEY`;
- `QDRANT_COLLECTION`;
- credenciais e modelo de embedding.

## Limitações conhecidas

- As conversas são armazenadas somente em memória. Reinicializações apagam o histórico.
- Sem Redis, os limites de requisição são válidos apenas dentro da instância que recebeu a requisição.
- As proteções implementadas são verificações iniciais e não substituem uma análise completa de segurança de aplicações públicas.
- Resultados do MCP e documentos recuperados devem continuar sendo tratados como dados não confiáveis.
- Erros externos são registrados sem devolver credenciais ou detalhes internos aos clientes.
- Os limites e guardrails não substituem autenticação de usuários, autorização persistente ou um banco de dados externo.
- Os coletores do worker ainda não possuem integrações registradas.

## Dependências Python

As dependências diretas são declaradas em `pyproject.toml`. Para atualizar ou regenerar o arquivo de dependências fixadas:

```bash
python -m pip install pip-tools
pip-compile pyproject.toml --extra test -o requirements.txt --upgrade
```

Para uma instalação limpa baseada no projeto:

```bash
python -m pip install -e ".[test]"
python -m pip check
```
