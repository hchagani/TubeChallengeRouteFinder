import pytest
from typing import Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from tubechallenge.db.tables import Base, Graph


@pytest.fixture
def db_session() -> Session:
    """Create an in-memory database and return a session."""
    engine = create_engine(
        "sqlite:///",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

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
