import logging
from pydantic import ValidationError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tubechallenge.db.schemas import CreateLine
from tubechallenge.db.tables import Line
from tubechallenge.db.utils import get_graph_ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create(line_infos: list[dict], session: Session) -> list[Line] | None:
    """Create new line records.

    Args:
        line_infos (list[dict]): data required to create line records.
        session (Session): database session.

    Returns:
        list of created line records.
    """
    db_graph_ids = get_graph_ids(line_infos, session)

    # Validate input data for lines and create records
    lines = []
    for line_info in line_infos:
        try:
            validated_line = CreateLine(**line_info)

            if validated_line.graph_id not in db_graph_ids:
                logger.error(f"Invalid graph ID {validated_line.graph_id}")
                return None

            lines.append(Line(**line_info))

        except ValidationError as err:
            logger.error(f"Validation failed for tube line {line_info}: {err}")
            return None

    # Commit to database
    try:
        session.add_all(lines)
        session.commit()
    except SQLAlchemyError as err:
        session.rollback()
        logger.error(f"Database error: {err}")
        return None

    for line in lines:
        session.refresh(line)
        logger.info(f"Tube line record created: {line.id}")

    return lines


def get_one(line_id: str, graph_id: int, session: Session) -> Line:
    """Get line record related to a particular graph record.

    Args:
        line_id (str): TfL's ID of line record to retrieve.
        graph_id (int): ID of related graph record.
        session (Session): database session.

    Returns:
        requested line record.
    """
    return (
        session.query(Line)
        .filter_by(line_id=line_id, graph_id=graph_id)
        .first()
    )


def get_many(
    graph_id: int, session: Session, limit: int = 0, offset: int = 0
) -> list[Line]:
    """Get all line records related to a particular graph record.

    Args:
        graph_id (int): ID of related graph record.
        session (Session): database session.
        limit (int): maximum number of line records to retrieve.
        offset (int): index of first line record to retrieve.

    Returns:
        list of line records ordered by ID.
    """
    query = session.query(Line).filter_by(graph_id=graph_id).order_by(Line.id)
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return query.all()
