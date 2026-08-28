# Legend — backend API image (the Legend engine + FastAPI).
#
#   docker build -t legend .
#   docker run --rm -p 8100:8100 -v kyc-data:/data legend
#
# Serves the REST API on :8100 (interactive docs at /docs). Repo indexing, the code
# graph and BM25 retrieval work out of the box; set provider keys via -e to enable
# LLM answers. Build the SPA separately (cd app/frontend && npm ci && npm run build)
# and serve app/frontend/dist behind a proxy that forwards /api to this container,
# or use ./app/run.sh for the full dev experience on macOS/Linux.
FROM python:3.12-slim

# git is required at runtime: repo ingestion shells out to `git clone`.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching.
COPY app/backend/requirements.txt ./app/backend/requirements.txt
RUN pip install --no-cache-dir -r app/backend/requirements.txt

# App code: the engine, the backend, and the codemap tool the backend imports.
COPY engine/ ./engine/
COPY app/backend/ ./app/backend/
COPY diagrams/ ./diagrams/

# Bind on all interfaces inside the container (main.py honours LEGEND_HOST); the
# TrustedHost middleware still only accepts localhost Host headers, so reach it as
# http://localhost:8100 from the host. Persist indexes/caches on a volume.
ENV LEGEND_HOST=0.0.0.0 \
    LEGEND_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8100

WORKDIR /app/app/backend
CMD ["python", "main.py"]
