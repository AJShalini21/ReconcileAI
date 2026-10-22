import tracemalloc

tracemalloc.start()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.database import check_database_connection

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.app_debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    connected, database_version = check_database_connection()
    return {
        "status": "ok",
        "service": settings.app_name,
        "database": "connected" if connected else "disconnected",
        "database_version": database_version[:120] if connected else database_version,
    }
