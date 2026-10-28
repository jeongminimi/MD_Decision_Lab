from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 — registers SQLAlchemy metadata
from .api.routes import router
from .api.olist_routes import router as olist_router
from .api.fashion_routes import router as fashion_router
from .modules.shortform import models as shortform_models  # noqa: F401 — registers module table
from .database import Base, SessionLocal, engine, ensure_schema_compatibility
from .services.seed import seed_demo_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility(engine)
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="MD Decision Lab API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(olist_router)
app.include_router(fashion_router)


@app.get("/")
def root():
    return {"name": "MD Decision Lab API", "docs": "/docs"}
