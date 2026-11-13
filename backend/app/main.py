from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.access import DocumentNotFound, PermissionDenied
from app.config import Settings
from app.db import Base, make_engine, make_sessionmaker
from app.routers import auth, documents
from app.security import SessionSigner
from app.seed import seed_demo_data

log = logging.getLogger("ajaia")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    engine = make_engine(settings.database_url)
    session_factory = make_sessionmaker(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        Base.metadata.create_all(engine)
        if settings.seed_demo_users:
            with session_factory() as db:
                seed_demo_data(db, with_sample_content=settings.seed_sample_content)
        yield
        engine.dispose()

    app = FastAPI(title="Ajaia Docs", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.settings = settings
    app.state.sessionmaker = session_factory
    app.state.signer = SessionSigner(settings.secret_key, settings.session_max_age_seconds)

    @app.exception_handler(DocumentNotFound)
    async def _not_found(_req: Request, _exc: DocumentNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Document not found"})

    @app.exception_handler(PermissionDenied)
    async def _forbidden(_req: Request, _exc: PermissionDenied) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": "You don't have permission to do that"})

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.include_router(auth.router)
    app.include_router(documents.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.static_dir and Path(settings.static_dir).is_dir():
        _mount_spa(app, Path(settings.static_dir))

    return app


def _mount_spa(app: FastAPI, static_dir: Path) -> None:
    index = static_dir / "index.html"
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    def spa(full_path: str) -> FileResponse | JSONResponse:
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = (static_dir / full_path).resolve()
        if full_path and candidate.is_file() and static_dir.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)
