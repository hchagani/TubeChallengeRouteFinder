import logging
from pydantic import ValidationError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tubechallenge.db.schemas import CreateStation
from tubechallenge.db.tables import Station

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create(station_infos: list[dict], session: Session) -> list[dict]:
    """Create new station records.

    Args:
        station_infos (list[dict]): data required to create station records.
        session (Session): database session.

    Returns:
        list of created station records
    """
    # Validation station dictionary and create records
    stations = []
    for station_info in station_infos:
        try:
            CreateStation(**station_info)
            stations.append(Station(**station_info))
        except ValidationError as err:
            logger.error(
                f"Validation failed for tube station {station_info}: {err}"
            )
            return None

    # Commit to database
    try:
        session.add_all(stations)
        session.commit()
    except SQLAlchemyError as err:
        session.rollback()
        logger.error(f"Database error: {err}")
        return None

    for station in stations:
        session.refresh(station)
        logger.info(f"Tube station record created: {station.id}")

    return stations


def get_one(station_id: str, session: Session):
    """Get station record."""
    return session.query(Station).filter_by(station_id=station_id).first()


def get_many(
    session: Session,
    station_ids: list[str] | None = None,
    latitude_min: float | None = None,
    latitude_max: float | None = None,
    longitude_min: float | None = None,
    longitude_max: float | None = None,
    limit: int = 0,
    offset: int = 0,
):
    """Get all station records."""
    query = session.query(Station)

    # Filter by station IDs if provided
    if station_ids and len(station_ids) > 0:
        query = query.filter(Station.station_id.in_(station_ids))

    if latitude_min is not None:
        query = query.filter(Station.latitude >= latitude_min)
    if latitude_max is not None:
        query = query.filter(Station.latitude <= latitude_max)
    if longitude_min is not None:
        query = query.filter(Station.longitude >= longitude_min)
    if longitude_max is not None:
        query = query.filter(Station.longitude <= longitude_max)

    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return query.all()
