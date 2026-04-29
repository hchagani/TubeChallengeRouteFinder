import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tubechallenge.db.enums import StatusFlag
from tubechallenge.db.db import get_session
from tubechallenge.db.tables import Base, Graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create(session: Session, rebuild: bool = False) -> dict:
    """Create new graph record. This record contains the metadata for the
    database. There can only be one graph record.

    Args:
        session (Session): database session
        rebuild (bool): flag to indicate whether database should be rebuilt

    Returns:
        created graph record.
    """
    def delete_all_rows(session: Session):
        """Delete all rows in each table respecting foreign key order."""
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()

    graph = get_one(session=session)

    # Do not try to create a new database if it is being filled
    if graph and graph.status == StatusFlag.PENDING:
        return {
            "graph_id": graph.id,
            "status": graph.status.value,
            "state": "conflict"
        }
    # Do not create a new database if it exists unless instructed otherwise
    if graph and graph.status == StatusFlag.COMPLETED and not rebuild:
        return {"graph_id": graph.id, "status": graph.status.value}

    # If we reach here, we must rebuild
    # Start with full reset
    delete_all_rows(session)
    session.expunge_all()  # clear identity map

    try:
        graph = Graph(status=StatusFlag.PENDING)
        session.add(graph)
        session.commit()
        session.refresh(graph)
        logger.info(f"Database record created: {graph.id}")

    except SQLAlchemyError as err:
        session.rollback()
        logger.error(f"Database error: {err}")
        return None

    return {"graph_id": graph.id, "status": graph.status.value}


def get_one(session: Session) -> Graph:
    """Get graph record. There should only be one record."""
    return session.query(Graph).first()


def update(status: StatusFlag, session: Session) -> dict:
    """Update status of graph record. This status reflects whether database
    setup has been completed or has failed.

    Args:
        status (StatusFlag): status of database setup.
        session (Session): database session.
    """
    db_graph = get_one(session)

    if db_graph:
        try:
            db_graph.status = status
            session.commit()
            session.refresh(db_graph)
            logger.info(f"Database record updated: {db_graph.id}")
            return {"graph_id": db_graph.id, "status": db_graph.status.value}

        except SQLAlchemyError as err:
            session.rollback()
            logger.error(f"Database error: {err}")
            return None


    logger.info("Database record does not exist.")
    return None  # If graph record does not exist
