from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import health, items, saved
from app.config import get_settings
from app.services.errors import ServiceError


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Muse API",
        description="Find an item, compare its price across retailers, discover more like it.",
        version="0.2.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(items.router)
    api.include_router(saved.router)
    app.include_router(api)

    # Locally stored uploads (development; production uses Supabase Storage).
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
    return app


app = create_app()
