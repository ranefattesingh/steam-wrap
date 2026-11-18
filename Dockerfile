# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY steam_wrap ./steam_wrap
RUN pip install .

COPY app.py config.yaml ./

RUN useradd --create-home --uid 10001 appuser
USER appuser

ENV STEAMWRAP_APP__ENVIRONMENT=production \
    STEAMWRAP_APP__LOG_JSON=true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').status == 200 else 1)"

# One worker: the cache is in-process. Scale with more containers, or switch
# the cache to a shared backend (see docs/ARCHITECTURE.md) before adding workers.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
