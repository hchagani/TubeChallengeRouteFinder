import logging
from pydantic import ValidationError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tubechallenge.db.graph import get_many as get_graphs
from tubechallenge.db.schemas import CreateStation
from tubechallenge.db.tables import Station

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create(station_infos: list[dict], session: Session) -> list[Station] | None:
    """Create new station records.

    Args:
        station_infos (list[dict]): data required to create station records.
        session (Session): database session.

    Returns:
        list of created station records
    """
    graph_ids = {station_info["graph_id"] for station_info in station_infos}
    db_graph_ids = {g.id for g in get_graphs(session, graph_ids=graph_ids)}

    # Validate station dictionary and create records
    stations = []
    for station_info in station_infos:
        try:
            validated_station = CreateStation(**station_info)

            if validated_station.graph_id not in db_graph_ids:
                logger.error(f"Invalid graph ID {validated_station.graph_id}")
                return None

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


def get_one(station_id: str, graph_id: int, session: Session):
    """Get station record related to a particular graph record.

    Args:
        station_id (str): TfL's ID of station record to retrieve.
        graph_id (int): ID of related graph record.
        session (Session): database session.

    Returns:
        requested station record.
    """
    return (
        session.query(Station)
        .filter_by(station_id=station_id, graph_id=graph_id)
        .first()
    )


def get_many(
    graph_id: int,
    session: Session,
    station_ids: list[str] | None = None,
    latitude_min: float | None = None,
    latitude_max: float | None = None,
    longitude_min: float | None = None,
    longitude_max: float | None = None,
    limit: int = 0,
    offset: int = 0,
):
    """Get all station records related to a particular graph record.

    Args:
        graph_id (int): ID of related graph record.
        session (Session): database session.
        station_ids (list[str]): list of station IDs to retrieve.
        latitude_min (float): station's minimum latitude coordinate.
        latitude_max (float): station's maximum latitude coordinate.
        longitude_min (float): station's minimum longitude coordinate.
        longitude_max (float): station's maximum longitude coordinate.
        limit (int): maximum number of station records to retrieve.
        offset (int): index of first station record to retrieve.

    Returns:
        list of station records ordered by ID.
    """
    query = session.query(Station).filter_by(graph_id=graph_id)

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

    query = query.order_by(Station.id)  # order by station ID

    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return query.all()
