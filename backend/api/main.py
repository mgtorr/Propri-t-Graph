"""
PropriétéGraph - Real Estate Intelligence Platform
FastAPI backend serving DVF, BAN, and cadastral data analysis.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from loguru import logger
import time

from api.config import settings
from api.database import init_db
from api.routers import analysis, ownership, opportunities, properties


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"DB init skipped (not available): {e}")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="PropriétéGraph API",
    description="""
## PropriétéGraph - Real Estate Intelligence Platform

Combines **Demandes de Valeurs Foncières (DVF)**, **Base Adresse Nationale (BAN)**,
and **cadastral data** from data.gouv.fr to provide deep real estate market intelligence.

### Features
- **Price Evolution** – Historical trends + predictive modeling per neighborhood
- **Speculation Detection** – Rapid flips, mass acquisitions, corporate patterns
- **Gentrification Tracking** – Multi-signal gentrification and displacement risk
- **Ownership Network** – Graph visualization of who owns what
- **First-Time Buyer Finder** – Scored opportunities within budget constraints

### Data Sources
- [DVF - data.gouv.fr](https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/)
- [Base Adresse Nationale](https://adresse.data.gouv.fr/)
- [Cadastre Etalab](https://cadastre.data.gouv.fr/)
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
    return response


# Routers
PREFIX = settings.API_PREFIX
app.include_router(analysis.router, prefix=PREFIX)
app.include_router(ownership.router, prefix=PREFIX)
app.include_router(opportunities.router, prefix=PREFIX)
app.include_router(properties.router, prefix=PREFIX)


@app.get("/", tags=["Health"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "data_sources": {
            "dvf": "Demandes de Valeurs Foncières (data.gouv.fr)",
            "ban": "Base Adresse Nationale (adresse.data.gouv.fr)",
            "cadastre": "Cadastre Etalab (cadastre.data.gouv.fr)",
        },
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
