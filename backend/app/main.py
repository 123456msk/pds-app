"""FastAPI application factory and router registration only."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import cases, health, predict, segment


def create_app() -> FastAPI:
    application = FastAPI(title="前列腺 MRI 智能分割诊断")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router, prefix="/api")
    application.include_router(cases.router, prefix="/api")
    application.include_router(segment.router, prefix="/api")
    application.include_router(predict.router, prefix="/api")
    return application


app = create_app()
