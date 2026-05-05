from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import Base, engine
from app.api.jobs import router as jobs_router

# Create all tables on startup (fine for dev; use Alembic migrations in prod)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="JobFlow API",
    description="Background job processing with Celery + Redis",
    version="1.0.0",
)

# CORS — allow the React dev server and Nginx proxy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:80", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(jobs_router, prefix="/api")


@app.get("/health")
def health_check():
    """Used by Docker healthcheck and load balancers."""
    return {"status": "ok"}
