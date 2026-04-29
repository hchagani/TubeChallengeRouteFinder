from fastapi import FastAPI

from tubechallenge.api import graph
from tubechallenge.db import tables
from tubechallenge.db.db import engine

ROUTER_PREFIX = "/api/v1"

app = FastAPI(
    title="Tube Challenge Route Finder API",
    description="API for building database, journey matrices and solutions",
    version="0.1.0",
)

app.include_router(graph.router, prefix=ROUTER_PREFIX, tags=["graph"])


@app.on_event("startup")
def on_startup() -> None:
    tables.Base.metadata.create_all(bind=engine)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": app.title, "version": app.version}
