# Observabilidade

## Logs

Os logs usam `structlog` e o nível configurado por `LOG_LEVEL`.

## Prometheus

As métricas incluem requisições, decisões de escopo, respostas, chamadas MCP, ferramentas MCP, rejeições de limites, rotas de refinamento e validações.

Também existem métricas por etapa:

- `ocean_llm_stage_duration_seconds`: latência do portão de escopo, refinador, agente e Validador;
- `ocean_llm_estimated_tokens_total`: estimativa de tokens de entrada e saída por etapa;
- `ocean_question_routes_total`: distribuição entre perguntas simples, dados ao vivo, conhecimento e consultas complexas;
- `ocean_response_validations_total`: aprovações, rejeições e falhas do Validador.

Os tokens são estimados localmente pelo tamanho do texto, pois os provedores não são consultados por uma API unificada de uso nesta etapa.

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
