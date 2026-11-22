# API HTTP

## Enviar mensagem

```bash
curl -c cookies.txt -b cookies.txt \
  -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Quais são as condições marítimas de Recife?"}'
```

Uma chamada sem `conversation_id` cria uma conversa. Para continuar:

```bash
curl -c cookies.txt -b cookies.txt \
  -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"CONVERSATION_ID","message":"E amanhã?"}'
```

Resposta:

```json
{
  "conversation_id": "...",
  "response": "...",
  "request_id": "...",
  "duration_ms": 4210.5,
  "sources": []
}
```

`sources` fica vazio quando nenhuma ferramenta é usada. Fontes usadas ficam em `sources` e no metadata da mensagem armazenada.

## Conversas

```bash
curl -b cookies.txt http://localhost:8000/api/v1/conversations
curl -b cookies.txt http://localhost:8000/api/v1/conversations/CONVERSATION_ID
curl -b cookies.txt -X DELETE http://localhost:8000/api/v1/conversations/CONVERSATION_ID
```

Cada conversa pertence ao proprietário identificado pelo cookie `ocean_session`. Conversas de outro proprietário retornam `404`.
