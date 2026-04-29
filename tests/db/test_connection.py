from itertools import product
import logging
import pytest
import random
from typing import Callable

from sqlalchemy.orm import Session

from tubechallenge.db import connection
from tubechallenge.db.tables import Connection, Line, Station


@pytest.fixture
def generate_connection_infos() -> Callable:
    def _generate_connection_infos(
            line_ids: list[int], station_ids: list[int], n_connections: int = 1
    ) -> list[dict]:
        """Generate data for records of connections between adjacent stations.
        Randomly select combinations of originating and destination stations,
        and lines connecting them, and assign random integer journey times.

        Args:
            line_ids (list[int]): list of line IDs to associate with
              connections.
            station_ids (list[int]): list of station IDs to choose from when
              assigning originating and destination stations.
            n_connections (int): number of connections.

        Returns:
            list of data requried to create records of connections between
              adjacent stations.
        """
        connection_infos = []

        # Get all possible combinations of stations and lines
        possible_combinations = [
            (
                from_station, to_station, line
            ) for from_station, to_station, line in product(
                station_ids, station_ids, line_ids
            ) if from_station != to_station
        ]

        # Number of connections cannot exceed number of possible combinations
        n_connections = min(n_connections, len(possible_combinations))

        selected_combinations = random.sample(
            possible_combinations, n_connections
        )

        for from_station_id, to_station_id, line_id in selected_combinations:
            connection_infos.append(
                {
                    "from_station_id": from_station_id,
                    "to_station_id": to_station_id,
                    "line_id": line_id,
                    "time": random.randint(1, 8),  # randomise journey times
                    "interval": random.randint(1, 10),  # randomise times between services
                }
            )

        return connection_infos

    return _generate_connection_infos


def test_create_connection(
    db_lines: Callable,
    db_stations: Callable,
    generate_connection_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test : Create a record of a connection between adjacent stations in the
    database.
    """
    # Create line and station records for connection
    new_line = db_lines()[0]
    new_stations = db_stations(n_stations=2)
    new_station_ids = [new_station.id for new_station in new_stations]

    connection_infos = generate_connection_infos(
        line_ids=[new_line.id], station_ids=new_station_ids
    )

    with caplog.at_level(logging.INFO):
        new_connection = connection.create(connection_infos, db_session)
    assert "Connection record created" in caplog.records[0].message

    assert isinstance(new_connection, list)
    assert len(new_connection) == 1
    assert new_connection[0].from_station_id != new_connection[0].to_station_id
    assert new_connection[0].from_station_id in new_station_ids
    assert new_connection[0].to_station_id in new_station_ids
    assert new_connection[0].line_id == new_line.id
    assert isinstance(new_connection[0].time, int)
    assert new_connection[0].time > 0
    assert isinstance(new_connection[0].interval, int)
    assert new_connection[0].interval > 0

    # Check line is associated with connection
    db_line = db_session.get(Line, new_line.id)
    assert len(db_line.connections) == 1
    assert db_line.connections[0].from_station_id == new_connection[0].from_station_id
    assert db_line.connections[0].to_station_id == new_connection[0].to_station_id
    assert db_line.connections[0].line_id == new_connection[0].line_id

    # Check stations are associated with connection
    db_origin_station = db_session.get(
        Station, new_connection[0].from_station_id
    )
    assert len(db_origin_station.connections_from) == 1
    assert db_origin_station.connections_from[0].from_station_id == new_connection[0].from_station_id
    assert db_origin_station.connections_from[0].to_station_id == new_connection[0].to_station_id
    assert db_origin_station.connections_from[0].line_id == new_connection[0].line_id

    db_destination_station = db_session.get(
        Station, new_connection[0].to_station_id
    )
    assert len(db_destination_station.connections_to) == 1
    assert db_destination_station.connections_to[0].from_station_id == new_connection[0].from_station_id
    assert db_destination_station.connections_to[0].to_station_id == new_connection[0].to_station_id
    assert db_destination_station.connections_to[0].line_id == new_connection[0].line_id
