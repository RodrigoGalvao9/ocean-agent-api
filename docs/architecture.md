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

## Fluxo de uma pergunta

```text
pergunta
  -> validação e normalização local
  -> portão de escopo
  -> refinador condicional OpenRouter
  -> LangGraph + Groq
  -> ferramentas MCP/Qdrant
  -> revisor determinístico
  -> revisor Ultra somente em perguntas complexas
  -> resposta
```

O histórico longo é resumido localmente antes de ser enviado aos modelos. O refinador só é chamado para perguntas ambíguas ou continuadas. Consultas claras seguem diretamente para o Groq e o MCP.

As respostas complexas usam uma única tentativa de validação/correção. Falhas ou timeouts do refinador e do Validador não interrompem o fluxo principal.

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
