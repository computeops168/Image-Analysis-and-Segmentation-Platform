from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, auth, files, images, jobs
from app.config import (
    CORS_ORIGINS,
    FRONTEND_DIR,
    RATE_LIMIT_IMAGES_PER_MINUTE,
    RATE_LIMIT_JOBS_PER_MINUTE,
    RATE_LIMIT_LOGIN_PER_MINUTE,
)
from app.observability import RequestObservabilityMiddleware, render_metrics, setup_logging
from app.db.session import init_db
from app.rate_limit import RateLimitRule, RateLimiterMiddleware


setup_logging()
app = FastAPI(title="Image Analysis and Segmentation Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestObservabilityMiddleware)
app.add_middleware(
    RateLimiterMiddleware,
    rules=[
        RateLimitRule("POST", "/api/auth/login", RATE_LIMIT_LOGIN_PER_MINUTE),
        RateLimitRule("POST", "/api/images", RATE_LIMIT_IMAGES_PER_MINUTE),
        RateLimitRule("POST", "/api/upload", RATE_LIMIT_IMAGES_PER_MINUTE),
        RateLimitRule("POST", "/api/jobs", RATE_LIMIT_JOBS_PER_MINUTE),
    ],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    return render_metrics()


app.include_router(images.router)
app.include_router(files.router)
app.include_router(jobs.router)
app.include_router(admin.router)
app.include_router(auth.router)

if FRONTEND_DIR.exists():
    # Serve the static frontend from the backend for single-origin deployments.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
