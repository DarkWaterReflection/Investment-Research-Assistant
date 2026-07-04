# Single production image: FastAPI backend + built React frontend + PDF export.
# Cloud Run-ready: listens on $PORT (default 8080), runs as non-root.

# --- Stage 1: build the frontend ---
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Stage 2: install Python dependencies ---
FROM python:3.13-slim AS builder
WORKDIR /src
COPY pyproject.toml ./
COPY core ./core
COPY collectors ./collectors
COPY processors ./processors
COPY llm ./llm
COPY analysis ./analysis
COPY orchestration ./orchestration
COPY reports ./reports
COPY api ./api
RUN pip install --no-cache-dir --prefix=/install ".[pdf]"

# --- Stage 3: runtime ---
FROM python:3.13-slim
# WeasyPrint native libraries (Pango/HarfBuzz) + fonts + curl for healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libharfbuzz-subset0 \
        fonts-dejavu-core \
        shared-mime-info \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY --from=frontend /build/dist /app/static

ENV PYTHONUNBUFFERED=1 \
    STATIC_DIR=/app/static \
    PORT=8080

WORKDIR /app
RUN useradd --create-home appuser
USER appuser

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -sf "http://localhost:${PORT}/health" || exit 1

CMD ["sh", "-c", "uvicorn api.app:app --host 0.0.0.0 --port ${PORT}"]
