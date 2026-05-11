FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

# Liveness probe for the ml-api entrypoint. Worker variants (celery)
# don't run on port 8000 so the HEALTHCHECK simply no-ops their probe
# — K8s deployments override this with WORKER_HEALTH_SERVER + an
# httpGet probe on port 8001 (see src/utils/worker_health.py).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["python", "-c", "print('worldcup-predictor base image — override CMD in compose')"]
