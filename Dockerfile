FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# System deps for xgboost / shap
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY model_artifacts/ ./model_artifacts/

EXPOSE 8080

# 2 workers x 4 threads = handles ~8 concurrent reqs per instance
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 0 \
    --access-logfile - --error-logfile - \
    "app.app:create_app()"
