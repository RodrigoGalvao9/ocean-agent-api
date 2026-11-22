# Limitações conhecidas

- O plano gratuito do Render pode dormir o MCP. A primeira chamada após uma pausa pode atingir o timeout frio.
- Conversas são armazenadas em memória e desaparecem ao reiniciar.
- Sem Redis compartilhado, limites são válidos apenas na instância atual.
- O cache do MCP deve ser preservado por até 30 minutos para reduzir chamadas ao Open-Meteo.
- Os guardrails são proteções iniciais e não substituem autenticação persistente ou autorização completa.
- Resultados MCP e documentos são dados não confiáveis.
- O sistema não deve prometer segurança para sair ao mar.
