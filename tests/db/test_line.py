import logging
import pytest
from typing import Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from tubechallenge.db import line
from tubechallenge.db.constants import MAX_LINE_ID_LENGTH


def test_create_line(
    generate_line_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a line record in the database."""
    line_info = generate_line_infos()

    with caplog.at_level(logging.INFO):
        new_line = line.create(line_info, db_session)
    assert "Tube line record created" in caplog.records[0].message

    assert isinstance(new_line, list)
    assert len(new_line) == 1
    assert new_line[0].id is not None
    assert new_line[0].line_id == line_info[0]["line_id"]
    assert new_line[0].name == line_info[0]["name"]
    assert new_line[0].mode == line_info[0]["mode"]
    assert new_line[0].average_speed == 0.0  # default value


def test_create_line__line_id_is_too_long(
    generate_line_infos: Callable,
    get_invalid_resource_id: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a line record in the database with a line ID that exceeds
    the maximum length. Logs an error and returns None.
    """
    line_info = generate_line_infos()
    line_info[0]["line_id"] = get_invalid_resource_id(MAX_LINE_ID_LENGTH)

    with caplog.at_level(logging.ERROR):
        new_line = line.create(line_info, db_session)
    assert "Validation failed for tube line" in caplog.records[0].message

    assert new_line is None


def test_get_line(db_lines: Callable, db_session: Session):
    """Test: Get a single line record from the database."""
    db_rec = db_lines()[0]

    line_rec = line.get_one(db_rec.line_id, db_session)

    assert line_rec.id == db_rec.id
    assert line_rec.line_id == db_rec.line_id
    assert line_rec.name == db_rec.name
    assert line_rec.mode == db_rec.mode
    assert line_rec.average_speed == db_rec.average_speed


def test_get_lines(db_lines: Callable, db_session: Session):
    """Test: Get multiple line records from the database."""
    n_lines = 4
    db_recs = db_lines(n_lines)

    line_recs = line.get_many(db_session)

    assert isinstance(line_recs, list)
    assert len(line_recs) == n_lines
    for line_rec, db_rec in zip(line_recs, db_recs):
        assert line_rec.id == db_rec.id
        assert line_rec.line_id == db_rec.line_id
        assert line_rec.name == db_rec.name
        assert line_rec.mode == db_rec.mode
        assert line_rec.average_speed == db_rec.average_speed


def test_get_lines__with_limit_and_offset(
    db_lines: Callable, db_session: Session
):
    """Test: Get a certain number of records (limit) from the database after a
    particular record (offset).
    """
    n_lines = 6
    db_recs = db_lines(n_lines)

    limit = 3
    offset = 2
    line_recs = line.get_many(limit=limit, offset=offset, session=db_session)

    assert isinstance(line_recs, list)
    assert len(line_recs) == limit
    for line_rec, db_rec in zip(line_recs, db_recs[offset: offset + limit + 1]):
        assert line_rec.id == db_rec.id
        assert line_rec.line_id == db_rec.line_id
        assert line_rec.name == db_rec.name
        assert line_rec.mode == db_rec.mode
        assert line_rec.average_speed == db_rec.average_speed
