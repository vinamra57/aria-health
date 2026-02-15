import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import close_db, init_db
from app.routers import cases, stream
# Unnecessary for minimal flow (voice→text, text→NEMSIS only):
# from app.routers import gp_call, hospital

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Relay...")
    await init_db()
    logger.info("Database initialized")
    yield
    await close_db()
    logger.info("Relay shut down")


app = FastAPI(
    title="Relay",
    description="AI Emergency Response System - Automated ePCR for Paramedics",
    version="0.1.0",
    lifespan=lifespan,
)

# Page routes first so "/" is not shadowed
@app.get("/", response_class=FileResponse)
async def serve_paramedic_ui():
    path = _STATIC_DIR / "index_enhanced.html"
    return FileResponse(path, media_type="text/html")


# Unnecessary for minimal flow: hospital UI
# @app.get("/hospital", response_class=FileResponse)
# async def serve_hospital_ui():
#     path = _STATIC_DIR / "hospital.html"
#     return FileResponse(path, media_type="text/html")

# API and static (directory must be str for StaticFiles)
app.include_router(stream.router)
app.include_router(cases.router)
# app.include_router(hospital.router)
# app.include_router(gp_call.router, prefix="/api")
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
