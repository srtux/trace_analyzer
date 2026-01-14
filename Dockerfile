# --- Builder Stage for Flutter Web ---
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y \
    curl git unzip xz-utils libglu1-mesa \
    && rm -rf /var/lib/apt/lists/*

# Install Flutter
RUN git clone https://github.com/flutter/flutter.git -b stable /flutter
ENV PATH="/flutter/bin:$PATH"
RUN flutter doctor

WORKDIR /app
COPY autosre/ ./autosre/
WORKDIR /app/autosre
RUN flutter build web --release

# --- Production Stage ---
FROM python:3.11-slim

# 1. Setup Python Backend
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY sre_agent/ ./sre_agent/
COPY server.py .
COPY README.md .

# Install dependencies and the local package
RUN uv pip install --system --no-cache . uvicorn fastapi google-adk google-cloud-aiplatform nest-asyncio mcp pydantic-core

# 2. Setup Flutter Web Frontend (from builder)
COPY --from=builder /app/autosre/build/web ./web/

# 3. Startup Script
COPY scripts/start_unified.sh .
RUN chmod +x start_unified.sh

# Environment variables
ENV PORT=8080
ENV HOSTNAME="0.0.0.0"
ENV SRE_AGENT_URL="http://127.0.0.1:8001"

CMD ["./start_unified.sh"]
