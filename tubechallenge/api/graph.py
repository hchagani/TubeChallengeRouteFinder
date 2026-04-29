from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.orm import Session

from tubechallenge.db import graph
from tubechallenge.db.db import get_session
from tubechallenge.db.enums import StatusFlag
from tubechallenge.db.tasks import fill_db

router = APIRouter(tags=["graph"])


@router.put("/graph")
def create_graph(
    background_tasks: BackgroundTasks,
    response: Response,
    session: Session = Depends(get_session),
    rebuild: bool = False,
) -> dict:
    """Create database record in database if it does not exist. If rebuild flag
    is set, database will be rebuilt even if it exists. Attempting to build a
    database while one is already pending results in a conflict as this is not
    allowed.

    Args:
        rebuild (bool): flag to indicate whether database should be rebuilt if
          it already exists.
    """
    result = graph.create(session=session, rebuild=rebuild)

    if result["status"] == StatusFlag.PENDING.value:
        if result.get("state") == "conflict":
            response.status_code = status.HTTP_409_CONFLICT
            result["message"] = "Database build already in progress."
        else:
            background_tasks.add_task(fill_db)
            response.status_code = status.HTTP_202_ACCEPTED
            result["message"] = "Database build started."
    else:
        response.status_code = status.HTTP_200_OK
        result["message"] = "Database already exists."

    result["status"] = result["status"]  # convert from enum

    return result


@router.get("/graph")
def get_graph(response: Response, session: Session = Depends(get_session)):
    """Get database record from database."""
    db_graph = graph.get_one(session=session)

    if not db_graph:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {
            "id": None,
            "status": None,
            "message": "Graph does not exist yet.",
        }

    response.status_code = status.HTTP_200_OK
    return {"id": db_graph.id, "status": db_graph.status.value}
