FROM python:3.12-slim

WORKDIR /app
COPY src ./src
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
