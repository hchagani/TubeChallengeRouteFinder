import logging
from pydantic import ValidationError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tubechallenge.db.graph import get_many as get_graphs
from tubechallenge.db.schemas import CreateConnection
from tubechallenge.db.tables import Connection, Line, Station

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create(
    connection_infos: list[dict], session: Session
) -> list[Connection] | None:
    """Create a new connection between two adjacent stations.

    Args:
        connection_infos (list[dict]): data required top create connections
          between adjacent stations.
        session (Session): database session.

    Returns:
        list of created records of connections between adjacent stations.
    """
    graph_ids = [
        connection_info["graph_id"] for connection_info in connection_infos
    ]
    db_graph_ids = {g.id for g in get_graphs(session, graph_ids=graph_ids)}

    connections = []
    for connection_info in connection_infos:
        graph_id = connection_info.get("graph_id", None)
        if graph_id not in db_graph_ids:
            logger.error(f"Invalid graph ID {graph_id}")
            return None

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


def get_one(
    graph_id: int,
    from_station_id: int,
    to_station_id: int,
    line_id: int,
    session: Session,
) -> Connection:
    """Get record of connection between adjacent stations.

    Args:
        graph_id (int): ID of related graph record.
        from_station_id (int): ID of origin station.
        to_station_id (int): ID of neighbouring station.
        line_id (int): ID of line connecting the stations.
        session (Session): dtabase session.

    Returns:
        requested connection record.
    """
    return (
        session.query(Connection)
        .filter_by(
            graph_id=graph_id,
            from_station_id=from_station_id,
            to_station_id=to_station_id,
            line_id=line_id
        ).first()
    )


def get_many(
    graph_id: int,
    session: Session,
    from_station_id: int | None = None,
    to_station_id: int | None = None,
    line_id: int | None = None,
    limit: int = 0,
    offset: int = 0,
) -> list[Connection]:
    """Get all records of connections between adjacent stations.

    Args:
        graph_id (int): ID of related graph record.
        session (Session): database session.
        from_station_id (int): ID of origin station.
        to_station_id (int): ID of neighbouring station.
        line_id (int): ID of line connecting the stations.
        limit (int): maximum number of connection records to retrieve.
        offset (int): index of first connection record to retrieve.

    Returns:
        list of connection records ordered by ID.
    """
    query = session.query(Connection).filter_by(graph_id=graph_id)

    if from_station_id is not None:
        query = query.filter_by(from_station_id=from_station_id)
    if to_station_id is not None:
        query = query.filter_by(to_station_id=to_station_id)
    if line_id is not None:
        query = query.filter_by(line_id=line_id)

    query = query.order_by(
        Connection.graph_id,
        Connection.from_station_id,
        Connection.to_station_id,
        Connection.line_id,
    )

    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return query.all()
