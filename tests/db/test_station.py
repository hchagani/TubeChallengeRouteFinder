from collections import Counter
import logging
import pytest
import random
from typing import Callable

from sqlalchemy.orm import Session

from tubechallenge.db import station
from tubechallenge.db.constants import MAX_STATION_ID_LENGTH
from tubechallenge.db.tables import Station


def test_create_station(
    generate_station_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a station record in the database."""
    station_infos = generate_station_infos()

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


def test_create_station__station_id_is_too_long(
    generate_station_infos: Callable,
    get_invalid_resource_id: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a station record in the database with a station ID that
    exceeds the maximum length. Logs an error and returns None.
    """
    station_infos = generate_station_infos()
    station_infos[0]["station_id"] = get_invalid_resource_id(
        MAX_STATION_ID_LENGTH
    )

    with caplog.at_level(logging.ERROR):
        new_station = station.create(station_infos, db_session)
    assert "Validation failed for tube station" in caplog.records[0].message

    assert new_station is None


def test_get_station(db_stations: Callable, db_session: Session):
    """Test: Get a single station record from the database."""
    db_rec = db_stations()[0]

    station_rec = station.get_one(db_rec.station_id, db_session)

    assert station_rec.id == db_rec.id
    assert station_rec.station_id == db_rec.station_id
    assert station_rec.name == db_rec.name
    assert station_rec.latitude == db_rec.latitude
    assert station_rec.longitude == db_rec.longitude
    assert station_rec.is_open == db_rec.is_open


def test_get_stations(db_stations: Callable, db_session: Session):
    """Test: Get multiple station records from the database."""
    n_stations = 4
    db_recs = db_stations(n_stations)

    station_recs = station.get_many(db_session)

    assert isinstance(station_recs, list)
    assert len(station_recs) == n_stations
    for station_rec, db_rec in zip(station_recs, db_recs):
        assert station_rec.id == db_rec.id
        assert station_rec.station_id == db_rec.station_id
        assert station_rec.name == db_rec.name
        assert station_rec.latitude == db_rec.latitude
        assert station_rec.longitude == db_rec.longitude
        assert station_rec.is_open == db_rec.is_open


def test_get_stations__with_limit_and_offset(
    db_stations: Callable, db_session: Session
):
    """Test: Get a certain number of records (limit) from the database after a
    particular record (offset).
    """
    n_stations = 6
    db_recs = db_stations(n_stations)

    limit = 3
    offset = 2
    station_recs = station.get_many(
        limit=limit, offset=offset, session=db_session
    )

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


def test_get_stations__from_station_list(
    db_stations: Callable, db_session: Session
):
    """Test: Get multiple station records from the database that correspond to
    station IDs in a list.
    """
    n_stations = 12
    n_selected_stations = random.randint(2, n_stations - 1)

    db_recs = db_stations(n_stations)

    station_ids = [rec.station_id for rec in db_recs]
    selected_station_ids = random.sample(station_ids, n_selected_stations)

    station_recs = station.get_many(
        station_ids=selected_station_ids, session=db_session
    )

    assert isinstance(station_recs, list)
    assert len(station_recs) == n_selected_stations
    selected_db_recs = [
        rec for rec in db_recs if rec.station_id in selected_station_ids
    ]
    assert Counter(selected_db_recs) == Counter(station_recs)
