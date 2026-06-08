import logging
import pytest
import random
import re
from typing import Callable

from sqlalchemy.orm import Session

from tubechallenge.db import graph
from tubechallenge.db.constants import (
    DEFAULT_GRAPH_NAME,
    DEFAULT_MAX_RUN_DISTANCE,
    DEFAULT_SECONDS_PER_KM,
)
from tubechallenge.db.enums import StatusFlag
from tubechallenge.db.tables import (
    Branch,
    BranchStation,
    Connection,
    Graph,
    Line,
    Station,
)


def test_create_graph(db_session: Session, caplog: pytest.LogCaptureFixture):
    """Test: Create a database record in the database."""
    with caplog.at_level(logging.INFO):
        new_graph = graph.create(session=db_session)

    assert "Graph record created" in caplog.records[0].message

    assert new_graph is not None
    assert isinstance(new_graph, dict)
    assert new_graph["graph_id"] is not None
    assert new_graph["name"] == DEFAULT_GRAPH_NAME
    assert new_graph["status"] == StatusFlag.PENDING.value
    assert re.fullmatch(r"\d{2}:\d{2}", new_graph["run_pace"])
    minutes, seconds = map(int, new_graph["run_pace"].split(":"))
    assert DEFAULT_SECONDS_PER_KM == minutes * 60 + seconds
    assert new_graph["max_run_distance"] == DEFAULT_MAX_RUN_DISTANCE


def test_create_graph__graph_pending_reports_conflict(
    db_graphs: Callable, db_session: Session
):
    """Test: Attempt to create a database record in the database when record
    exists with pending status. Should indicate that there is a conflict.
    """
    # Check graph in database has pending status
    db_graph = db_graphs()[0]
    assert db_graph.status == StatusFlag.PENDING
    original_date_created = db_graph.date_created
    original_last_updated = db_graph.last_updated

    result = graph.create(session=db_session)

    assert result is not None
    assert isinstance(result, dict)
    assert result["graph_id"] is not None
    assert result["name"] == db_graph.name
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
    db_graphs: Callable, db_session: Session
):
    """Test: Attempt to create a database record in the database when record
    exists with completed status. Should return the existing completed record.
    """
    # Set graph status to completed in database record
    db_graph = db_graphs()[0]
    db_graph.status = StatusFlag.COMPLETED
    db_session.commit()
    db_session.refresh(db_graph)
    assert db_graph.status == StatusFlag.COMPLETED

    # Rebuild database record
    new_graph = graph.create(session=db_session)

    assert new_graph is not None
    assert isinstance(new_graph, dict)
    assert new_graph["graph_id"] is not None
    assert new_graph["name"] == db_graph.name
    assert new_graph["status"] == StatusFlag.COMPLETED.value


def test_create_graph__rebuild_flag_replaces_graph(
    db_graphs: Callable,
    db_stations: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Rebuilding database should replace previous database."""
    # Generate station record in database and check it is there
    db_graph = db_graphs()[0]
    db_station = db_stations(graph_ids=[db_graph.id])
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

    assert "Graph record deleted" in caplog.records[0].message
    assert "Graph record created" in caplog.records[1].message

    assert new_graph is not None
    assert isinstance(new_graph, dict)
    assert new_graph["graph_id"] is not None
    assert new_graph["name"] == DEFAULT_GRAPH_NAME
    assert new_graph["status"] == StatusFlag.PENDING.value
    assert re.fullmatch(r"\d{2}:\d{2}", new_graph["run_pace"])
    minutes, seconds = map(int, new_graph["run_pace"].split(":"))
    assert DEFAULT_SECONDS_PER_KM == minutes * 60 + seconds

    # Check that graph record has been replaced and the database tables have
    # been reset (i.e. no station record exists)
    new_graph_rec = list(db_session.query(Graph))
    new_station_rec = list(db_session.query(Station))

    assert len(new_graph_rec) == 1  # there should only be one graph
    assert new_graph_rec[0].id is not None
    assert new_graph_rec[0].date_created > original_date_created
    assert new_graph_rec[0].last_updated > original_last_updated
    assert new_graph_rec[0].date_created == new_graph_rec[0].last_updated
    assert new_graph_rec[0].name == DEFAULT_GRAPH_NAME
    assert new_graph_rec[0].status == StatusFlag.PENDING
    assert isinstance(new_graph_rec[0].run_pace, int)
    assert new_graph_rec[0].run_pace == DEFAULT_SECONDS_PER_KM

    assert len(new_station_rec) == 0  # there should be no station records


def test_create_graph__run_pace_is_invalid(
    generate_graph_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture
):
    """Test: Create a graph record in the database with an invalid run pace.
    Logs an error and returns None.
    """
    graph_info = generate_graph_infos(n_graphs=1)[0]
    graph_info["run_pace"] = "06;00"

    with caplog.at_level(logging.INFO):
        new_graph = graph.create(graph_info=graph_info, session=db_session)

    assert "Validation failed for graph" in caplog.records[0].message
    assert "Duration must be in MM:SS format." in caplog.records[0].message

    assert new_graph is None


def test_get_graph(db_graphs: Callable, db_session: Session):
    """Test: Get graph record from database."""
    db_graph = db_graphs(n_graphs=3)[1]  # second graph record
    graph_rec = graph.get_one(graph_id=db_graph.id, session=db_session)

    assert graph_rec.id == db_graph.id
    assert graph_rec.name == db_graph.name
    assert graph_rec.status == db_graph.status
    assert graph_rec.run_pace == db_graph.run_pace
    assert graph_rec.max_run_distance == db_graph.max_run_distance


def test_get_graphs(db_graphs: Callable, db_session: Session):
    """Test: Get all graph records from database."""
    n_graphs = 3
    db_recs = db_graphs(n_graphs=n_graphs)
    db_recs = sorted(db_recs, key=lambda g: g.id)
    graph_recs = graph.get_many(db_session)
    graph_recs = sorted(graph_recs, key=lambda g: g.id)

    assert isinstance(graph_recs, list)
    assert len(graph_recs) == n_graphs
    for graph_rec, db_rec in zip(graph_recs, db_recs):
        assert graph_rec.id == db_rec.id
        assert graph_rec.name == db_rec.name
        assert graph_rec.status == db_rec.status
        assert graph_rec.run_pace == db_rec.run_pace
        assert graph_rec.max_run_distance == db_rec.max_run_distance


def test_get_graphs__with_graph_ids(db_graphs: Callable, db_session: Session):
    """Test: Get multiple records that correspond to supplied graph IDs."""
    # Generate graph records and select subset to query
    n_graphs = 6
    n_samples = 3
    db_recs = db_graphs(n_graphs=n_graphs)
    db_recs_selected = random.sample(db_recs, n_samples)
    db_recs_selected = sorted(db_recs_selected, key=lambda g: g.id)
    graph_ids = {g.id for g in db_recs_selected}

    graph_recs = graph.get_many(db_session, graph_ids=graph_ids)
    graph_recs = sorted(graph_recs, key=lambda g: g.id)

    assert isinstance(graph_recs, list)
    assert len(graph_recs) == n_samples
    for graph_rec, db_rec in zip(graph_recs, db_recs_selected):
        assert graph_rec.id == db_rec.id
        assert graph_rec.name == db_rec.name
        assert graph_rec.status == db_rec.status
        assert graph_rec.run_pace == db_rec.run_pace
        assert graph_rec.max_run_distance == db_rec.max_run_distance


def test_get_graphs__with_limit_and_offset(
    db_graphs: Callable, db_session: Session
):
    """Test: Get a certain number of graph from the database (limit) after a
    particular record (offset).
    """
    n_graphs = 6
    db_recs = db_graphs(n_graphs=n_graphs)
    db_recs = sorted(db_recs, key=lambda g: g.id)

    limit = 3
    offset = 2
    # This should return sorted by graph ID
    graph_recs = graph.get_many(db_session, limit=limit, offset=offset)

    assert isinstance(graph_recs, list)
    assert len(graph_recs) == limit
    for graph_rec, db_rec in zip(graph_recs, db_recs[offset: offset + limit + 1]):
        assert graph_rec.id == db_rec.id
        assert graph_rec.name == db_rec.name
        assert graph_rec.status == db_rec.status
        assert graph_rec.run_pace == db_rec.run_pace
        assert graph_rec.max_run_distance == db_rec.max_run_distance


def test_update_graph(
    db_graphs: Callable, db_session: Session, caplog: pytest.LogCaptureFixture
):
    """Test: Update graph record with new status."""
    # Check graph in database has pending status
    db_graph = db_graphs()[0]
    assert db_graph.status == StatusFlag.PENDING
    original_date_created = db_graph.date_created
    original_last_updated = db_graph.last_updated

    graph_info = {"status": StatusFlag.COMPLETED}
    with caplog.at_level(logging.INFO):
        updated_graph = graph.update(
            graph_id=db_graph.id, graph_info=graph_info, session=db_session
        )

    assert "Graph record updated" in caplog.records[0].message

    assert updated_graph is not None
    assert isinstance(updated_graph, dict)
    assert updated_graph["graph_id"] is not None
    assert updated_graph["graph_id"] == db_graph.id
    assert updated_graph["name"] == db_graph.name
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
            graph_id=1, graph_info={}, session=db_session
        )

    assert "Graph record does not exist" in caplog.records[0].message
    assert updated_graph is None


def test_update_graph__name_is_of_invalid_data_type(
    db_graphs: Callable, db_session: Session, caplog: pytest.LogCaptureFixture
):
    """Test: Attempt to replace value of name field with invalid data type
    during an update.
    """
    db_graph = db_graphs()[0]
    graph_info = {"name": 2}
    with caplog.at_level(logging.INFO):
        updated_graph = graph.update(
            graph_id=db_graph.id, graph_info=graph_info, session=db_session
        )

    assert "Validation failed for graph" in caplog.records[0].message
    assert updated_graph is None


def test_update_graph__nothing_to_update_should_not_write_to_database(
    db_graphs: Callable, db_session: Session, caplog: pytest.LogCaptureFixture
):
    """Test: Attempt to update graph with empty dictionary. Should not update
    record.
    """
    db_graph = db_graphs()[0]
    original_date_created = db_graph.date_created
    original_last_updated = db_graph.last_updated

    graph_info = {}  # no fields to update
    with caplog.at_level(logging.INFO):
        updated_graph = graph.update(
            graph_id=db_graph.id, graph_info=graph_info, session=db_session
        )

    # No confirmation message in logs
    assert len(caplog.records) == 0

    assert updated_graph is not None
    assert isinstance(updated_graph, dict)
    assert updated_graph["graph_id"] is not None
    assert updated_graph["graph_id"] == db_graph.id
    assert updated_graph["name"] == db_graph.name
    assert updated_graph["status"] == db_graph.status

    # Check that the graph has not been updated
    db_rec = list(db_session.query(Graph))
    assert len(db_rec) == 1  # there should only be one graph in the database
    assert db_rec[0].date_created == original_date_created
    assert db_rec[0].last_updated == original_last_updated


def test_delete_graph(
    db_graphs: Callable, db_session: Session, caplog: pytest.LogCaptureFixture
):
    """Test: Delete graph record from database. Check correct record is
    removed."""
    n_graphs = 3
    db_recs = db_graphs(n_graphs=n_graphs)
    db_del = random.choice(db_recs)  # randomly select record to delete

    with caplog.at_level(logging.INFO):
        result = graph.delete(graph_id=db_del.id, session=db_session)
    assert result is True  # deletion was successful
    assert "Graph record deleted" in caplog.records[0].message

    # check that correct record was deleted
    db_recs.remove(db_del)
    db_recs = sorted(db_recs, key=lambda g: g.id)
    graph_recs = db_session.query(Graph).all()  # all graphs in database
    graph_recs = sorted(db_recs, key=lambda g: g.id)
    assert len(graph_recs) == n_graphs - 1
    for graph_rec, db_rec in zip(graph_recs, db_recs):
        assert graph_rec.id == db_rec.id
        assert graph_rec.name == db_rec.name
        assert graph_rec.status == db_rec.status


def test_delete_graph__all_associated_tables_are_removed(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    db_branches: Callable,
    db_connections: Callable,
    db_session: Session
):
    """Test: Delete graph record from database. Check that all related records
    are removed.
    """
    # Build database and associate lines, stations, branches and connections
    # with new graph
    new_graph = db_graphs()[0]
    n_lines = 3
    new_lines = db_lines(graph_ids=[new_graph.id], n_lines=n_lines)
    line_ids = [ln.id for ln in new_lines]
    n_stations = 12
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=n_stations)
    station_ids = [sttn.id for sttn in new_stations]
    n_branches = 4
    new_branches = db_branches(
        graph_id=new_graph.id,
        line_ids=line_ids,
        stations=new_stations,
        n_branches=n_branches,
    )
    n_connections = 16
    new_connections = db_connections(
        graph_id=new_graph.id,
        line_ids=line_ids,
        station_ids=station_ids,
        n_connections=n_connections,
    )

    assert db_session.query(Graph).count() == 1
    assert db_session.query(Line).count() == n_lines
    assert db_session.query(Station).count() == n_stations
    assert db_session.query(Branch).count() == n_branches
    n_branchstations = db_session.query(BranchStation).count()
    assert n_branchstations > 0
    assert db_session.query(Connection).count() == n_connections

    result = graph.delete(graph_id=new_graph.id, session=db_session)
    assert result is True

    assert db_session.query(Graph).count() == 0
    assert db_session.query(Line).count() == 0
    assert db_session.query(Station).count() == 0
    assert db_session.query(Branch).count() == 0
    assert db_session.query(BranchStation).count() == 0
    assert db_session.query(Connection).count() == 0


def test_delete_graph__graph_does_not_exist(
    db_session: Session, caplog: pytest.LogCaptureFixture
):
    """Test: Attempt to delete graph record that does not exist. Should return
    and informative message.
    """
    with caplog.at_level(logging.INFO):
        result = graph.delete(graph_id=1, session=db_session)

    assert result is False
    assert "Graph record does not exist" in caplog.records[0].message
