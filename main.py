from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ACCESS_ALLOWED_ORIGINS
from app.db import Base, engine
from app.routers import admin, auth, system


app = FastAPI(title="Access Control API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ACCESS_ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(system.router)
app.include_router(auth.router)
app.include_router(admin.router)
