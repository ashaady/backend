from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    ACCESS_ALLOWED_ORIGINS,
    ACCESS_ALLOWED_ORIGIN_REGEX,
    ACCESS_CORS_ALLOW_CREDENTIALS,
)
from app.db import Base, engine
from app.routers import admin, auth, messages, system


allow_credentials = ACCESS_CORS_ALLOW_CREDENTIALS and "*" not in ACCESS_ALLOWED_ORIGINS

app = FastAPI(title="Access Control API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ACCESS_ALLOWED_ORIGINS or ["*"],
    allow_origin_regex=ACCESS_ALLOWED_ORIGIN_REGEX,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(system.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(messages.router)
