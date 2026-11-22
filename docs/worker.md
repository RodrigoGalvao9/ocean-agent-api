# Worker em segundo plano

O worker usa ARQ sobre Redis.

## Arquivos

- `src/worker/settings.py`;
- `src/worker/collectors.py`;
- `src/worker/cache.py`;
- `tests/worker/test_worker.py`.

O worker executa `heartbeat` a cada minuto e `run_collectors` às horas 00, 15, 30 e 45 minutos.

Atualmente não há coletores registrados em `COLLECTORS`.

## Execução

```powershell
python -m arq src.worker.settings.WorkerSettings
```

Verificação:

```powershell
python -m arq src.worker.settings.WorkerSettings --check
```

Com Docker Compose:

```powershell
docker compose up -d redis worker
docker compose logs --tail 100 worker
```

Os dados coletados usam chaves como `ocean:src:<nome_do_coletor>`. O heartbeat usa `ocean:worker:heartbeat`.
