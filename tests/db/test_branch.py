import logging
import pytest
from typing import Callable

from sqlalchemy.orm import Session

from tubechallenge.db import branch
from tubechallenge.db.tables import BranchStation, Graph, Line


def test_create_branch(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    generate_branch_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a branch record in the database."""
    # Create graph, line and station records to associate with branch
    new_graph = db_graphs()[0]
    new_line = db_lines(graph_ids=[new_graph.id])[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=6)
    station_map = {station.station_id: station.id for station in new_stations}

    branch_infos = generate_branch_infos(
        graph_id=new_graph.id, line_ids=[new_line.id], stations=new_stations
    )

    with caplog.at_level(logging.INFO):
        new_branch = branch.create(branch_infos, station_map, db_session)
    assert "Branch record created" in caplog.records[0].message

    assert isinstance(new_branch, list)
    assert len(new_branch) == 1
    assert new_branch[0].id is not None
    assert new_branch[0].line_id == new_line.id
    assert new_branch[0].name == branch_infos[0]["name"]
    assert new_branch[0].direction == branch_infos[0]["direction"]
    assert new_branch[0].graph_id == new_graph.id

    # Check graph is associated with branch
    db_graph = db_session.get(Graph, new_graph.id)
    assert len(db_graph.branches) == 1
    assert db_graph.branches[0].id == new_branch[0].id

    # Check line is associated with branch
    db_line = db_session.get(Line, new_line.id)
    assert len(db_line.branches) == 1
    assert db_line.branches[0].id == new_branch[0].id

    # Check stations are associated with branches
    db_branchstations = db_session.query(
        BranchStation
    ).filter_by(branch_id=new_branch[0].id).all()
    assert len(db_branchstations) > 0
    assert len(db_branchstations) == len(new_branch[0].branchstations)
    assert all(
        elem in db_branchstations for elem in new_branch[0].branchstations
    )


def test_create_branch__name_is_of_invalid_data_type(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    generate_branch_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a branch record in the database with an integer for a name.
    Logs an error and returns None.
    """
    # Create graph, line and station records to associate with branch
    new_graph = db_graphs()[0]
    new_line = db_lines(graph_ids=[new_graph.id])[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=6)
    station_map = {station.station_id: station.id for station in new_stations}

    branch_infos = generate_branch_infos(
        graph_id=new_graph.id, line_ids=[new_line.id], stations=new_stations
    )
    branch_infos[0]["name"] = 0

    with caplog.at_level(logging.ERROR):
        new_branch = branch.create(branch_infos, station_map, db_session)
    assert "Validation failed for branch" in caplog.records[0].message

    assert new_branch is None


def test_create_branch__direction_is_invalid(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    generate_branch_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a branch record in the database with an invalid direction.
    Logs an error and returns None.
    """
    # Create graph, line and station records to associate with branch
    new_graph = db_graphs()[0]
    new_line = db_lines(graph_ids=[new_graph.id])[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=6)
    station_map = {station.station_id: station.id for station in new_stations}

    branch_infos = generate_branch_infos(
        graph_id=new_graph.id, line_ids=[new_line.id], stations=new_stations
    )
    branch_infos[0]["direction"] = "westbound"  # inbound/outbound are valid

    with caplog.at_level(logging.ERROR):
        new_branch = branch.create(branch_infos, station_map, db_session)
    assert "Validation failed for branch" in caplog.records[0].message

    assert new_branch is None


def test_create_branch__line_does_not_exist(
    db_graphs: Callable,
    db_stations: Callable,
    generate_branch_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a branch record in the database for a line that does not
    have a record in the database. Logs an error and returns None.
    """
    # Create graph and station records to associate with branch
    new_graph = db_graphs()[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=6)
    station_map = {station.station_id: station.id for station in new_stations}

    missing_line_id = 1
    branch_infos = generate_branch_infos(
        graph_id=new_graph.id, line_ids=[missing_line_id], stations=new_stations
    )

    with caplog.at_level(logging.ERROR):
        new_branch = branch.create(branch_infos, station_map, db_session)
    assert f"Line {missing_line_id} does not exist" in caplog.records[0].message

    assert new_branch is None


def test_create_branch__station_has_no_id(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    generate_branch_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a branch record in the database that comprises of a station
    that does not have a corresponding ID in the map. Logs an error and returns
    None.
    """
    # Create graph, line and station records to associate with branch
    new_graph = db_graphs()[0]
    new_line = db_lines(graph_ids=[new_graph.id])[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=6)
    station_map = {station.station_id: station.id for station in new_stations}

    branch_infos= generate_branch_infos(
        graph_id=new_graph.id, line_ids=[new_line.id], stations=new_stations
    )
    missing_station_id = "Test Station with no ID"
    branch_infos[0]["sequence"].append(missing_station_id)

    with caplog.at_level(logging.ERROR):
        new_branch = branch.create(branch_infos, station_map, db_session)
    assert f"Station {missing_station_id} has no ID" in caplog.records[0].message

    assert new_branch is None


def test_create_branch__station_does_not_exist(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    generate_branch_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a branch record in the database that comprises of a station
    that does not have a record in the database. Logs an error and returns
    None.
    """
    # Create graph, line and station records to associate with branch
    new_graph = db_graphs()[0]
    new_line = db_lines(graph_ids=[new_graph.id])[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=6)
    station_map = {station.station_id: station.id for station in new_stations}
    missing_station_id = "Missing Test Station"
    station_map[missing_station_id] = len(new_stations) + 1

    branch_infos = generate_branch_infos(
        graph_id=new_graph.id, line_ids=[new_line.id], stations=new_stations
    )
    branch_infos[0]["sequence"].append(missing_station_id)

    with caplog.at_level(logging.ERROR):
        new_branch = branch.create(branch_infos, station_map, db_session)
    assert f"Station {station_map[missing_station_id]} does not exist" in caplog.records[0].message

    assert new_branch is None


def test_get_branch(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    db_branches: Callable,
    db_session: Session,
):
    """Test: Get a single branch record from the database."""
    # Create graph, line and station records to associate with branch
    new_graph = db_graphs()[0]
    new_line = db_lines(graph_ids=[new_graph.id])[0]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=6)

    db_rec = db_branches(
        graph_id=new_graph.id, line_ids=[new_line.id], stations=new_stations
    )[0]

    branch_rec = branch.get_one(db_rec.id, db_session)

    assert branch_rec.id == db_rec.id
    assert branch_rec.line_id == new_line.id
    assert branch_rec.name == db_rec.name
    assert branch_rec.direction == db_rec.direction
    assert branch_rec.graph_id == new_graph.id
    assert len(branch_rec.branchstations) > 0
    assert len(branch_rec.branchstations) == len(db_rec.branchstations)
    assert all(
        elem in branch_rec.branchstations for elem in db_rec.branchstations
    )


def test_get_branches(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    db_branches: Callable,
    db_session: Session,
):
    """Test: Get multiple branch records from the database."""
    # Create graph, line and station records to associate with new branches
    new_graph = db_graphs()[0]
    n_lines = 2
    line_ids = [new_line.id for new_line in db_lines([new_graph.id], n_lines)]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=12)

    # Create new branches
    n_branches = 4
    db_recs = db_branches(
        graph_id=new_graph.id,
        line_ids=line_ids,
        stations=new_stations,
        n_branches=n_branches,
    )
    db_recs = sorted(db_recs, key=lambda brnch: brnch.id)

    branch_recs = branch.get_many(graph_id=new_graph.id, session=db_session)
    branch_recs = sorted(branch_recs, key=lambda brnch: brnch.id)

    assert isinstance(branch_recs, list)
    assert len(branch_recs) == n_branches
    for branch_rec, db_rec in zip(branch_recs, db_recs):
        assert branch_rec.id == db_rec.id
        assert branch_rec.line_id == db_rec.line_id
        assert branch_rec.name == db_rec.name
        assert branch_rec.direction == db_rec.direction
        assert branch_rec.graph_id == new_graph.id
        assert len(branch_rec.branchstations) > 0
        assert len(branch_rec.branchstations) == len(db_rec.branchstations)
        assert all(
            elem in branch_rec.branchstations for elem in db_rec.branchstations
        )


def test_get_branches__with_limit_and_offset(
    db_graphs: Callable,
    db_lines: Callable,
    db_stations: Callable,
    db_branches: Callable,
    db_session: Session,
):
    """Test: Get a certain number of records (limit) from the database after a
    particular record (offset).
    """
    # Create graph, line and station records to associate with new branches
    new_graph = db_graphs()[0]
    n_lines = 3
    line_ids = [new_line.id for new_line in db_lines([new_graph.id], n_lines)]
    new_stations = db_stations(graph_ids=[new_graph.id], n_stations=18)

    # Create new branches
    n_branches = 6
    db_recs = db_branches(
        graph_id=new_graph.id,
        line_ids=line_ids,
        stations=new_stations,
        n_branches=n_branches,
    )
    db_recs = sorted(db_recs, key=lambda brnch: brnch.id)

    limit = 3
    offset = 2
    branch_recs = branch.get_many(
        graph_id=new_graph.id, limit=limit, offset=offset, session=db_session
    )  # this should return sorted by branch ID

    assert isinstance(branch_recs, list)
    assert len(branch_recs) == limit
    for branch_rec, db_rec in zip(
        branch_recs, db_recs[offset: offset + limit + 1]
    ):
        assert branch_rec.id == db_rec.id
        assert branch_rec.line_id == db_rec.line_id
        assert branch_rec.name == db_rec.name
        assert branch_rec.direction == db_rec.direction
        assert branch_rec.graph_id == new_graph.id
        assert len(branch_rec.branchstations) > 0
        assert len(branch_rec.branchstations) == len(db_rec.branchstations)
        assert all(
            elem in branch_rec.branchstations for elem in db_rec.branchstations
        )
