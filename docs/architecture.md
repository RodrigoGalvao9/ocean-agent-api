# Arquitetura

```text
ocean-frontend
  -> ocean-agent-api
       -> LangGraph
       -> Groq
       -> servidor MCP
            -> PostgreSQL
            -> Qdrant
            -> Redis
            -> fontes externas
```

Esta API não contém credenciais nem modelos de recuperação vetorial. Qdrant, Cloudflare, embeddings e bancos pertencem ao servidor MCP/ingestor.

## Estrutura

```text
src/
├── agent/          LangGraph e portão de escopo
├── api/            Rotas, schemas, dependências e middleware
├── conversations/  Modelos e repositório em memória
├── core/           Configuração, fontes e exceções
├── llm/            Inicialização do Groq
├── mcp/            Cliente MCP e adaptação das ferramentas
├── observability/  Logging, métricas e tracing
├── security/       Limites e validações
└── worker/         Worker ARQ
```
