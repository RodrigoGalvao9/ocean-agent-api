# Observabilidade

## Logs

Os logs usam `structlog` e o nível configurado por `LOG_LEVEL`.

## Prometheus

As métricas incluem requisições, decisões de escopo, respostas, chamadas MCP, ferramentas MCP e rejeições de limites.

Com Docker Compose:

```text
http://localhost:9090
```

Em produção, `METRICS_TOKEN` pode proteger o endpoint `/metrics`.

## Grafana

Com Docker Compose:

```text
http://localhost:3000
```

Credenciais padrão:

- usuário: `admin`
- senha: `admin`

O Compose provisiona Prometheus como fonte de dados e o dashboard `Ocean — visão geral`.

## Langfuse

Quando `LANGFUSE_PUBLIC_KEY` e `LANGFUSE_SECRET_KEY` estiverem configuradas, cada chat recebe um trace `ocean-chat`.

O conteúdo só é capturado quando `LANGFUSE_CAPTURE_CONTENT=true`.
