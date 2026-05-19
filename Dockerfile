# syntax=docker/dockerfile:1

# amd64 for reliable onnxruntime wheels on cloud hosts (Railway, etc.).
FROM --platform=linux/amd64 python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    HF_HOME=/app/.cache/huggingface \
    HF_HUB_CACHE=/app/.cache/huggingface/hub \
    HUGGINGFACE_HUB_CACHE=/app/.cache/huggingface/hub \
    OMP_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
COPY api.py ./
COPY src ./src
COPY docker-entrypoint.sh ./

RUN mkdir -p /app/.cache/huggingface/hub \
    && chmod +x /app/docker-entrypoint.sh \
    && uv sync --frozen --no-dev \
    && .venv/bin/python src/agent.py download-files

# LiveKit agent worker (self-hosted: set LIVEKIT_URL in .env).
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["start"]
