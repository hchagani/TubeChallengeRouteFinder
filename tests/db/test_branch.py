import logging
import pytest
import random
from typing import Callable

from sqlalchemy.orm import Session

from tubechallenge.db import branch
from tubechallenge.db.enums import BranchDirection
from tubechallenge.db.tables import Branch, BranchStation, Line, Station


@pytest.fixture
def generate_branch_infos() -> Callable:
    def _generate_branch_infos(
            line_ids: list[int], stations: list[Station], n_branches: int = 1
    ) -> list[dict]:
        """Generate data for branch records. Line IDs assigned randomly to
        branches.

        Args:
            line_ids (list[int]): list of line IDs to associate with branches.
            stations (list[Station]): list of stations to associate with
              branches.
            n_branches (int): number of branches.

        Returns:
            list of data required to create branch records.
        """
        branch_infos = []
        for idx in range(n_branches):
            # Associate random line and stations to each branch
            line_id = random.choice(line_ids)
            branch_stations = random.sample(
                stations, random.randint(1, len(stations))
            )

            # Randomise branch ID and increment name
            branch_infos.append(
                {
                    "line_id": line_id,
                    "name": f"Test Branch {idx}",
                    "sequence": [
                        station.station_id for station in branch_stations
                    ],
                    "direction": random.choice(
                        [
                            direction.value for direction in BranchDirection
                        ]
                    ),
                }
            )

        return branch_infos

    return _generate_branch_infos


@pytest.fixture
def db_branches(
    generate_branch_infos: Callable,
    db_stations: list[Station],
    db_resource: Callable,
) -> Callable:
    def _db_branches(
        line_ids: list[int], stations: list[Station], n_branches: int = 1
    ) -> list[branch]:
        """Create records for branches in the database. Line IDs assigned
        randomly to branches.

        Args:
            line_ids (list[int]): list of line ids to associate with branches.
            stations (list[Station]): list of stations to associate with
              branches.
            n_branches (int): number of branches.

        Returns:
            branch records that have been written to the database.
        """
        branch_infos = generate_branch_infos(line_ids, stations, n_branches)

        # Create associations between stations and branches
        station_map = {station.station_id: station.id for station in stations}
        for branch_info in branch_infos:
            sequence = branch_info.pop("sequence")
            branch_info["branchstations"] = []
            for idx, station in enumerate(sequence):
                branch_info["branchstations"].append(
                    BranchStation(
                        station_id=station_map[station],
                        sequence=idx,
                    )
                )

        return db_resource(branch_infos, Branch)

    return _db_branches


def test_create_branch(
    db_lines: Callable,
    db_stations: Callable,
    generate_branch_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a branch record in the database."""
    # Create line and station records to associate with branch
    new_line = db_lines()[0]
    new_stations = db_stations(n_stations=6)
    station_map = {station.station_id: station.id for station in new_stations}

    branch_infos = generate_branch_infos(
        line_ids=[new_line.id], stations=new_stations
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
    db_lines: Callable,
    db_stations: Callable,
    generate_branch_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a branch record in the database with an integer for a name.
    Logs an error and returns None.
    """
    # Create line and station records to associate with branch
    new_line = db_lines()[0]
    new_stations = db_stations(n_stations=6)
    station_map = {station.station_id: station.id for station in new_stations}

    branch_infos = generate_branch_infos(
        line_ids=[new_line.id], stations=new_stations
    )
    branch_infos[0]["name"] = 0

    with caplog.at_level(logging.ERROR):
        new_branch = branch.create(branch_infos, station_map, db_session)
    assert "Validation failed for branch" in caplog.records[0].message

    assert new_branch is None


def test_create_branch__direction_is_invalid(
    db_lines: Callable,
    db_stations: Callable,
    generate_branch_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a branch record in the database with an invalid direction.
    Logs an error and returns None.
    """
    # Create line and station records to associate with branch
    new_line = db_lines()[0]
    new_stations = db_stations(n_stations=6)
    station_map = {station.station_id: station.id for station in new_stations}

    branch_infos = generate_branch_infos(
        line_ids=[new_line.id], stations=new_stations
    )
    branch_infos[0]["direction"] = "westbound"  # inbound/outbound are valid

    with caplog.at_level(logging.ERROR):
        new_branch = branch.create(branch_infos, station_map, db_session)
    assert "Validation failed for branch" in caplog.records[0].message

    assert new_branch is None


def test_create_branch__line_does_not_exist(
    db_stations: Callable,
    generate_branch_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a branch record in the database for a line that does not
    have a record in the database. Logs an error and returns None.
    """
    # Create station records to associate with branch
    new_stations = db_stations(n_stations=6)
    station_map = {station.station_id: station.id for station in new_stations}

    missing_line_id = 1
    branch_infos = generate_branch_infos(
        line_ids=[missing_line_id], stations=new_stations
    )

    with caplog.at_level(logging.ERROR):
        new_branch = branch.create(branch_infos, station_map, db_session)
    assert f"Line {missing_line_id} does not exist" in caplog.records[0].message

    assert new_branch is None


def test_create_branch__station_has_no_id(
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
    # Create line and station records to associate with branch
    new_line = db_lines()[0]
    new_stations = db_stations(n_stations=6)
    station_map = {station.station_id: station.id for station in new_stations}

    branch_infos= generate_branch_infos(
        line_ids=[new_line.id], stations=new_stations
    )
    missing_station_id = "Test Station with no ID"
    branch_infos[0]["sequence"].append(missing_station_id)

    with caplog.at_level(logging.ERROR):
        new_branch = branch.create(branch_infos, station_map, db_session)
    assert f"Station {missing_station_id} has no ID" in caplog.records[0].message

    assert new_branch is None


def test_create_branch__station_does_not_exist(
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
    # Create line and station records to associate with branch
    new_line = db_lines()[0]
    new_stations = db_stations(n_stations=6)
    station_map = {station.station_id: station.id for station in new_stations}
    missing_station_id = "Missing Test Station"
    station_map[missing_station_id] = len(new_stations) + 1

    branch_infos = generate_branch_infos(
        line_ids=[new_line.id], stations=new_stations
    )
    branch_infos[0]["sequence"].append(missing_station_id)

    with caplog.at_level(logging.ERROR):
        new_branch = branch.create(branch_infos, station_map, db_session)
    assert f"Station {station_map[missing_station_id]} does not exist" in caplog.records[0].message

    assert new_branch is None


def test_get_branch(
    db_lines: Callable,
    db_stations: Callable,
    db_branches: Callable,
    db_session: Session,
):
    """Test: Get a single branch record from the database."""
    # Create line and station records to associate with branch
    new_line = db_lines()[0]
    new_stations = db_stations(n_stations=6)

    db_rec = db_branches(line_ids=[new_line.id], stations=new_stations)[0]

    branch_rec = branch.get_one(db_rec.id, db_session)

    assert branch_rec.id == db_rec.id
    assert branch_rec.line_id == new_line.id
    assert branch_rec.name == db_rec.name
    assert branch_rec.direction == db_rec.direction
    assert len(branch_rec.branchstations) > 0
    assert len(branch_rec.branchstations) == len(db_rec.branchstations)
    assert all(
        elem in branch_rec.branchstations for elem in db_rec.branchstations
    )


def test_get_branches(
    db_lines: Callable,
    db_stations: Callable,
    db_branches: Callable,
    db_session: Session,
):
    """Test: Get multiple branch records from the database."""
    # Create line and station records to associate with new branches
    n_lines = 2
    line_ids = [new_line.id for new_line in db_lines(n_lines)]
    new_stations = db_stations(n_stations=12)

    # Create new branches
    n_branches = 4
    db_recs = db_branches(
        line_ids=line_ids, stations=new_stations, n_branches=n_branches
    )

    branch_recs = branch.get_many(db_session)

    assert isinstance(branch_recs, list)
    assert len(branch_recs) == n_branches
    for branch_rec, db_rec in zip(branch_recs, db_recs):
        assert branch_rec.id == db_rec.id
        assert branch_rec.line_id == db_rec.line_id
        assert branch_rec.name == db_rec.name
        assert branch_rec.direction == db_rec.direction
        assert len(branch_rec.branchstations) > 0
        assert len(branch_rec.branchstations) == len(db_rec.branchstations)
        assert all(
            elem in branch_rec.branchstations for elem in db_rec.branchstations
        )


def test_get_branches__with_limit_and_offset(
    db_lines: Callable, db_stations: Callable, db_branches: Callable, db_session: Session
):
    """Test: Get a certain number of records (limit) from the database after a
    particular record (offset).
    """
    # Create line and station records to associate with new branches
    n_lines = 3
    line_ids = [new_line.id for new_line in db_lines(n_lines)]
    new_stations = db_stations(n_stations=18)

    # Create new branches
    n_branches = 6
    db_recs = db_branches(
        line_ids=line_ids, stations=new_stations, n_branches=n_branches
    )

    limit = 3
    offset = 2
    branch_recs = branch.get_many(limit=limit, offset=offset, session=db_session)

    assert isinstance(branch_recs, list)
    assert len(branch_recs) == limit
    for branch_rec, db_rec in zip(
        branch_recs, db_recs[offset: offset + limit + 1]
    ):
        assert branch_rec.id == db_rec.id
        assert branch_rec.line_id == db_rec.line_id
        assert branch_rec.name == db_rec.name
        assert branch_rec.direction == db_rec.direction
        assert len(branch_rec.branchstations) > 0
        assert len(branch_rec.branchstations) == len(db_rec.branchstations)
        assert all(
            elem in branch_rec.branchstations for elem in db_rec.branchstations
        )
