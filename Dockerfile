FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar a API unificada
COPY api/ ./api

# Copiar os ficheiros estáticos
COPY static/ ./static

ENV PORT=8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
