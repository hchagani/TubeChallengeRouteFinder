from contextlib import asynccontextmanager

from fastapi import FastAPI

from tubechallenge.api import graphs
from tubechallenge.db import tables
from tubechallenge.db.db import engine

ROUTER_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    tables.Base.metadata.create_all(bind=engine)

    yield

    # Shutdown
    engine.dispose()


app = FastAPI(
    title="Tube Challenge Route Finder API",
    description="API for building database, journey matrices and solutions",
    version="0.1.0",
)

app.include_router(graphs.router, prefix=ROUTER_PREFIX, tags=["graphs"])


@app.get("/")
def root() -> dict[str, str]:
    return {"message": app.title, "version": app.version}
