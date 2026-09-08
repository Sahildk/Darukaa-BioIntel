"""Main FastAPI application entrypoint."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.config import settings
from app.services.conversation_service import EnvironmentalChatService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes application-scoped reusable components on startup."""
    app.state.chat_service = EnvironmentalChatService()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Evidence-constrained environmental intelligence and decision-support system for biodiversity, land health, and restoration.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API router under configured prefix
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", tags=["System"])
def root():
    """Root redirect / information endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }
