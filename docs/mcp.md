# Agente e ferramentas MCP

## Fluxo

1. Valida a mensagem.
2. Identifica o proprietário da conversa.
3. Aplica limites.
4. Localiza ou cria a conversa.
5. Classifica o escopo marítimo.
6. Recusa fora do escopo sem consultar ferramentas.
7. Descobre ferramentas MCP e aplica `ALLOWED_TOOLS`.
8. Executa o agente LangGraph.
9. Converte o resultado em fontes e atribuições.
10. Armazena a resposta no histórico.

## Ferramentas permitidas

| Ferramenta | Função |
|---|---|
| `search_maritime_knowledge` | Busca conceitual no RAG |
| `list_knowledge_topics` | Lista tópicos de conhecimento |
| `get_marine_conditions` | Condições meteorológicas e marítimas Open-Meteo |
| `get_tide_table` | Marés da Marinha do Brasil/DHN |
| `get_fishing_closures` | Defeso da pesca |
| `search_vessels` | Busca de embarcações |
| `find_fish_markets` | Locais para vender pescado |

Somente `search_maritime_knowledge`, `list_knowledge_topics`, `get_marine_conditions` e `get_tide_table` estão implementadas no servidor MCP atual.

## Contrato de proveniência

Cada resultado pode incluir `status`, `source`, `source_url`, `retrieved_at`, `data_timestamp`, `freshness`, `attribution`, `license`, `data` e `limitations`.

Status possíveis:

- `ok`
- `partial`
- `stale`
- `unavailable`

Falhas externas são transformadas em respostas indisponíveis e não devem virar erros HTTP 502.
