from collections import Counter
import logging
import pytest
import random
from typing import Callable

from sqlalchemy.orm import Session

from tubechallenge.db import stationpair
from tubechallenge.db.tables import Graph, Station


def test_create_stationpair(
    db_graphs: Callable,
    db_stations: Callable,
    generate_stationpair_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a station pair record in the database."""
    # Create graph and station records to create station pair
    new_graph = db_graphs()[0]
    new_stations = db_stations(
        graph_ids=[new_graph.id], n_stations=2, all_tube=True
    )
    station_ids = [stn.station_id for stn in new_stations]
    station_db_ids = [stn.id for stn in new_stations]

    stationpair_infos = generate_stationpair_infos(
        graph_id=new_graph.id, station_ids=station_ids
    )

    with caplog.at_level(logging.INFO):
        new_stationpair = stationpair.create(stationpair_infos, db_session)
    assert "Station pair record created" in caplog.records[0].message

    assert isinstance(new_stationpair, list)
    assert len(new_stationpair) == 1
    assert new_stationpair[0].id is not None
    new_origin_station_id = new_stationpair[0].origin_station_id
    new_destination_station_id = new_stationpair[0].destination_station_id
    assert new_origin_station_id in station_db_ids
    assert new_destination_station_id in station_db_ids
    assert new_origin_station_id != new_destination_station_id
    assert new_stationpair[0].graph_id == new_graph.id

    # Check graph is associated with station pair
    db_graph = db_session.get(Graph, new_graph.id)
    assert len(db_graph.station_pairs) == 1
    assert db_graph.station_pairs[0].id == new_stationpair[0].id

    # Check origin and destination stations are associated with station pair
    db_stations = db_session.query(Station).all()
    for db_station in db_stations:
        if len(db_station.route_origins) == 1:
            assert len(db_station.route_destinations) == 0
            assert db_station.route_origins[0].id == new_stationpair[0].id
            continue

        assert len(db_station.route_origins) == 0
        assert len(db_station.route_destinations) == 1
        assert db_station.route_destinations[0].id == new_stationpair[0].id


def test_create_stationpair__origin_and_destination_station_are_the_same(
    db_graphs: Callable,
    db_stations: Callable,
    generate_stationpair_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a station pair where the origin and destination station are
    the same. Logs an error and returns None.
    """
    # Create graph and station records to create station pair
    new_graph = db_graphs()[0]
    new_stations = db_stations(
        graph_ids=[new_graph.id], n_stations=2, all_tube=True
    )
    station_ids = [stn.station_id for stn in new_stations]

    stationpair_infos = generate_stationpair_infos(
        graph_id=new_graph.id, station_ids=station_ids
    )
    stationpair_infos[0]["destination_station_id"] = stationpair_infos[0]["origin_station_id"]

    with caplog.at_level(logging.ERROR):
        new_stationpair = stationpair.create(stationpair_infos, db_session)
    assert "Validation failed for station pair" in caplog.records[0].message

    assert new_stationpair is None


def test_create_stationpair__invalid_origin_station_id(
    db_graphs: Callable,
    db_stations: Callable,
    generate_stationpair_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a station pair with an invalid origin station ID. Logs an
    error and returns None.
    """
    # Create graph and station records to create station pair
    new_graph = db_graphs()[0]
    new_stations = db_stations(
        graph_ids=[new_graph.id], n_stations=2, all_tube=True
    )
    station_ids = [stn.station_id for stn in new_stations]

    stationpair_infos = generate_stationpair_infos(
        graph_id=new_graph.id, station_ids=station_ids
    )
    stationpair_infos[0]["origin_station_id"] = "invalid_id"

    with caplog.at_level(logging.ERROR):
        new_stationpair = stationpair.create(stationpair_infos, db_session)
    assert "Invalid origin_station_id" in caplog.records[0].message

    assert new_stationpair is None


def test_create_stationpair__invalid_destination_station_id(
    db_graphs: Callable,
    db_stations: Callable,
    generate_stationpair_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a station pair with an invalid destination station ID. Logs
    an error and returns None.
    """
    # Create graph and station records to create station pair
    new_graph = db_graphs()[0]
    new_stations = db_stations(
        graph_ids=[new_graph.id], n_stations=2, all_tube=True
    )
    station_ids = [stn.station_id for stn in new_stations]

    stationpair_infos = generate_stationpair_infos(
        graph_id=new_graph.id, station_ids=station_ids
    )
    stationpair_infos[0]["destination_station_id"] = "invalid_id"

    with caplog.at_level(logging.ERROR):
        new_stationpair = stationpair.create(stationpair_infos, db_session)
    assert "Invalid destination_station_id" in caplog.records[0].message

    assert new_stationpair is None


def test_get_stationpair(
    db_graphs: Callable,
    db_stations: Callable,
    db_stationpairs: Callable,
    db_session: Session,
):
    """Test: Get a single station pair record from the database."""
    # Create graph and station records to create station pair
    new_graph = db_graphs()[0]
    new_stations = db_stations(
        graph_ids=[new_graph.id], n_stations=2, all_tube=True
    )
    station_map = {stn.station_id: stn.id for stn in new_stations}

    db_rec = db_stationpairs(graph_id=new_graph.id, station_map=station_map)[0]
    origin_station_id = db_rec.origin_station_id
    destination_station_id = [
        stn.id for stn in new_stations if stn.id != origin_station_id
    ][0]

    stationpair_rec = stationpair.get_one(
        graph_id=new_graph.id,
        origin_station_id=origin_station_id,
        destination_station_id=destination_station_id,
        session=db_session,
    )

    assert stationpair_rec.id == db_rec.id
    assert stationpair_rec.origin_station_id == db_rec.origin_station_id
    assert stationpair_rec.destination_station_id == db_rec.destination_station_id
    assert stationpair_rec.graph_id == db_rec.graph_id
    assert stationpair_rec.date_created == db_rec.date_created
    assert stationpair_rec.last_updated == db_rec.last_updated

    # The inverted pair should not exist
    missing_stationpair_rec = stationpair.get_one(
        graph_id=new_graph.id,
        origin_station_id=destination_station_id,
        destination_station_id=origin_station_id,
        session=db_session,
    )
    assert missing_stationpair_rec is None


def test_get_stationpairs(
    db_graphs: Callable,
    db_stations: Callable,
    db_stationpairs: Callable,
    db_session: Session,
):
    """Test: Get multiple station pair records from the database."""
    # Create graph and station records to create station pair
    new_graph = db_graphs()[0]
    new_stations = db_stations(
        graph_ids=[new_graph.id], n_stations=6, all_tube=True
    )
    station_map = {stn.station_id: stn.id for stn in new_stations}

    n_pairs = 12
    db_recs = db_stationpairs(
        graph_id=new_graph.id, station_map=station_map, n_pairs=n_pairs
    )
    db_recs = sorted(db_recs, key=lambda stnpr: stnpr.id)

    stationpair_recs = stationpair.get_many(
        graph_id=new_graph.id, session=db_session
    )
    stationpair_recs = sorted(stationpair_recs, key=lambda stnpr: stnpr.id)

    assert isinstance(stationpair_recs, list)
    assert len(stationpair_recs) == n_pairs
    for stationpair_rec, db_rec in zip(stationpair_recs, db_recs):
        assert stationpair_rec.id == db_rec.id
        assert stationpair_rec.origin_station_id == db_rec.origin_station_id
        assert stationpair_rec.destination_station_id == db_rec.destination_station_id
        assert stationpair_rec.graph_id == db_rec.graph_id
        assert stationpair_rec.date_created == db_rec.date_created
        assert stationpair_rec.last_updated == db_rec.last_updated


def test_get_stationpairs__with_limit_and_offset(
    db_graphs: Callable,
    db_stations: Callable,
    db_stationpairs: Callable,
    db_session: Session,
):
    """Test: Get a certain number of records (limit) from the database after a
    particular record (offset).
    """
    # Create graph and station records to create station pair
    new_graph = db_graphs()[0]
    new_stations = db_stations(
        graph_ids=[new_graph.id], n_stations=6, all_tube=True
    )
    station_map = {stn.station_id: stn.id for stn in new_stations}

    n_pairs = 12
    db_recs = db_stationpairs(
        graph_id=new_graph.id, station_map=station_map, n_pairs=n_pairs
    )
    db_recs = sorted(db_recs, key=lambda stnpr: stnpr.id)

    limit = 3
    offset = 2
    stationpair_recs = stationpair.get_many(
        graph_id=new_graph.id, limit=limit, offset=offset, session=db_session
    )  # this should return sorted by station pair ID

    assert isinstance(stationpair_recs, list)
    assert len(stationpair_recs) == limit
    for stationpair_rec, db_rec in zip(
        stationpair_recs, db_recs[offset: offset + limit + 1]
    ):
        assert stationpair_rec.id == db_rec.id
        assert stationpair_rec.origin_station_id == db_rec.origin_station_id
        assert stationpair_rec.destination_station_id == db_rec.destination_station_id
        assert stationpair_rec.graph_id == db_rec.graph_id
        assert stationpair_rec.date_created == db_rec.date_created
        assert stationpair_rec.last_updated == db_rec.last_updated


def test_get_stationpairs__from_station_list(
    db_graphs: Callable,
    db_stations: Callable,
    db_stationpairs: Callable,
    db_session: Session,
):
    """Test: Get multiple station pair records from the database that correspond
    to station IDs on a list.
    """
    # Create graph and station records to create station pair
    new_graph = db_graphs()[0]
    n_stations = 6
    new_stations = db_stations(
        graph_ids=[new_graph.id], n_stations=n_stations, all_tube=True
    )
    station_map = {stn.station_id: stn.id for stn in new_stations}

    # Number of permutations = n! / (n - r)!, where n is number of stations and
    # r is number of stations in a pair, i.e. 2
    # This simplifies to 6 x 5 x (6 - 2)! / (6 - 2)! = 6 x 5
    n_pairs = n_stations * (n_stations - 1)
    db_recs = db_stationpairs(
        graph_id=new_graph.id, station_map=station_map, n_pairs=n_pairs
    )

    n_selected_stations = 4
    station_ids = random.sample(list(station_map.values()), n_selected_stations)
    selected_db_recs = [
        db_rec for db_rec in db_recs if db_rec.origin_station_id in station_ids and db_rec.destination_station_id in station_ids
    ]
    selected_db_recs = sorted(selected_db_recs, key=lambda stnpr: stnpr.id)
    # Permutations simplify to 4 x 3 (see above)
    n_selected_pairs = n_selected_stations * (n_selected_stations - 1)
    stationpair_recs = stationpair.get_many(
        graph_id=new_graph.id, station_ids=station_ids, session=db_session
    )  # this should return sorted by station pair ID

    assert isinstance(stationpair_recs, list)
    assert len(stationpair_recs) == n_selected_pairs
    assert Counter(selected_db_recs) == Counter(stationpair_recs)
