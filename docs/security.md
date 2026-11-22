# Segurança e limites

O chat aplica:

- limites por IP por minuto e por dia;
- limite global por minuto;
- limite de operações de leitura;
- limite do tamanho do corpo;
- limite de mensagens e conversas;
- limite do histórico enviado ao modelo;
- isolamento de conversas por proprietário;
- validação das mensagens;
- validação dos nomes e argumentos MCP;
- allowlist explícita em `ALLOWED_TOOLS`;
- identificador único por requisição;
- CORS limitado às origens configuradas.

Quando excedido, o chat responde `429 Too Many Requests`.

Mensagens que pedem instruções internas, chaves ou credenciais são bloqueadas.

Os resultados MCP são tratados como dados não confiáveis. O agente deve fundamentar respostas somente nos resultados das ferramentas.
