# Prompt 01 — Project Scaffold & Monorepo Layout

## Goal
Create the complete folder structure and base configuration files for the Audio Intelligence Platform (AIP). Do not write any application logic yet — only scaffold, config files, and tooling.

## What to create

### Root level
```
audio-intelligence-platform/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docker-compose.prod.yml
├── README.md
```

### Backend scaffold
```
backend/
├── Dockerfile
├── pyproject.toml          ← use uv + pyproject.toml (NOT requirements.txt)
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/           ← empty, migrations go here
└── app/
    ├── __init__.py
    ├── main.py             ← empty FastAPI app for now
    ├── config.py           ← empty
    ├── database.py         ← empty
    ├── models/             ← empty __init__.py only
    ├── schemas/            ← empty __init__.py only
    ├── routers/            ← empty __init__.py only
    ├── services/           ← empty __init__.py only
    ├── workers/            ← empty __init__.py only
    └── websocket/          ← empty __init__.py only
```

### Frontend scaffold
```
frontend/
├── Dockerfile
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── postcss.config.mjs
└── src/
    ├── app/
    │   ├── layout.tsx      ← empty root layout
    │   └── page.tsx        ← empty home page
    ├── components/
    │   └── ui/             ← empty, shadcn goes here
    ├── hooks/              ← empty
    ├── lib/
    │   └── utils.ts        ← shadcn cn() utility only
    └── stores/             ← empty
```

### Nginx scaffold
```
nginx/
├── nginx.conf
└── ssl/                    ← empty, certs mounted here
```

## Specific file contents

### `.env.example`
Include every variable from Section 14 of the spec sheet. All values should be safe placeholder defaults (never real secrets). Add a comment above each group.

### `pyproject.toml`
Use `uv` as the package manager. Include ALL of these dependencies:
- `fastapi>=0.115`
- `uvicorn[standard]`
- `sqlalchemy>=2.0`
- `alembic`
- `asyncpg`
- `pydantic-settings`
- `celery[redis]`
- `redis`
- `minio`
- `faster-whisper`
- `pyannote.audio`
- `transformers`
- `torch` (CPU version for now — GPU handled via docker-compose override)
- `torchaudio`
- `ffmpeg-python`
- `structlog`
- `python-multipart`
- `aiofiles`

Dev dependencies:
- `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`

### `package.json`
Next.js 15, React 19, TypeScript. Include:
- `next@15`, `react@19`, `react-dom@19`
- `typescript`, `@types/react`, `@types/node`
- `tailwindcss@4`, `@tailwindcss/postcss`
- `@tanstack/react-query@5`
- `zustand`
- `react-dropzone`
- `recharts`
- `clsx`, `tailwind-merge`
- `lucide-react`
- `class-variance-authority`

### `next.config.ts`
- Enable `output: 'standalone'` for Docker
- Set `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` from env

### `tsconfig.json`
Strict mode. Path alias `@/*` → `./src/*`.

### `.gitignore`
Cover: Python (`__pycache__`, `.venv`, `*.pyc`), Node (`node_modules`, `.next`), env files (`.env`, `.env.local`), model weights (`models/`), Docker volumes.

### `alembic/env.py`
Wire up to `DATABASE_URL` from environment. Use async engine (`asyncpg`). Target metadata from `app.models`.

### `alembic.ini`
Set `script_location = alembic`. Leave `sqlalchemy.url` as `%(DATABASE_URL)s` (overridden in env.py).

## Constraints
- Do not write any business logic
- Do not install anything — just write the files
- All paths must exactly match the folder structure in Section 13 of the spec sheet
- Backend `Dockerfile`: base image `python:3.12-slim`, install `ffmpeg` via apt, copy pyproject.toml, run `uv sync`
- Frontend `Dockerfile`: multi-stage — `node:22-alpine` builder + runner stage, `output: standalone`
