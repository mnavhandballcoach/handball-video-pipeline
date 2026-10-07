FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar apenas a pasta app/ onde está o teu main.py
COPY app/ ./app

ENV PORT=8080

# Arrancar FastAPI a partir de app/main.py
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
