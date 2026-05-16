from collections import Counter
import logging
import pytest
import random
from typing import Callable

from sqlalchemy.orm import Session

from tubechallenge.db import station
from tubechallenge.db.constants import MAX_STATION_ID_LENGTH
from tubechallenge.db.tables import Graph, Station


def test_create_station(
    db_graphs: Callable,
    generate_station_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a station record in the database."""
    new_graph = db_graphs()[0]  # create graph that station will belong to

    station_infos = generate_station_infos(graph_ids=[new_graph.id])

    with caplog.at_level(logging.INFO):
        new_station = station.create(station_infos, db_session)
    assert "Tube station record created" in caplog.records[0].message

    assert isinstance(new_station, list)
    assert len(new_station) == 1
    assert new_station[0].id is not None
    assert new_station[0].station_id == station_infos[0]["station_id"]
    assert new_station[0].name == station_infos[0]["name"]
    assert new_station[0].latitude == station_infos[0]["latitude"]
    assert new_station[0].longitude == station_infos[0]["longitude"]
    assert new_station[0].is_open == True  # default value
    assert new_station[0].is_tube == station_infos[0]["is_tube"]
    assert new_station[0].graph_id == new_graph.id

    # Check graph is associated with station
    db_graph = db_session.get(Graph, new_graph.id)
    assert len(db_graph.stations) == 1
    assert db_graph.stations[0].id == new_station[0].id


def test_create_station__station_id_is_too_long(
    db_graphs: Callable,
    generate_station_infos: Callable,
    get_invalid_resource_id: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a station record in the database with a station ID that
    exceeds the maximum length. Logs an error and returns None.
    """
    new_graph = db_graphs()[0]  # create graph that station will belong to

    station_infos = generate_station_infos(graph_ids=[new_graph.id])
    station_infos[0]["station_id"] = get_invalid_resource_id(
        MAX_STATION_ID_LENGTH
    )

    with caplog.at_level(logging.ERROR):
        new_station = station.create(station_infos, db_session)
    assert "Validation failed for tube station" in caplog.records[0].message

    assert new_station is None


def test_create_station__graph_does_not_exist(
    generate_station_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a station record in the database with a graph ID that does
    not exist.
    """
    station_info = generate_station_infos(graph_ids=[1])

    with caplog.at_level(logging.ERROR):
        new_station = station.create(station_info, db_session)
    assert "Invalid graph ID" in caplog.records[0].message

    assert new_station is None


def test_get_station(
    db_graphs: Callable, db_stations: Callable, db_session: Session
):
    """Test: Get a single station record from the database."""
    db_graph = db_graphs()[0]  # create graph that station will belong to

    db_rec = db_stations(graph_ids=[db_graph.id])[0]

    station_rec = station.get_one(
        station_id=db_rec.station_id, graph_id=db_graph.id, session=db_session
    )

    assert station_rec.id == db_rec.id
    assert station_rec.station_id == db_rec.station_id
    assert station_rec.name == db_rec.name
    assert station_rec.latitude == db_rec.latitude
    assert station_rec.longitude == db_rec.longitude
    assert station_rec.is_open == db_rec.is_open
    assert station_rec.is_tube == db_rec.is_tube
    assert station_rec.graph_id == db_graph.id


def test_get_stations(
    db_graphs: Callable, db_stations: Callable, db_session: Session
):
    """Test: Get multiple station records from the database."""
    db_graph = db_graphs()[0]  # create graph that stations will belong to

    n_stations = 4
    db_recs = db_stations(graph_ids=[db_graph.id], n_stations=n_stations)
    db_recs = sorted(db_recs, key=lambda sttn: sttn.id)

    station_recs = station.get_many(graph_id=db_graph.id, session=db_session)
    station_recs = sorted(station_recs, key=lambda sttn: sttn.id)

    assert isinstance(station_recs, list)
    assert len(station_recs) == n_stations
    for station_rec, db_rec in zip(station_recs, db_recs):
        assert station_rec.id == db_rec.id
        assert station_rec.station_id == db_rec.station_id
        assert station_rec.name == db_rec.name
        assert station_rec.latitude == db_rec.latitude
        assert station_rec.longitude == db_rec.longitude
        assert station_rec.is_open == db_rec.is_open
        assert station_rec.is_tube == db_rec.is_tube
        assert station_rec.graph_id == db_graph.id


def test_get_stations__with_limit_and_offset(
    db_graphs: Callable, db_stations: Callable, db_session: Session
):
    """Test: Get a certain number of records (limit) from the database after a
    particular record (offset).
    """
    db_graph = db_graphs()[0]  # create graph that stations will belong to
    n_stations = 6
    db_recs = db_stations(graph_ids=[db_graph.id], n_stations=n_stations)
    db_recs = sorted(db_recs, key=lambda sttn: sttn.id)

    limit = 3
    offset = 2
    station_recs = station.get_many(
        graph_id=db_graph.id, limit=limit, offset=offset, session=db_session
    )  # this should return sorted by station ID

    assert isinstance(station_recs, list)
    assert len(station_recs) == limit
    for station_rec, db_rec in zip(
        station_recs, db_recs[offset: offset + limit + 1]
    ):
        assert station_rec.id == db_rec.id
        assert station_rec.station_id == db_rec.station_id
        assert station_rec.name == db_rec.name
        assert station_rec.latitude == db_rec.latitude
        assert station_rec.longitude == db_rec.longitude
        assert station_rec.is_open == db_rec.is_open
        assert station_rec.is_tube == db_rec.is_tube
        assert station_rec.graph_id == db_rec.graph_id


def test_get_stations__from_station_list(
    db_graphs: Callable, db_stations: Callable, db_session: Session
):
    """Test: Get multiple station records from the database that correspond to
    station IDs in a list.
    """
    db_graph = db_graphs()[0]  # create graph that stations will belong to
    n_stations = 12
    n_selected_stations = random.randint(2, n_stations - 1)

    db_recs = db_stations(graph_ids=[db_graph.id], n_stations=n_stations)
    db_recs = sorted(db_recs, key=lambda sttn: sttn.id)

    station_ids = [rec.station_id for rec in db_recs]
    selected_station_ids = random.sample(station_ids, n_selected_stations)

    station_recs = station.get_many(
        graph_id=db_graph.id,
        station_ids=selected_station_ids,
        session=db_session,
    )

    assert isinstance(station_recs, list)
    assert len(station_recs) == n_selected_stations
    selected_db_recs = [
        rec for rec in db_recs if rec.station_id in selected_station_ids
    ]
    assert Counter(selected_db_recs) == Counter(station_recs)


def test_get_stations__retrieve_tube_stations_only(
    db_graphs: Callable,
    generate_station_infos: Callable,
    db_resource: Callable,
    db_session: Session,
):
    """Test: Only retrieve tube stations from the database."""
    db_graph = db_graphs()[0]  # create graph that stations will belong to
    n_stations = 12
    n_tube_stations = random.randint(2, n_stations - 1)

    # Ensure that number of tube stations in database matches above number
    station_infos = generate_station_infos(
        graph_ids=[db_graph.id], n_stations=n_stations
    )
    station_types = [True] * n_tube_stations + [False] * (n_stations - n_tube_stations)
    random.shuffle(station_types)
    for station_info, station_type in zip(station_infos, station_types):
        station_info["is_tube"] = station_type

    db_recs = db_resource(station_infos, Station)  # create station records
    db_recs = sorted(db_recs, key=lambda sttn: sttn.id)

    # Retrieve tube stations from the database
    station_recs = station.get_many(
        graph_id=db_graph.id, is_tube=True, session=db_session
    )

    assert isinstance(station_recs, list)
    assert len(station_recs) == n_tube_stations
    tube_db_recs = [rec for rec in db_recs if rec.is_tube == True]
    assert tube_db_recs == station_recs
