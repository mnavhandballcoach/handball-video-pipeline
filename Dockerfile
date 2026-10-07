FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar a pasta api/ para dentro do container
COPY api/ ./api

ENV PORT=8080

# Arrancar FastAPI a partir de api/main.py
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
