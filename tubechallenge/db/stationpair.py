import itertools
import logging
from pydantic import ValidationError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tubechallenge.db.graph import get_many as get_graphs
from tubechallenge.db.station import get_many as get_stations
from tubechallenge.db.schemas import CreateStationPair
from tubechallenge.db.tables import StationPair

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create(
    stationpair_infos: list[dict], session: Session
) -> list[StationPair] | None:
    """Create new station pair records.

    Args:
        stationpair_infos (list[dict]): data required to create station pair
          records.
        session (Session): database session.

    Returns:
        list of created station pair records.
    """
    # Get IDs for graphs to associate with station pairs
    graph_ids = [
        stationpair_info["graph_id"] for stationpair_info in stationpair_infos
    ]
    db_graph_ids = {g.id for g in get_graphs(session, graph_ids=graph_ids)}

    # Get map between TfL and database IDs for stations
    station_map = {}
    for db_graph_id in db_graph_ids:
        station_map[db_graph_id] = {
            stn.station_id: stn.id for stn in get_stations(
                graph_id=db_graph_id, session=session, is_tube=True
            )
        }

    # Validate station pair dictionary and create records
    station_pairs = []
    for stationpair_info in stationpair_infos:
        try:
            # Convert TfL station ID to database station ID
            stationpair_data = stationpair_info.copy()
            for stn in ["origin_station_id", "destination_station_id"]:
                station_id = station_map.get(
                    stationpair_info["graph_id"], {}
                ).get(stationpair_info[stn])
                if station_id is None:
                    logger.error(f"Invalid {stn} {station_id}")
                    return None
                stationpair_data[stn] = station_id

            validated_stationpair = CreateStationPair(**stationpair_data)

            if validated_stationpair.graph_id not in db_graph_ids:
                logger.error(
                    f"Invalid graph ID {validated_stationpair.graph_id}"
                )
                return None

            station_pairs.append(StationPair(**stationpair_data))

        except ValidationError as err:
            logger.error(
                f"Validation failed for station pair {stationpair_info}: {err}"
            )
            return None

    # Commit to database
    try:
        session.add_all(station_pairs)
        session.commit()
    except SQLAlchemyError as err:
        session.rollback()
        logger.error(f"Database error: {err}")
        return None

    for station_pair in station_pairs:
        session.refresh(station_pair)
        logger.info(f"Station pair record created: {station_pair.id}")

    return station_pairs


def get_one(
    graph_id: int,
    origin_station_id: int,
    destination_station_id: int,
    session: Session,
) -> StationPair:
    """Get station pair record related to a particular graph record.

    Args:
        graph_id (int): ID of related graph record.
        origin_station_id (int): database ID of origin station.
        destination_station_id (int): database ID of destination station.
        session (Session): database session.

    Returns:
        requested station pair record.
    """
    return (
        session.query(StationPair)
        .filter_by(
            graph_id=graph_id,
            origin_station_id=origin_station_id,
            destination_station_id=destination_station_id
        ).first()
    )


def get_many(
        graph_id: int,
        session: Session,
        station_ids: list[int] | None = None,
        limit: int = 0,
        offset: int = 0,
) -> list[StationPair]:
    """Get all station pair records related to a particualr graph record.

    Args:
        graph_id (int): ID of related graph record.
        session (Session): database session.
        station_ids (list[int]): list of station database IDs.
        limit (int): maximum number of station pair records to retrieve.
        offset (int): index of first station pair record to retrieve.

    Returns:
        list of station pair records ordered by ID.
    """
    query = session.query(StationPair).filter_by(graph_id=graph_id)

    # Filter by station IDs if provided
    if station_ids:
        query = query.filter(
            StationPair.origin_station_id.in_(station_ids),
            StationPair.destination_station_id.in_(station_ids),
        )

    query = query.order_by(StationPair.id)  # order by station pair ID

    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return query.all()
