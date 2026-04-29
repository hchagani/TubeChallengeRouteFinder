import logging
from pydantic import ValidationError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tubechallenge.db.schemas import CreateConnection
from tubechallenge.db.tables import Connection, Line, Station

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create(connection_infos: list[dict], session: Session) -> list[Connection]:
    """Create a new connection between two adjacent stations.

    Args:
        connection_infos (list[dict]): data required top create connections
          between adjacent stations.
        session (Session): database session.

    Returns:
        list of created records of connections between adjacent stations.
    """
    connections = []

    for connection_info in connection_infos:
        # Ensure record for line exists in database
        if session.get(Line, connection_info["line_id"]) == None:
            logger.error(f"Line {connection_info['line_id']} does not exist")
            return None

        # Ensure originating and destination stations are not the same
        origin_station_id = connection_info["from_station_id"]
        destination_station_id = connection_info["to_station_id"]
        if origin_station_id == destination_station_id:
            logger.error(
                f"Connection between same stations is not possible: origin station {origin_station_id}, destination station {destination_station_id}"
            )
            return None

        # Ensure records for stations exist in database
        for station_id in [
            connection_info["from_station_id"],
            connection_info["to_station_id"],
        ]:
            if session.get(Station, station_id) == None:
                logger.error(f"Station {station_id} does not exist")
                return None

        try:
            CreateConnection(**connection_info)
            connections.append(Connection(**connection_info))
        except ValidationError as err:
            logger.error(
                f"Validation failed for connection {connection_info}: {err}"
            )
            return None

    # Commit to database
    try:
        session.add_all(connections)
        session.commit()
    except SQLAlchemyError as err:
        session.rollback()
        logger.error(f"Database error: {err}")
        return None

    for connection in connections:
        session.refresh(connection)
        logger.info(
            f"Connection record created from {connection.from_station_id} to {connection.to_station_id}"
        )

    return connections


def get_one(connection_id: int, session: Session):
    """Get record of connection between adjacent stations."""
    return session.query(Connection).filter_by(id=connection_id).first()


def get_many(session: Session, limit: int = 0, offset: int = 0):
    """Get all records of connections between adjacent stations."""
    query = session.query(Connection)
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return query.all()
