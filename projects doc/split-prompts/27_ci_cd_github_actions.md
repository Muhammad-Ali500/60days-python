# Prompt 27 — CI/CD Pipeline (GitHub Actions)

## Goal
Write GitHub Actions workflows for linting, testing, building Docker images, and deploying to production. Covers backend and frontend pipelines.

## Files to create

```
.github/
├── workflows/
│   ├── ci.yml          ← runs on every PR and push to main
│   ├── deploy.yml      ← runs only on push to main after CI passes
│   └── models.yml      ← weekly check that models are downloadable
```

---

### `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  backend-lint:
    name: Backend — Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { python-version: "3.12" }
      - run: uv sync --dev
        working-directory: backend
      - run: uv run ruff check app/ tests/
        working-directory: backend
      - run: uv run ruff format --check app/ tests/
        working-directory: backend
      - run: uv run mypy app/
        working-directory: backend

  backend-test:
    name: Backend — Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: aip_test
          POSTGRES_USER: aip_user
          POSTGRES_PASSWORD: testpassword
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U aip_user -d aip_test"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 3s
          --health-retries 5
    env:
      POSTGRES_HOST: localhost
      POSTGRES_PORT: 5432
      POSTGRES_DB: aip_test
      POSTGRES_USER: aip_user
      POSTGRES_PASSWORD: testpassword
      REDIS_URL: redis://localhost:6379/0
      MINIO_ENDPOINT: localhost:9000
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
      WHISPER_DEVICE: cpu
      WHISPER_COMPUTE_TYPE: int8
      WHISPER_MODEL_SIZE: tiny    # tiny model for CI speed
      HF_TOKEN: ""
      MODELS_DIR: /tmp/models
      LOG_LEVEL: WARNING
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { python-version: "3.12" }
      - run: sudo apt-get install -y ffmpeg
      - run: uv sync --dev
        working-directory: backend
      - run: uv run alembic upgrade head
        working-directory: backend
      - run: |
          uv run pytest tests/ \
            -m "not integration" \
            --tb=short \
            -q
        working-directory: backend

  frontend-lint:
    name: Frontend — Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "22", cache: "npm", cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
        working-directory: frontend
      - run: npm run lint
        working-directory: frontend
      - run: npm run typecheck
        working-directory: frontend

  frontend-test:
    name: Frontend — Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "22", cache: "npm", cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
        working-directory: frontend
      - run: npm test
        working-directory: frontend

  build:
    name: Build Docker Images
    runs-on: ubuntu-latest
    needs: [backend-lint, backend-test, frontend-lint, frontend-test]
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - name: Build backend image
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: false
          tags: aip-backend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - name: Build frontend image
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: false
          tags: aip-frontend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

### `.github/workflows/deploy.yml`

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:    # allow manual trigger

jobs:
  deploy:
    name: Deploy
    runs-on: ubuntu-latest
    environment: production    # requires GitHub environment approval
    steps:
      - uses: actions/checkout@v4

      - name: Build and push backend image
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/backend:${{ github.sha }}
            ghcr.io/${{ github.repository }}/backend:latest
          # Requires GHCR_TOKEN secret

      - name: Build and push frontend image
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/frontend:${{ github.sha }}
            ghcr.io/${{ github.repository }}/frontend:latest

      - name: Deploy to server via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          script: |
            cd /opt/aip
            echo "${{ secrets.GHCR_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
            docker compose pull
            docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans
            docker compose exec -T backend alembic upgrade head
            docker image prune -f
            echo "Deploy complete: ${{ github.sha }}"
```

---

### `.github/workflows/models.yml`

Weekly check that models can be downloaded (catches HuggingFace URL changes):

```yaml
name: Model Availability Check

on:
  schedule:
    - cron: "0 6 * * 1"    # Every Monday 6 AM UTC
  workflow_dispatch:

jobs:
  check-models:
    name: Verify model availability
    runs-on: ubuntu-latest
    env:
      MODELS_DIR: /tmp/models-check
      WHISPER_MODEL_SIZE: tiny    # tiny for speed, just checking download works
      HF_TOKEN: ${{ secrets.HF_TOKEN }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { python-version: "3.12" }
      - run: uv sync
        working-directory: backend
      - run: uv run python -m app.scripts.download_models
        working-directory: backend
      - name: Notify on failure
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          payload: '{"text": "⚠️ AIP model download check failed. Check HuggingFace URLs."}'
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

---

### Required GitHub Secrets

Document in `README.md`:

```markdown
## Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `DEPLOY_HOST` | Production server IP or hostname |
| `DEPLOY_USER` | SSH username |
| `DEPLOY_SSH_KEY` | Private SSH key for server access |
| `GHCR_TOKEN` | GitHub Container Registry token (PAT with packages:write) |
| `HF_TOKEN` | HuggingFace token for pyannote model download |
| `SLACK_WEBHOOK_URL` | (Optional) Slack webhook for failure notifications |
```

---

### `frontend/package.json` — add scripts

```json
{
  "scripts": {
    "dev":        "next dev",
    "build":      "next build",
    "start":      "next start",
    "lint":       "next lint",
    "typecheck":  "tsc --noEmit",
    "test":       "vitest run",
    "test:watch": "vitest"
  }
}
```

---

## Constraints
- Integration tests (marked `@pytest.mark.integration`) are excluded from CI with `-m "not integration"` — they require GPU and real models
- Docker image builds use `type=gha` GitHub Actions cache — dramatically speeds up repeat builds
- Deploy workflow requires `environment: production` — configure this in GitHub repository settings with required reviewers for safety
- `alembic upgrade head` runs in CI test job to ensure migrations are valid
- Deployment SSH command uses `-T` flag with `docker compose exec` to avoid TTY allocation in non-interactive CI
