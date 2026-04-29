import logging
from pydantic import ValidationError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tubechallenge.db.schemas import CreateLine
from tubechallenge.db.tables import Line

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create(line_infos: list[dict], session: Session) -> list[Line]:
    """Create new line records.

    Args:
        line_infos (list[dict]): data required to create line records.
        session (Session): database session.

    Returns:
        list of created line records.
    """
    # Validation input data for lines and create records
    lines = []
    for line_info in line_infos:
        try:
            CreateLine(**line_info)
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


def get_one(line_id: str, session: Session):
    """Get line record."""
    return session.query(Line).filter_by(line_id=line_id).first()


def get_many(session: Session, limit: int = 0, offset: int = 0):
    """Get all line records."""
    query = session.query(Line)
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return query.all()
