from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, stores
from app.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Muse API",
        description="AI stylist: curate a coherent collection from one inspiration item.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(stores.router)
    app.include_router(api)
    return app


app = create_app()
