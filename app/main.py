"""FastAPI application entry point.

Creates the CMDB API with all route handlers, initializes the database
on startup, and configures CORS middleware.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.api import ingest, devices, users, apps, ci, ask

# Import models so Base.metadata knows about all tables
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create database tables on startup, dispose engine on shutdown."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="AI-First CMDB",
    description="AI-powered Configuration Management Database for IT infrastructure",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — permissive for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers
app.include_router(ingest.router)
app.include_router(devices.router)
app.include_router(users.router)
app.include_router(apps.router)
app.include_router(ci.router)
app.include_router(ask.router)


@app.get("/", tags=["health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify the API is running."""
    return {"status": "healthy", "service": "AI-First CMDB"}
