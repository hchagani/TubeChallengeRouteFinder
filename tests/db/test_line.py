import logging
import pytest
from typing import Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from tubechallenge.db import line
from tubechallenge.db.constants import MAX_LINE_ID_LENGTH
from tubechallenge.db.tables import Graph


def test_create_line(
    db_graphs: Callable,
    generate_line_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a line record in the database."""
    new_graph = db_graphs()[0]  # create graph that line will belong to

    line_info = generate_line_infos(graph_ids=[new_graph.id])

    with caplog.at_level(logging.INFO):
        new_line = line.create(line_info, db_session)
    assert "Tube line record created" in caplog.records[0].message

    assert isinstance(new_line, list)
    assert len(new_line) == 1
    assert new_line[0].id is not None
    assert new_line[0].line_id == line_info[0]["line_id"]
    assert new_line[0].name == line_info[0]["name"]
    assert new_line[0].mode == line_info[0]["mode"]
    assert new_line[0].graph_id == new_graph.id

    # Check graph is associated with line
    db_graph = db_session.get(Graph, new_graph.id)
    assert len(db_graph.lines) == 1
    assert db_graph.lines[0].id == new_line[0].id


def test_create_line__line_id_is_too_long(
    db_graphs: Callable,
    generate_line_infos: Callable,
    get_invalid_resource_id: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a line record in the database with a line ID that exceeds
    the maximum length. Logs an error and returns None.
    """
    new_graph = db_graphs()[0]  # create graph that line will belong to

    line_info = generate_line_infos(graph_ids=[new_graph.id])
    line_info[0]["line_id"] = get_invalid_resource_id(MAX_LINE_ID_LENGTH)

    with caplog.at_level(logging.ERROR):
        new_line = line.create(line_info, db_session)
    assert "Validation failed for tube line" in caplog.records[0].message

    assert new_line is None


def test_create_line__graph_does_not_exist(
    generate_line_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a line record in the database with a graph ID that does not
    exist.
    """
    line_info = generate_line_infos(graph_ids=[1])

    with caplog.at_level(logging.ERROR):
        new_line = line.create(line_info, db_session)
    assert "Invalid graph ID" in caplog.records[0].message

    assert new_line is None


def test_get_line(
    db_graphs: Callable, db_lines: Callable, db_session: Session
):
    """Test: Get a single line record from the database."""
    db_graph = db_graphs()[0]  # create graph that line will belong to

    db_rec = db_lines(graph_ids=[db_graph.id])[0]

    line_rec = line.get_one(
        line_id=db_rec.line_id, graph_id=db_graph.id, session=db_session
    )

    assert line_rec.id == db_rec.id
    assert line_rec.line_id == db_rec.line_id
    assert line_rec.name == db_rec.name
    assert line_rec.mode == db_rec.mode
    assert line_rec.graph_id == db_graph.id


def test_get_lines(
    db_graphs: Callable, db_lines: Callable, db_session: Session
):
    """Test: Get multiple line records from the database."""
    db_graph = db_graphs()[0]  # create graph that lines will belong to

    n_lines = 4
    db_recs = db_lines(graph_ids=[db_graph.id], n_lines=n_lines)
    db_recs = sorted(db_recs, key=lambda ln: ln.id)

    line_recs = line.get_many(graph_id=db_graph.id, session=db_session)
    line_recs = sorted(line_recs, key=lambda ln: ln.id)

    assert isinstance(line_recs, list)
    assert len(line_recs) == n_lines
    for line_rec, db_rec in zip(line_recs, db_recs):
        assert line_rec.id == db_rec.id
        assert line_rec.line_id == db_rec.line_id
        assert line_rec.name == db_rec.name
        assert line_rec.mode == db_rec.mode
        assert line_rec.graph_id == db_graph.id


def test_get_lines__with_limit_and_offset(
    db_graphs: Callable, db_lines: Callable, db_session: Session
):
    """Test: Get a certain number of records (limit) from the database after a
    particular record (offset).
    """
    db_graph = db_graphs()[0]  # create graph that lines will belong to
    n_lines = 6
    db_recs = db_lines(graph_ids=[db_graph.id], n_lines=n_lines)
    db_recs = sorted(db_recs, key=lambda ln: ln.id)

    limit = 3
    offset = 2
    line_recs = line.get_many(
        graph_id=db_graph.id, limit=limit, offset=offset, session=db_session
    )  # this should return sorted by line ID

    assert isinstance(line_recs, list)
    assert len(line_recs) == limit
    for line_rec, db_rec in zip(line_recs, db_recs[offset: offset + limit + 1]):
        assert line_rec.id == db_rec.id
        assert line_rec.line_id == db_rec.line_id
        assert line_rec.name == db_rec.name
        assert line_rec.mode == db_rec.mode
        assert line_rec.graph_id == db_graph.id
