import logging
import pytest
from typing import Callable

from sqlalchemy.orm import Session

from tubechallenge.db import graph
from tubechallenge.db.enums import StatusFlag
from tubechallenge.db.tables import Graph, Station


def test_create_graph(db_session: Session, caplog: pytest.LogCaptureFixture):
    """Test: Create a database record in the database."""
    with caplog.at_level(logging.INFO):
        new_graph = graph.create(session=db_session)

    assert "Database record created" in caplog.records[0].message

    assert new_graph is not None
    assert isinstance(new_graph, dict)
    assert new_graph["graph_id"] is not None
    assert new_graph["status"] == StatusFlag.PENDING.value


def test_create_graph__graph_pending_reports_conflict(
    db_graph: Graph, db_session: Session
):
    """Test: Attempt to create a database record in the database when record
    exists with pending status. Should indicate that there is a conflict.
    """
    # Check graph in database has pending status
    assert db_graph.status == StatusFlag.PENDING
    original_date_created = db_graph.date_created
    original_last_updated = db_graph.last_updated

    result = graph.create(session=db_session)

    assert result is not None
    assert isinstance(result, dict)
    assert result["graph_id"] is not None
    assert result["status"] == StatusFlag.PENDING.value
    assert result["state"] == "conflict"

    # Check that the graph has not been replaced
    db_rec = list(db_session.query(Graph))
    assert len(db_rec) == 1  # there should only be one graph in the database
    assert db_rec[0].date_created == original_date_created
    assert db_rec[0].last_updated == original_last_updated
    assert db_rec[0].date_created == db_rec[0].last_updated
    assert db_rec[0].status == StatusFlag.PENDING


def test_create_graph__do_not_replace_completed_graph(
    db_graph: Graph, db_session: Session
):
    """Test: Attempt to create a database record in the database when record
    exists with completed status. Should return the existing completed record.
    """
    # Set graph status to completed in database record
    db_graph.status = StatusFlag.COMPLETED
    db_session.commit()
    db_session.refresh(db_graph)
    assert db_graph.status == StatusFlag.COMPLETED

    # Rebuild database record
    new_graph = graph.create(session=db_session)

    assert new_graph is not None
    assert isinstance(new_graph, dict)
    assert new_graph["graph_id"] is not None
    assert new_graph["status"] == StatusFlag.COMPLETED.value


def test_create_graph__rebuild_flag_replaces_graph(
    db_graph: Graph,
    db_stations: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Rebuilding database should replace previous database."""
    # Generate station record in database and check it is there
    db_station = db_stations()
    station_rec = db_session.query(Station).first()
    assert station_rec is not None

    # Set graph status to completed in database record
    db_graph.status = StatusFlag.COMPLETED
    db_session.commit()
    db_session.refresh(db_graph)
    assert db_graph.status == StatusFlag.COMPLETED
    original_date_created = db_graph.date_created
    original_last_updated = db_graph.last_updated

    # Rebuild database record
    with caplog.at_level(logging.INFO):
        new_graph = graph.create(session=db_session, rebuild=True)

    assert "Database record created" in caplog.records[0].message

    assert new_graph is not None
    assert isinstance(new_graph, dict)
    assert new_graph["graph_id"] is not None
    assert new_graph["status"] == StatusFlag.PENDING.value

    # Check that graph record has been replaced and the database tables have
    # been reset (i.e. no station record exists)
    new_graph_rec = list(db_session.query(Graph))
    new_station_rec = list(db_session.query(Station))

    assert len(new_graph_rec) == 1  # there should only be one graph
    assert new_graph_rec[0].id is not None
    assert new_graph_rec[0].date_created > original_date_created
    assert new_graph_rec[0].last_updated > original_last_updated
    assert new_graph_rec[0].date_created == new_graph_rec[0].last_updated
    assert new_graph_rec[0].status == StatusFlag.PENDING

    assert len(new_station_rec) == 0  # there should be no station records


def test_get_graph(db_graph: Graph, db_session: Session):
    """Test: Get graph record from database."""
    graph_rec = graph.get_one(db_session)

    assert graph_rec.id == db_graph.id
    assert graph_rec.status == db_graph.status


def test_update_graph(
    db_graph: Graph, db_session: Session, caplog: pytest.LogCaptureFixture
):
    """Test: Update graph record with new status."""
    # Check graph in database has pending status
    assert db_graph.status == StatusFlag.PENDING
    original_date_created = db_graph.date_created
    original_last_updated = db_graph.last_updated

    with caplog.at_level(logging.INFO):
        updated_graph = graph.update(
            status=StatusFlag.COMPLETED, session=db_session
        )

    assert "Database record updated" in caplog.records[0].message

    assert updated_graph is not None
    assert isinstance(updated_graph, dict)
    assert updated_graph["graph_id"] is not None
    assert updated_graph["status"] == StatusFlag.COMPLETED.value

    # Check that the graph has been updated not replaced
    db_rec = list(db_session.query(Graph))
    assert len(db_rec) == 1  # there should only be one graph in the database
    assert db_rec[0].date_created == original_date_created
    assert db_rec[0].last_updated > original_last_updated


def test_update_graph__graph_record_does_not_exist(
    db_session: Session, caplog: pytest.LogCaptureFixture
):
    """Test: Attempt to update a graph record that does not exist. Should log a
    message and return None.
    """
    with caplog.at_level(logging.INFO):
        updated_graph = graph.update(
            status=StatusFlag.COMPLETED, session=db_session
        )

    assert "Database record does not exist" in caplog.records[0].message
    assert updated_graph is None
