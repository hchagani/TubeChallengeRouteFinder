import itertools
import pytest
import random
from typing import Callable
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tubechallenge.db.constants import (
    MAX_LINE_ID_LENGTH,
    MAX_STATION_ID_LENGTH,
)
from tubechallenge.db.enums import BranchDirection, ModeOfTransport
from tubechallenge.db.tables import (
    Base,
    Branch,
    BranchStation,
    Connection,
    Graph,
    Line,
    Station,
)


@pytest.fixture
def db_session() -> Session:
    """Create an in-memory database and return a session."""
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def db_resource(db_session: Session) -> Callable:
    """Create a new record in the database."""
    def _create_records(rec_infos: list[dict], Record: Base) -> list[Base]:
        """Create new records in the database.

        Args:
            rec_info (list[dict]): data required to create record.
            Record (Base): database table class.

        Returns:
            record that has been written to database.
        """
        new_recs = []  # list of database records
        for rec_info in rec_infos:
            rec = Record(**rec_info)

            db_session.add(rec)
            db_session.commit()
            db_session.refresh(rec)

            new_recs.append(rec)

        return new_recs

    return _create_records


@pytest.fixture
def generate_graph_infos() -> Callable:
    def _generate_graph_infos(n_graphs: int = 1) -> list[dict]:
        """Generate data for graph records.

        Args:
            n_graphs (int): number of graph records.

        Returns:
            list of data required to create graph records.
        """
        graph_infos = []
        for idx in range(n_graphs):
            graph_infos.append({"name": f"Test Graph {idx}"})  # Increment name

        return graph_infos

    return _generate_graph_infos


@pytest.fixture
def db_graphs(
    generate_graph_infos: Callable, db_resource: Callable
) -> Callable:
    def _db_graphs(n_graphs: int = 1) -> list[Graph]:
        """Create records for graphs in the database.

        Args:
            n_graphs (int): number of graph records.

        Returns:
            graph records that have been written to the database.
        """
        graph_infos = generate_graph_infos(n_graphs)

        return db_resource(graph_infos, Graph)

    return _db_graphs


@pytest.fixture
def generate_line_infos() -> Callable:
    def _generate_line_infos(
        graph_ids: list[int], n_lines: int = 1
    ) -> list[dict]:
        """Generate data for line records.

        Args:
            graph_ids (list[int]): list of graph record IDs.
            n_lines (int): number of lines.

        Returns:
            list of data required to create line records.
        """
        valid_modes = [mode.value for mode in ModeOfTransport]
        line_infos = []
        for idx in range(n_lines):
            # Randomise line ID and increment name
            line_infos.append(
                {
                    "line_id": str(uuid4())[:MAX_LINE_ID_LENGTH],
                    "name": f"Test Line {idx}",
                    "mode": random.choice(valid_modes),
                    "graph_id": random.choice(graph_ids),
                }
            )

        return line_infos

    return _generate_line_infos


@pytest.fixture
def db_lines(generate_line_infos: Callable, db_resource: Callable) -> Callable:
    def _db_lines(graph_ids: list[int], n_lines: int = 1) -> list[Line]:
        """Create records for lines in the database.

        Args:
            graph_ids (list[int]): list of graph record IDs.
            n_lines (int): number of lines.

        Returns:
            line records that have been written to the database.
        """
        line_infos = generate_line_infos(graph_ids, n_lines)

        return db_resource(line_infos, Line)

    return _db_lines


@pytest.fixture
def generate_station_infos() -> Callable:
    def _generate_station_infos(
        graph_ids: list[int], n_stations: int = 1
    ) -> list[dict]:
        """Generate data for station records.

        Args:
            graph_ids (list[int]): list of graph record IDs.
            n_stations (int): number of stations.

        Returns:
            list of data required to create station records.
        """
        station_infos = []
        for idx in range(n_stations):
            # Randomise station ID and increment name; randomise latitude and
            # longitude coordinates centred on Central London
            station_infos.append(
                {
                    "station_id": str(uuid4())[:MAX_STATION_ID_LENGTH],
                    "name": f"Test Station {idx}",
                    "zone": str(random.randint(1, 7)),
                    "latitude": 51.5074 + random.random() - 0.5,
                    "longitude": -0.1272 + random.random() - 0.5,
                    "graph_id": random.choice(graph_ids),
                }
            )

        return station_infos

    return _generate_station_infos


@pytest.fixture
def db_stations(
    generate_station_infos: Callable, db_resource: Callable
) -> Callable:
    def _db_stations(
        graph_ids: list[int], n_stations: int = 1
    ) -> list[Station]:
        """Create records for stations in the database.

        Args:
            graph_ids (list[int]): list of graph record IDs.
            n_stations (int): number of stations.

        Returns:
            station records that have been written to the database.
        """
        station_infos = generate_station_infos(graph_ids, n_stations)

        return db_resource(station_infos, Station)

    return _db_stations


@pytest.fixture
def generate_branch_infos() -> Callable:
    def _generate_branch_infos(
            graph_id: int,
            line_ids: list[int],
            stations: list[Station],
            n_branches: int = 1,
    ) -> list[dict]:
        """Generate data for branch records. Line IDs assigned randomly to
        branches.

        Args:
            graph_id (int): ID for graph record.
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
                    "graph_id": graph_id,
                }
            )

        return branch_infos

    return _generate_branch_infos


@pytest.fixture
def db_branches(
    generate_branch_infos: Callable, db_resource: Callable
) -> Callable:
    def _db_branches(
        graph_id: int,
        line_ids: list[int],
        stations: list[Station],
        n_branches: int = 1,
    ) -> list[Branch]:
        """Create records for branches in the database. Line IDs assigned
        randomly to branches.

        Args:
            graph_id (int): ID for graph record.
            line_ids (list[int]): list of line IDs to associate with branches.
            stations (list[Station]): list of stations to associate with
              branches.
            n_branches (int): number of branches.

        Returns:
            branch records that have been written to the database.
        """
        branch_infos = generate_branch_infos(
            graph_id, line_ids, stations, n_branches
        )

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
                        graph_id=branch_info["graph_id"],
                    )
                )

        return db_resource(branch_infos, Branch)

    return _db_branches


@pytest.fixture
def generate_connection_infos() -> Callable:
    def _generate_connection_infos(
        graph_id: int,
        line_ids: list[int],
        station_ids: list[int],
        n_connections: int = 1,
    ) -> list[dict]:
        """Generate data for records of connections between adjacent stations.
        Randomly select combinations of originating and destination stations,
        and lines connecting them, and assign random integer journey times.

        Args:
            graph_id (int): ID for graph record.
            line_ids (list[int]): list of line IDs to associate with
              connections.
            station_ids (list[int]): list of station IDs to choose from when
              assigning originating and destination stations.
            n_connections (int): number of connections.

        Returns:
            list of data requried to create records of connections between
              adjacent stations.
        """
        connection_infos = []

        # Get all possible combinations of stations and lines
        possible_combinations = [
            (
                from_station, to_station, line
            ) for from_station, to_station, line in itertools.product(
                station_ids, station_ids, line_ids
            ) if from_station != to_station
        ]

        # Number of connections cannot exceed number of possible combinations
        n_connections = min(n_connections, len(possible_combinations))

        selected_combinations = random.sample(
            possible_combinations, n_connections
        )

        for from_station_id, to_station_id, line_id in selected_combinations:
            connection_infos.append(
                {
                    "graph_id": graph_id,
                    "from_station_id": from_station_id,
                    "to_station_id": to_station_id,
                    "line_id": line_id,
                    "time": random.randint(1, 8),  # randomise journey times
                    "interval": random.randint(1, 10),  # randomise times between services
                }
            )

        return connection_infos

    return _generate_connection_infos


@pytest.fixture
def db_connections(
    generate_connection_infos: Callable, db_resource: Callable
) -> Callable:
    def _db_connections(
        graph_id: int,
        line_ids: list[int],
        station_ids: list[int],
        n_connections: int = 1,
    ) -> list[Connection]:
        """Create records for connections between adjacent stations in the
        database.

        Args:
            graph_id (int): ID for graph record.
            line_ids (list[int]): list of line IDs to associate with
              connections.
            station_ids (list[int]): list of station IDs to associate with
              connections.
            n_connections (int): number of connections.

        Returns:
            connection records that have been written to the database.
        """
        connection_infos = generate_connection_infos(
            graph_id, line_ids, station_ids, n_connections
        )

        return db_resource(connection_infos, Connection)

    return _db_connections



@pytest.fixture
def get_invalid_resource_id() -> Callable:
    def _get_invalid_resource_id(max_length: int) -> str:
        """Generate a resource ID that is larger than the maximum length, thus
        making it invalid.

        Args:
            max_length (int): maximum length of a valid resource ID.

        Returns:
            string of length greater than max_length.
        """
        resource_id = ""
        while len(resource_id) <= max_length:
            resource_id += str(uuid4())

        return resource_id

    return _get_invalid_resource_id
