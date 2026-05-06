import logging
import pytest
import random
from typing import Callable

from sqlalchemy.orm import Session

from tubechallenge.db import connection
from tubechallenge.db.tables import Graph, Line, Station


def test_create_connection(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    generate_connection_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a record of a connection between adjacent stations in the
    database.
    """
    # Create graph, line and station records for connection
    new_graph = db_graphs()[0]
    new_line = db_lines(graph_ids=[new_graph.id])[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=2)
    new_station_ids = [new_station.id for new_station in new_stations]

    connection_infos = generate_connection_infos(
        graph_id=new_graph.id,
        line_ids=[new_line.id],
        station_ids=new_station_ids,
    )

    with caplog.at_level(logging.INFO):
        new_connection = connection.create(connection_infos, db_session)
    assert "Connection record created" in caplog.records[0].message

    assert isinstance(new_connection, list)
    assert len(new_connection) == 1
    assert new_connection[0].graph_id == new_graph.id
    assert new_connection[0].from_station_id != new_connection[0].to_station_id
    assert new_connection[0].from_station_id in new_station_ids
    assert new_connection[0].to_station_id in new_station_ids
    assert new_connection[0].line_id == new_line.id
    assert isinstance(new_connection[0].time, int)
    assert new_connection[0].time > 0
    assert isinstance(new_connection[0].interval, int)
    assert new_connection[0].interval > 0

    # Check graph is associated with connection
    db_graph = db_session.get(Graph, new_graph.id)
    assert len(db_graph.connections) == 1
    assert db_graph.connections[0].graph_id == new_connection[0].graph_id
    assert db_graph.connections[0].from_station_id == new_connection[0].from_station_id
    assert db_graph.connections[0].to_station_id == new_connection[0].to_station_id
    assert db_graph.connections[0].line_id == new_connection[0].line_id

    # Check line is associated with connection
    db_line = db_session.get(Line, new_line.id)
    assert len(db_line.connections) == 1
    assert db_line.connections[0].graph_id == new_connection[0].graph_id
    assert db_line.connections[0].from_station_id == new_connection[0].from_station_id
    assert db_line.connections[0].to_station_id == new_connection[0].to_station_id
    assert db_line.connections[0].line_id == new_connection[0].line_id

    # Check stations are associated with connection
    db_origin_station = db_session.get(
        Station, new_connection[0].from_station_id
    )
    assert len(db_origin_station.connections_from) == 1
    assert db_origin_station.connections_from[0].graph_id == new_connection[0].graph_id
    assert db_origin_station.connections_from[0].from_station_id == new_connection[0].from_station_id
    assert db_origin_station.connections_from[0].to_station_id == new_connection[0].to_station_id
    assert db_origin_station.connections_from[0].line_id == new_connection[0].line_id

    db_destination_station = db_session.get(
        Station, new_connection[0].to_station_id
    )
    assert len(db_destination_station.connections_to) == 1
    assert db_destination_station.connections_to[0].graph_id == new_connection[0].graph_id
    assert db_destination_station.connections_to[0].from_station_id == new_connection[0].from_station_id
    assert db_destination_station.connections_to[0].to_station_id == new_connection[0].to_station_id
    assert db_destination_station.connections_to[0].line_id == new_connection[0].line_id


def test_create_connection__time_is_of_invalid_data_type(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    generate_connection_infos: Callable,
    db_session: Callable,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a connection record in the database with a string for
    journey time. Logs and error and returns None.
    """
    # Create graph, line and station records for connection
    new_graph = db_graphs()[0]
    new_line = db_lines(graph_ids=[new_graph.id])[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=2)
    new_station_ids = [new_station.id for new_station in new_stations]

    connection_infos = generate_connection_infos(
        graph_id=new_graph.id,
        line_ids=[new_line.id],
        station_ids=new_station_ids,
    )
    connection_infos[0]["time"] = "two"

    with caplog.at_level(logging.ERROR):
        new_connection = connection.create(connection_infos, db_session)
    assert "Validation failed for connection" in caplog.records[0].message

    assert new_connection is None


def test_create_connection__line_does_not_exist(
    db_graphs: Callable,
    db_stations: Callable,
    generate_connection_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a connection record in the database for a line that does
    not have a record in the database. Logs an error and returns None.
    """
    # Create graph and station records to associate with connection
    new_graph = db_graphs()[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=2)
    new_station_ids = [new_station.id for new_station in new_stations]

    missing_line_id = 1
    connection_infos = generate_connection_infos(
        graph_id=new_graph.id,
        line_ids=[missing_line_id],
        station_ids=new_station_ids,
    )

    with caplog.at_level(logging.ERROR):
        new_connection = connection.create(connection_infos, db_session)
    assert f"Line {missing_line_id} does not exist" in caplog.records[0].message

    assert new_connection is None


def test_create_connection__origin_and_destination_stations_are_the_same(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    generate_connection_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a connection record in the database between the same
    stations. Logs an error and returns None.
    """
    # Create graph, line and station records for connection
    new_graph = db_graphs()[0]
    new_line = db_lines(graph_ids=[new_graph.id])[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=2)
    new_station_ids = [new_station.id for new_station in new_stations]

    connection_infos = generate_connection_infos(
        graph_id=new_graph.id,
        line_ids=[new_line.id],
        station_ids=new_station_ids,
    )
    connection_infos[0]["to_station_id"] = connection_infos[0]["from_station_id"]

    with caplog.at_level(logging.ERROR):
        new_connection = connection.create(connection_infos, db_session)
    assert "Connection between same stations is not possible" in caplog.records[0].message

    assert new_connection is None


def test_create_connection__origin_station_does_not_exist(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    generate_connection_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a connection record in the databases for an origin station
    that does not have a record in the database. Logs an error and returns
    None.
    """
    # Create graph, line and station records for connection
    new_graph = db_graphs()[0]
    new_line = db_lines(graph_ids=[new_graph.id])[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=2)
    new_station_ids = [new_station.id for new_station in new_stations]

    connection_infos = generate_connection_infos(
        graph_id=new_graph.id,
        line_ids=[new_line.id],
        station_ids=new_station_ids,
    )
    missing_station_id = random.choice(
        [i for i in range(1, 10) if i not in new_station_ids]
    )
    connection_infos[0]["from_station_id"] = missing_station_id

    with caplog.at_level(logging.ERROR):
        new_connection = connection.create(connection_infos, db_session)
    assert f"Station {missing_station_id} does not exist" in caplog.records[0].message

    assert new_connection is None


def test_create_connection__destination_station_does_not_exist(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    generate_connection_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a connection record in the databases for a destination
    station that does not have a record in the database. Logs an error and
    returns None.
    """
    # Create graph, line and station records for connection
    new_graph = db_graphs()[0]
    new_line = db_lines(graph_ids=[new_graph.id])[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=2)
    new_station_ids = [new_station.id for new_station in new_stations]

    connection_infos = generate_connection_infos(
        graph_id=new_graph.id,
        line_ids=[new_line.id],
        station_ids=new_station_ids,
    )
    missing_station_id = random.choice(
        [i for i in range(1, 10) if i not in new_station_ids]
    )
    connection_infos[0]["to_station_id"] = missing_station_id

    with caplog.at_level(logging.ERROR):
        new_connection = connection.create(connection_infos, db_session)
    assert f"Station {missing_station_id} does not exist" in caplog.records[0].message

    assert new_connection is None


def test_get_connection(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    db_connections: Callable,
    db_session: Session,
):
    """Test: Get a single connection record from the database."""
    # Create graph, line and station records for connection
    new_graph = db_graphs()[0]
    new_line = db_lines(graph_ids=[new_graph.id])[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=2)
    new_station_ids = [new_station.id for new_station in new_stations]

    db_rec = db_connections(
        graph_id=new_graph.id,
        line_ids=[new_line.id],
        station_ids=new_station_ids,
    )[0]

    connection_rec = connection.get_one(
        graph_id=db_rec.graph_id,
        from_station_id=db_rec.from_station_id,
        to_station_id=db_rec.to_station_id,
        line_id=db_rec.line_id,
        session=db_session,
    )

    assert connection_rec.graph_id == db_rec.graph_id
    assert connection_rec.from_station_id == db_rec.from_station_id
    assert connection_rec.to_station_id == db_rec.to_station_id
    assert connection_rec.line_id == db_rec.line_id
    assert connection_rec.time == db_rec.time
    assert connection_rec.interval == db_rec.interval


def test_get_connections(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    db_connections: Callable,
    db_session: Session,
):
    """Test: Get multiple connection records from the database."""
    # Create graph, line and station records for connections
    new_graph = db_graphs()[0]
    n_lines = 3
    n_stations = 12
    new_lines = db_lines(graph_ids=[new_graph.id], n_lines=n_lines)
    new_line_ids = [new_line.id for new_line in new_lines]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=n_stations)
    new_station_ids = [new_station.id for new_station in new_stations]

    # Create new connections
    n_connections = (n_lines * (n_stations - 1)) // 2
    db_recs = db_connections(
        graph_id=new_graph.id,
        line_ids=new_line_ids,
        station_ids=new_station_ids,
        n_connections=n_connections,
    )
    db_recs = sorted(
        db_recs,
        key=lambda conn: (
            conn.graph_id,
            conn.from_station_id,
            conn.to_station_id,
            conn.line_id,
        ),
    )

    connection_recs = connection.get_many(
        graph_id=new_graph.id, session=db_session
    )
    connection_recs = sorted(
        connection_recs,
        key=lambda conn: (
            conn.graph_id,
            conn.from_station_id,
            conn.to_station_id,
            conn.line_id,
        ),
    )

    assert isinstance(connection_recs, list)
    assert len(connection_recs) == n_connections
    for connection_rec, db_rec in zip(connection_recs, db_recs):
        assert connection_rec.graph_id == db_rec.graph_id
        assert connection_rec.from_station_id == db_rec.from_station_id
        assert connection_rec.to_station_id == db_rec.to_station_id
        assert connection_rec.line_id == db_rec.line_id
        assert connection_rec.time == db_rec.time
        assert connection_rec.interval == db_rec.interval


def test_get_connections__with_origin_and_destination_station_and_line_ids(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    db_connections: Callable,
    db_session: Session,
):
    """Test: Get multiple connection records that correspond to supplied IDs
    for the origin and destination stations, and line.
    """
    # Create graph, line and station records for connections
    new_graph = db_graphs()[0]
    n_lines = 3
    n_stations = 12
    new_lines = db_lines(graph_ids=[new_graph.id], n_lines=n_lines)
    new_line_ids = [new_line.id for new_line in new_lines]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=n_stations)
    new_station_ids = [new_station.id for new_station in new_stations]

    # Extract last line ID and make it a connect two random stations
    # This is the connection that will be queried
    stub_line_id = new_line_ids.pop()
    db_rec = db_connections(
        graph_id=new_graph.id,
        line_ids=[stub_line_id],
        station_ids=new_station_ids
    )[0]

    # Connect up remaining lines
    db_connections(
        graph_id=new_graph.id,
        line_ids=new_line_ids,
        station_ids=new_station_ids,
        n_connections=(((n_lines - 1) * (n_stations - 1)) // 2),
    )

    connection_recs = connection.get_many(
        graph_id=new_graph.id,
        from_station_id=db_rec.from_station_id,
        to_station_id=db_rec.to_station_id,
        line_id=stub_line_id,
        session=db_session,
    )

    assert isinstance(connection_recs, list)
    assert len(connection_recs) == 1  # only one connection should satisfy query
    assert connection_recs[0].graph_id == db_rec.graph_id
    assert connection_recs[0].from_station_id == db_rec.from_station_id
    assert connection_recs[0].to_station_id == db_rec.to_station_id
    assert connection_recs[0].line_id == db_rec.line_id
    assert connection_recs[0].time == db_rec.time
    assert connection_recs[0].interval == db_rec.interval


def test_get_connections__with_limit_and_offset(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    db_connections: Callable,
    db_session: Session,
):
    """Test: Get a certain number of records (limit) from the database after a
    particular record (offset).
    """
    # Create graph, line and station records for connections
    new_graph = db_graphs()[0]
    n_lines = 3
    n_stations = 12
    new_lines = db_lines(graph_ids=[new_graph.id], n_lines=n_lines)
    new_line_ids = [new_line.id for new_line in new_lines]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=n_stations)
    new_station_ids = [new_station.id for new_station in new_stations]

    # Create new connections
    n_connections = (n_lines * (n_stations - 1)) // 2
    db_recs = db_connections(
        graph_id=new_graph.id,
        line_ids=new_line_ids,
        station_ids=new_station_ids,
        n_connections=n_connections,
    )
    db_recs = sorted(
        db_recs,
        key=lambda conn: (
            conn.graph_id,
            conn.from_station_id,
            conn.to_station_id,
            conn.line_id,
        ),
    )

    limit = 3
    offset = 2
    connection_recs = connection.get_many(
        graph_id=new_graph.id, limit=limit, offset=offset, session=db_session
    )  # this should return a sorted list

    assert isinstance(connection_recs, list)
    assert len(connection_recs) == limit
    for connection_rec, db_rec in zip(
        connection_recs, db_recs[offset: offset + limit + 1]
    ):
        assert connection_rec.graph_id == db_rec.graph_id
        assert connection_rec.from_station_id == db_rec.from_station_id
        assert connection_rec.to_station_id == db_rec.to_station_id
        assert connection_rec.line_id == db_rec.line_id
        assert connection_rec.time == db_rec.time
        assert connection_rec.interval == db_rec.interval
