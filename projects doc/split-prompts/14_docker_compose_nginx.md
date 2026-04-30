# Prompt 14 — Docker Compose & Nginx Configuration

## Goal
Write the complete Docker Compose stack (dev + production override) and Nginx configuration. All services must be wired together with correct networking, health checks, and volume mounts. Only Nginx is exposed to the outside world.

## Files to create

---

### `docker-compose.yml` (base — works for local dev)

```yaml
version: "3.9"

networks:
  aip_network:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
  minio_data:
  models_data:      # persists downloaded ML models across container restarts

services:

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks: [aip_network]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks: [aip_network]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    restart: unless-stopped

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"    # S3 API (accessible locally for dev)
      - "9001:9001"    # MinIO web console (accessible locally for dev)
    networks: [aip_network]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - REDIS_URL=redis://redis:6379/0
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
      - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
      - MINIO_USE_SSL=false
      - MINIO_WATCH_BUCKETS=${MINIO_WATCH_BUCKETS:-audio-uploads}
      - WHISPER_MODEL_SIZE=${WHISPER_MODEL_SIZE:-large-v3}
      - WHISPER_DEVICE=${WHISPER_DEVICE:-cpu}
      - WHISPER_COMPUTE_TYPE=${WHISPER_COMPUTE_TYPE:-int8}
      - PYANNOTE_MODEL=${PYANNOTE_MODEL:-pyannote/speaker-diarization-3.1}
      - SENTIMENT_MODEL=${SENTIMENT_MODEL:-cardiffnlp/twitter-roberta-base-sentiment-latest}
      - HF_TOKEN=${HF_TOKEN}
      - MODELS_DIR=/models
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    volumes:
      - models_data:/models
      - ./backend:/app           # hot-reload in dev
    ports:
      - "8000:8000"              # accessible locally for dev
    networks: [aip_network]
    depends_on:
      postgres: { condition: service_healthy }
      redis:    { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.workers.celery_app worker --queues gpu_queue,cpu_queue,celery --concurrency ${CELERY_CONCURRENCY:-2} --loglevel ${LOG_LEVEL:-info}
    environment:
      # Same env vars as backend (copy all)
      - POSTGRES_HOST=postgres
      - REDIS_URL=redis://redis:6379/0
      - MINIO_ENDPOINT=minio:9000
      # ... all others same as backend
      - MODELS_DIR=/models
      - WHISPER_DEVICE=${WHISPER_DEVICE:-cpu}
    volumes:
      - models_data:/models
    networks: [aip_network]
    depends_on:
      postgres: { condition: service_healthy }
      redis:    { condition: service_healthy }
    restart: unless-stopped
    # Scale with: docker compose up --scale worker=4

  beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.workers.celery_app beat --loglevel ${LOG_LEVEL:-info}
    environment:
      # Same as worker
      - POSTGRES_HOST=postgres
      - REDIS_URL=redis://redis:6379/0
    networks: [aip_network]
    depends_on:
      postgres: { condition: service_healthy }
      redis:    { condition: service_healthy }
    restart: unless-stopped
    # Only ONE beat instance ever — never scale this

  flower:
    image: mher/flower:2.0
    command: celery flower --broker=redis://redis:6379/0 --port=5555
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    ports:
      - "5555:5555"    # accessible locally for dev
    networks: [aip_network]
    depends_on: [redis]
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: runner
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000/api/v1
      - NEXT_PUBLIC_WS_URL=ws://backend:8000/api/v1
    networks: [aip_network]
    depends_on: [backend]
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    networks: [aip_network]
    depends_on: [frontend]
    restart: unless-stopped
```

---

### `docker-compose.prod.yml` (production override)

```yaml
# Overrides for production:
# - Remove source code volume mounts (no hot-reload)
# - Remove locally-exposed ports (only nginx is public)
# - Add GPU runtime for worker
# - Use production uvicorn flags

services:
  backend:
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
    volumes:
      - models_data:/models    # only models volume, no source mount
    ports: []                  # remove local port exposure

  worker:
    command: celery -A app.workers.celery_app worker --queues gpu_queue,cpu_queue,celery --concurrency ${CELERY_CONCURRENCY:-4} --loglevel warning
    volumes:
      - models_data:/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  minio:
    ports: []    # remove public MinIO access in production

  flower:
    ports: []    # remove public Flower access in production

  postgres:
    ports: []
```

---

### `nginx/nginx.conf`

```nginx
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    sendfile on;
    keepalive_timeout 65;
    client_max_body_size 250M;    # allow large audio uploads

    # Rate limiting zone
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1000;

    # Redirect HTTP → HTTPS
    server {
        listen 80;
        server_name ${DOMAIN};
        return 301 https://$host$request_uri;
    }

    # HTTPS — Frontend only
    server {
        listen 443 ssl http2;
        server_name ${DOMAIN};

        ssl_certificate     /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000" always;

        # Proxy to Next.js frontend
        location / {
            proxy_pass http://frontend:3000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
            proxy_read_timeout 300s;    # allow long SSR + WS connections
        }

        # Next.js static assets — long cache
        location /_next/static/ {
            proxy_pass http://frontend:3000;
            proxy_cache_valid 200 365d;
            add_header Cache-Control "public, max-age=31536000, immutable";
        }

        # Block direct access to internal services (redundant but defensive)
        location /api/ {
            return 404;
        }
    }
}
```

> **Note:** The Next.js frontend proxies API calls to the backend internally (server-side) using Docker's internal `http://backend:8000`. The browser never calls the backend directly — all API traffic goes through Next.js server components or API routes. WebSocket connections are also proxied through Next.js if needed, or the browser connects to a Next.js API route that upgrades to WS. This keeps the backend truly internal.

---

### `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Health check binary
HEALTHCHECK CMD curl -f http://localhost:8000/api/v1/health || exit 1
```

---

### `frontend/Dockerfile`

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

## Constraints
- `beat` service must never be scaled to more than 1 replica — add a comment warning in the compose file
- Worker GPU config is in `docker-compose.prod.yml` only — dev uses CPU by default
- `client_max_body_size 250M` in Nginx must be larger than `REALTIME_MAX_FILE_MB` (200MB)
- All internal services (postgres, redis, backend, worker, flower) must be on `aip_network` but NOT have ports exposed in `docker-compose.prod.yml`
- Health checks must be present on all data services (postgres, redis, minio, backend)
- `models_data` volume is critical — must persist across `docker compose down` (use named volume, never anonymous)
