FROM python:3.12-slim

WORKDIR /app
COPY src ./src
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e .

# Usuário sem privilégios: um comprometimento do processo não vira root no container.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin ocean \
    && chown -R ocean:ocean /app
USER ocean

ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
