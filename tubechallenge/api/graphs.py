from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from tubechallenge.db import graph
from tubechallenge.db.db import get_session
from tubechallenge.db.enums import StatusFlag
from tubechallenge.db.tasks import fill_db

router = APIRouter(tags=["graphs"])


@router.put("/graphs")
def create_graph(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    rebuild: bool = False,
) -> dict:
    """Create graph record. Currently, only one graph record can exist. Unless
    rebuild flag is set, attempting to build a graph when one exists will
    result in a conflict.

    Args:
        background_tasks (BackgroundTasks): allows for tasks to be run after
          returning a response.
        session (Sesson): database session.
        rebuild (bool): flag to indicate whether database should be rebuilt.

    Returns:
        created graph record.
    """
    result = graph.create(session=session, rebuild=rebuild)

    if result["status"] == StatusFlag.PENDING.value:
        if result.get("state") == "conflict":
            raise HTTPException(
                status_code=409, detail="Database build already in progress."
            )
        else:
            background_tasks.add_task(fill_db, result["graph_id"])

            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={**result, "message": "Database build started."},
            )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={**result, "message": "Database already exists."},
    )


@router.get("/graphs")
def get_graphs(
    graph_ids: list[int] = Query(default_factory=list),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session)
) -> list[dict]:
    """Get all graph records from database.

    Args:
        graph_ids (list[int]): list of graph IDs to retrieve.
        limit (int): maximum number of graphs records to retrieve.
        offset (int): index of first graph record to retrieve.
        session (Session): database session.

    Returns:
        list of retrieved graphs.
    """
    db_graphs = graph.get_many(
        graph_ids=set(graph_ids) if graph_ids else None,
        limit=limit,
        offset=offset,
        session=session,
    )

    return [db_graph.to_dict() for db_graph in db_graphs]


@router.get("/graphs/{graph_id}")
def get_graph(graph_id: int, session: Session = Depends(get_session)) -> dict:
    """Get a single graph record from database.

    Args:
        graph_id (int): ID of graph record to retrieve.
        session (Session): database session.

    Returns:
        requested graph record.
    """
    db_graph = graph.get_one(graph_id=graph_id, session=session)
    if db_graph is None:
        raise HTTPException(
            status_code=404, detail=f"Graph {graph_id} does not exist."
        )

    return db_graph.to_dict()
