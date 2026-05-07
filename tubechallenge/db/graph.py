import logging
from pydantic import ValidationError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tubechallenge.db.enums import StatusFlag
from tubechallenge.db.db import get_session
from tubechallenge.db.schemas import UpdateGraph
from tubechallenge.db.tables import Base, Graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_GRAPH_NAME = "default"


def create(session: Session, rebuild: bool = False) -> dict:
    """Create new graph record. This record contains the metadata for the
    database. There can only be one graph record.

    Args:
        session (Session): database session
        rebuild (bool): flag to indicate whether database should be rebuilt

    Returns:
        created graph record.
    """
    graphs = get_many(session=session, limit=1)
    graph = graphs[0] if graphs else None

    # Do not try to create a new database if it is being filled
    if graph and graph.status == StatusFlag.PENDING:
        return {
            "graph_id": graph.id,
            "name": graph.name,
            "status": graph.status.value,
            "state": "conflict"
        }
    # Do not create a new database if it exists unless instructed otherwise
    if graph and graph.status == StatusFlag.COMPLETED and not rebuild:
        return {
            "graph_id": graph.id,
            "name": graph.name,
            "status": graph.status.value,
        }

    # If we reach here, we must rebuild
    # Start with full reset
    if graph:  # remove graph and related data if it exists
        delete(graph.id, session)
    session.expunge_all()  # clear identity map

    try:
        graph = Graph(name=DEFAULT_GRAPH_NAME, status=StatusFlag.PENDING)
        session.add(graph)
        session.commit()
        session.refresh(graph)
        logger.info(f"Graph record created: {graph.id}")

    except SQLAlchemyError as err:
        session.rollback()
        logger.error(f"Database error: {err}")
        return None

    return {
        "graph_id": graph.id, "name": graph.name, "status": graph.status.value
    }


def get_one(graph_id: int, session: Session) -> Graph:
    """Get graph record.

    Args:
        graph_id (int): ID of graph record to retrieve.
        session (Session): database session.

    Returns:
        requested graph record.
    """
    return session.query(Graph).filter_by(id=graph_id).first()


def get_many(
    session: Session,
    graph_ids: set[int] | None = None,
    limit: int = 0,
    offset: int = 0,
) -> list[Graph]:
    """Get many graph records.

    Args:
        session (Session): database session.
        graph_ids (set[int]): IDs of graph records to extract from database.
        offset (int): index of first graph record to retrieve.
        limit (int): maximum number of graph records to retrieve.

    Returns:
        list of graph records ordered by ID.
    """
    query = session.query(Graph)

    if graph_ids is not None:
        query = query.filter(Graph.id.in_(graph_ids))

    query = query.order_by(Graph.id)

    if offset:
        query = query.offset(offset)

    if limit:
        query = query.limit(limit)

    return query.all()


def update(graph_id: int, graph_info: dict, session: Session) -> dict | None:
    """Update graph record.

    Args:
        graph_id (int): ID of graph record to update.
        graph_info (dict): data to update graph record.
        session (Session): database session.

    Returns:
        updated graph record.
    """
    db_graph = get_one(graph_id, session)
    if not db_graph:  # if graph record does not exist
        logger.info("Graph record does not exist: {graph_id}")
        return None

    # Verify data
    try:
        updated_graph = UpdateGraph(**graph_info)
    except ValidationError as err:
        logger.error(f"Validation failed for graph {graph_info}: {err}")
        return None

    # Update
    try:
        update_data = updated_graph.model_dump(
            exclude_unset=True, exclude_none=True
        )

        # Only write to database if there is something to update
        if update_data:
            for field, value in update_data.items():
                setattr(db_graph, field, value)

            session.commit()
            session.refresh(db_graph)
            logger.info(f"Graph record updated: {db_graph.id}")

        return {
            "graph_id": db_graph.id,
            "name": db_graph.name,
            "status": db_graph.status.value,
        }

    except SQLAlchemyError as err:
        session.rollback()
        logger.error(f"Database error: {err}")
        return None


def delete(graph_id: int, session: Session) -> bool:
    """Delete graph record. This should remove all related data.

    Args:
        graph_id (int): ID of graph record to delete.
        session (Session): database session.

    Returns:
        True if deleted, False if there was an issue.
    """
    graph = get_one(graph_id, session)

    if not graph:
        logger.info(f"Graph record does not exist: {graph_id}")
        return False

    try:
        session.delete(graph)
        session.commit()
        logger.info(f"Graph record deleted: {graph_id}")
        return True

    except SQLAlchemyError as err:
        session.rollback()
        logger.error(f"Database error: {err}")
        return False
