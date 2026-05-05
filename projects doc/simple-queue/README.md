# JobFlow — Three-Tier Background Job App

A production-ready reference project for DevOps learning.  
Covers: **Frontend → Nginx → FastAPI → PostgreSQL + Redis (cache) + Celery (queue)**

---

## Architecture

```
Browser
  │
  ▼
Nginx :80          ← reverse proxy (routes traffic)
  ├── /api/*  →  FastAPI :8000   ← REST API
  └──  /*    →  React :3000      ← SPA frontend

FastAPI
  ├── PostgreSQL :5432  ← persistent job storage
  ├── Redis :6379/0     ← cache (job stats, cache-aside pattern)
  └── Redis :6379/1     ← Celery broker (task queue)

Celery Worker
  ├── Reads tasks from Redis :6379/1
  ├── Writes results to Redis :6379/2
  └── Updates job status in PostgreSQL

Flower :5555  ← Celery monitoring UI
```

### Why each component?

| Component    | Role                                                         |
|--------------|--------------------------------------------------------------|
| React        | User submits jobs, polls for status updates                 |
| Nginx        | Single entry point, routes API vs frontend traffic          |
| FastAPI      | REST API, pushes tasks to queue, reads/writes DB            |
| PostgreSQL   | Durable job history (survives restarts)                     |
| Redis db0    | Cache — job stats cached for 300s (cache-aside pattern)     |
| Redis db1    | Celery broker — task messages live here                     |
| Redis db2    | Celery result backend — task results stored here            |
| Celery       | Background worker — processes jobs asynchronously           |
| Flower       | Web UI to monitor Celery queues and workers                 |

---

## Quick Start

```bash
# Clone and run everything
git clone <repo>
cd jobflow
docker-compose up --build
```

| Service       | URL                          |
|---------------|------------------------------|
| App (via Nginx)| http://localhost             |
| Frontend direct| http://localhost:3000        |
| API docs       | http://localhost:8000/docs   |
| Celery Flower  | http://localhost:5555        |
| PostgreSQL     | localhost:5432               |
| Redis          | localhost:6379               |

---

## Project Structure

```
jobflow/
├── docker-compose.yml          # orchestrates all 7 services
├── nginx/
│   └── nginx.conf              # reverse proxy rules
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI app entry point
│       ├── core/
│       │   ├── config.py       # settings from env vars
│       │   ├── database.py     # SQLAlchemy engine + session
│       │   └── redis_client.py # Redis connection
│       ├── models/
│       │   └── job.py          # Job SQLAlchemy model
│       ├── services/
│       │   └── job_service.py  # business logic + cache-aside
│       ├── api/
│       │   └── jobs.py         # FastAPI router (endpoints)
│       └── workers/
│           ├── celery_app.py   # Celery instance config
│           └── tasks.py        # actual background task code
│
└── frontend/
    ├── Dockerfile              # multi-stage build
    ├── nginx.conf              # SPA serving
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx            # React entry point
        ├── App.jsx             # main dashboard component
        ├── styles.css
        ├── api/jobs.js         # axios API client
        └── hooks/useJobs.js    # polling + state management
```

---

## Key Patterns to Learn From

### 1. Cache-Aside Pattern (Redis)
```python
# In job_service.py → get_stats()
cached = redis_client.get(STATS_CACHE_KEY)
if cached:
    return StatsRead(**json.loads(cached))   # cache HIT

# cache MISS → query DB → write back
stats = query_database()
redis_client.setex(STATS_CACHE_KEY, TTL, json.dumps(stats))
return stats
```

### 2. Task Queue Pattern (Celery + Redis)
```python
# API submits a job (non-blocking, returns immediately)
process_job.delay(str(job.id), job.job_type)

# Worker picks it up from Redis queue and runs it
@celery_app.task(bind=True)
def process_job(self, job_id, job_type):
    # runs in separate process
```

### 3. Nginx Reverse Proxy Routing
```nginx
location /api/ { proxy_pass http://backend; }  # API calls
location /     { proxy_pass http://frontend; } # SPA
```

### 4. Environment-Based Config
All secrets/URLs come from environment variables (docker-compose.yml injects them).
Never hardcode connection strings in code.

---

## CI/CD Pipeline (Next Step)

When you're ready, add `.github/workflows/deploy.yml`:

```yaml
# Suggested stages:
# 1. Lint & test (pytest, eslint)
# 2. Build Docker images
# 3. Push to ECR (AWS)
# 4. Deploy to EC2/ECS with docker-compose pull + up
```

---

## Useful Commands

```bash
# View logs of a specific service
docker-compose logs -f celery_worker

# Scale workers (run 3 Celery workers)
docker-compose up --scale celery_worker=3

# Shell into backend
docker-compose exec backend bash

# Check Redis keys
docker-compose exec redis redis-cli -n 0 keys "*"

# Check Celery queue length
docker-compose exec redis redis-cli -n 1 llen celery
```
