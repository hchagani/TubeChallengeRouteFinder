import pytest
import re
from typing import Callable
from unittest.mock import ANY, patch

from fastapi import status
from fastapi.testclient import TestClient

from tubechallenge.api.app import ROUTER_PREFIX
from tubechallenge.db.constants import (
    DEFAULT_GRAPH_NAME,
    DEFAULT_MAX_RUN_DISTANCE,
    DEFAULT_SECONDS_PER_KM,
)
from tubechallenge.db.enums import StatusFlag


@pytest.fixture
def get_run_pace_string() -> Callable:
    def _get_run_pace_string(run_pace: int) -> str:
        """Convert run pace in seconds to HH:SS string format."""
        minutes, seconds = divmod(run_pace, 60)

        return f"{minutes:02d}:{seconds:02d}"

    return _get_run_pace_string


def test_create_graph__returns_created_record_and_starts_fill_db_task(
    client: TestClient
):
    """Test: Create new graph record and starts task to fill database in the
    background.
    """
    with patch("tubechallenge.api.graphs.fill_db") as mock_fill:
        response = client.put(f"{ROUTER_PREFIX}/graphs")

    assert response.status_code == status.HTTP_202_ACCEPTED

    payload = response.json()
    assert "graph_id" in payload
    assert payload["name"] == DEFAULT_GRAPH_NAME
    assert payload["status"] == StatusFlag.PENDING.value
    assert re.fullmatch(r"\d{2}:\d{2}", payload["run_pace"])
    minutes, seconds = map(int, payload["run_pace"].split(":"))
    assert DEFAULT_SECONDS_PER_KM == minutes * 60 + seconds
    assert payload["max_run_distance"] == DEFAULT_MAX_RUN_DISTANCE

    mock_fill.assert_called_with(payload["graph_id"])


def test_create_graph__returns_created_record_with_non_default_run_pace(
    client: TestClient, get_run_pace_string: Callable
):
    """Test: Create new graph record with run pace."""
    # Set run pace for test and check it differs from default
    run_pace = "06:30"
    assert get_run_pace_string(DEFAULT_SECONDS_PER_KM) != run_pace

    with patch("tubechallenge.api.graphs.fill_db") as mock_fill:
        response = client.put(
            f"{ROUTER_PREFIX}/graphs", params={"run_pace": run_pace}
        )

    assert response.status_code == status.HTTP_202_ACCEPTED

    payload = response.json()
    assert "graph_id" in payload
    assert payload["name"] == DEFAULT_GRAPH_NAME
    assert payload["status"] == StatusFlag.PENDING.value
    assert payload["run_pace"] == run_pace
    assert payload["max_run_distance"] == DEFAULT_MAX_RUN_DISTANCE

    mock_fill.assert_called_with(payload["graph_id"])


def test_create_graph__returns_created_record_with_non_default_max_run_distance(
    client: TestClient
):
    """Test: Create new graph record with maximum run distance."""
    # Set maximum run distance and check it differs from default
    max_run_distance = 3.5
    assert max_run_distance != DEFAULT_MAX_RUN_DISTANCE

    with patch("tubechallenge.api.graphs.fill_db") as mock_fill:
        response = client.put(
            f"{ROUTER_PREFIX}/graphs",
            params={"max_run_distance": max_run_distance},
        )

    assert response.status_code == status.HTTP_202_ACCEPTED

    payload = response.json()
    assert "graph_id" in payload
    assert payload["name"] == DEFAULT_GRAPH_NAME
    assert payload["status"] == StatusFlag.PENDING.value
    assert re.fullmatch(r"\d{2}:\d{2}", payload["run_pace"])
    minutes, seconds = map(int, payload["run_pace"].split(":"))
    assert DEFAULT_SECONDS_PER_KM == minutes * 60 + seconds
    assert payload["max_run_distance"] == max_run_distance

    mock_fill.assert_called_with(payload["graph_id"])


def test_create_graph__reports_database_build_in_progress(
    client: TestClient, db_graphs: Callable
):
    """Test: Attempt to create a new graph record when one exists in the
    database.
    """
    db_graphs()[0]

    with patch("tubechallenge.api.graphs.fill_db") as mock_fill:
        response = client.put(f"{ROUTER_PREFIX}/graphs")

    assert response.status_code == status.HTTP_409_CONFLICT
    mock_fill.assert_not_called()

    payload = response.json()
    assert payload["detail"] == "Database build already in progress."


def test_create_graph__reports_completed_graph_exists(client: TestClient):
    """Test: Attempt to create a graph when a completed one exists in the
    database.
    """
    with patch("tubechallenge.api.graphs.graph.create") as mock_create:
        with patch("tubechallenge.api.graphs.fill_db") as mock_fill:
            mock_create.return_value = {
                "graph_id": 1,
                "name": DEFAULT_GRAPH_NAME,
                "status": StatusFlag.COMPLETED.value,
            }

            response = client.put(f"{ROUTER_PREFIX}/graphs")

    assert response.status_code == status.HTTP_200_OK
    mock_create.assert_called_once_with(
        session=ANY, graph_info=ANY, rebuild=False
    )
    mock_fill.assert_not_called()

    payload = response.json()
    assert payload["message"] == "Database already exists."


def test_create_graph__rebuild_flag_passed_correctly(client: TestClient):
    """Test: Passes rebuild flag to create new graph record."""
    with patch("tubechallenge.api.graphs.graph.create") as mock_create:
        with patch("tubechallenge.api.graphs.fill_db") as mock_fill:
            mock_create.return_value = {
                "graph_id": 1,
                "name": DEFAULT_GRAPH_NAME,
                "status": StatusFlag.PENDING.value,
                "run_pace": "06:00",
            }

            response = client.put(
                f"{ROUTER_PREFIX}/graphs", params={"rebuild": True}
            )

    mock_create.assert_called_once_with(
        session=ANY, graph_info=ANY, rebuild=True
    )
    mock_fill.assert_called_once()


def test_get_graphs__returns_all_graphs(
    client: TestClient, db_graphs: Callable, get_run_pace_string: Callable
):
    """Test: Retrieve all graphs from database."""
    n_graphs = 3
    new_graphs = db_graphs(n_graphs=n_graphs)
    new_graphs = sorted(new_graphs, key=lambda g: g.id)
    new_graphs_dicts = [
        {
            "id": new_graph.id,
            "name": new_graph.name,
            "status": new_graph.status.value,
            "run_pace": get_run_pace_string(new_graph.run_pace),
            "max_run_distance": new_graph.max_run_distance,
            "date_created": new_graph.date_created.isoformat(),
            "last_updated": new_graph.last_updated.isoformat(),
        } for new_graph in new_graphs
    ]

    response = client.get(f"{ROUTER_PREFIX}/graphs")

    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    for graph_dict, new_graph_dict in zip(payload, new_graphs_dicts):
        assert graph_dict == new_graph_dict


def test_get_graphs__returns_graphs_according_to_limit_after_offset(
    client: TestClient, db_graphs: Callable, get_run_pace_string: Callable
):
    """Test: Retrieve graphs from database according to limit after an
    offset.
    """
    n_graphs = 6
    limit = 3
    offset = 2
    new_graphs = db_graphs(n_graphs=n_graphs)
    new_graphs = sorted(new_graphs, key=lambda g: g.id)
    new_graphs_dicts = [
        {
            "id": new_graph.id,
            "name": new_graph.name,
            "status": new_graph.status.value,
            "run_pace": get_run_pace_string(new_graph.run_pace),
            "max_run_distance": new_graph.max_run_distance,
            "date_created": new_graph.date_created.isoformat(),
            "last_updated": new_graph.last_updated.isoformat(),
        } for new_graph in new_graphs[offset:offset + limit + 1]
    ]

    response = client.get(
        f"{ROUTER_PREFIX}/graphs", params={"limit": 3, "offset": 2}
    )

    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    for graph_dict, new_graph_dict in zip(payload, new_graphs_dicts):
        assert graph_dict == new_graph_dict


def test_get_graphs__returns_graphs_according_to_requested_ids(
    client: TestClient, db_graphs: Callable, get_run_pace_string: Callable
):
    """Test: Retrieves graphs according to requested IDs."""
    n_graphs = 3
    new_graphs = db_graphs(n_graphs=n_graphs)
    new_graphs = sorted(new_graphs, key=lambda g: g.id)
    new_graphs_selected = [new_graphs[0], new_graphs[-1]]
    new_graphs_dicts = [
        {
            "id": new_graph.id,
            "name": new_graph.name,
            "status": new_graph.status.value,
            "run_pace": get_run_pace_string(new_graph.run_pace),
            "max_run_distance": new_graph.max_run_distance,
            "date_created": new_graph.date_created.isoformat(),
            "last_updated": new_graph.last_updated.isoformat(),
        } for new_graph in new_graphs_selected
    ]

    response = client.get(
        f"{ROUTER_PREFIX}/graphs",
        params={"graph_ids": [g.id for g in new_graphs_selected]},
    )

    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    for graph_dict, new_graph_dict in zip(payload, new_graphs_dicts):
        assert graph_dict == new_graph_dict


def test_get_graphs__returns_graphs_ignoring_duplicate_requested_ids(
    client: TestClient, db_graphs: Callable, get_run_pace_string: Callable
):
    """Test: Retrieves graphs according to requested IDs, ignoring duplicated
    IDs.
    """
    n_graphs = 3
    new_graphs = db_graphs(n_graphs=n_graphs)
    new_graphs = sorted(new_graphs, key=lambda g: g.id)
    new_graphs_selected = [new_graphs[0], new_graphs[-1]]
    new_graphs_dicts = [
        {
            "id": new_graph.id,
            "name": new_graph.name,
            "status": new_graph.status.value,
            "run_pace": get_run_pace_string(new_graph.run_pace),
            "max_run_distance": new_graph.max_run_distance,
            "date_created": new_graph.date_created.isoformat(),
            "last_updated": new_graph.last_updated.isoformat(),
        } for new_graph in new_graphs_selected
    ]

    graph_ids = [g.id for g in new_graphs_selected] + [new_graphs[-1].id]
    response = client.get(
        f"{ROUTER_PREFIX}/graphs", params={"graph_ids": graph_ids}
    )

    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    assert len(payload) == 2
    for graph_dict, new_graph_dict in zip(payload, new_graphs_dicts):
        assert graph_dict == new_graph_dict


def test_get_graphs__returns_empty_list_if_no_graphs_found(client: TestClient):
    """Test: Retrieves an empty list from database if no graphs are found."""
    response = client.get(f"{ROUTER_PREFIX}/graphs")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert len(payload) == 0


def test_get_graphs__returns_error_if_limit_is_zero(client: TestClient):
    """Test: Attempt to request limit = 0."""
    response = client.get(f"{ROUTER_PREFIX}/graphs", params={"limit": 0})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    payload = response.json()
    assert "detail" in payload
    assert len(payload["detail"]) == 1
    error = payload["detail"][0]
    assert error["loc"] == ["query", "limit"]
    assert error["type"] == "greater_than_equal"


def test_get_graphs__returns_error_if_limit_is_negative(client: TestClient):
    """Test: Attempt to request a negative limit."""
    response = client.get(f"{ROUTER_PREFIX}/graphs", params={"limit": -1})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    payload = response.json()
    assert "detail" in payload
    assert len(payload["detail"]) == 1
    error = payload["detail"][0]
    assert error["loc"] == ["query", "limit"]
    assert error["type"] == "greater_than_equal"


def test_get_graphs__returns_error_if_offset_is_negative(client: TestClient):
    """Test: Attempt to request a negative offset."""
    response = client.get(f"{ROUTER_PREFIX}/graphs", params={"offset": -1})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    payload = response.json()
    assert "detail" in payload
    assert len(payload["detail"]) == 1
    error = payload["detail"][0]
    assert error["loc"] == ["query", "offset"]
    assert error["type"] == "greater_than_equal"


def test_get_graph__returns_graph(
    client: TestClient, db_graphs: Callable, get_run_pace_string: Callable
):
    """Test: Retrieve an existing graph."""
    db_graph = db_graphs()[0]
    db_graph_dict = {
        "id": db_graph.id,
        "name": db_graph.name,
        "status": db_graph.status.value,
        "run_pace": get_run_pace_string(db_graph.run_pace),
        "max_run_distance": db_graph.max_run_distance,
        "date_created": db_graph.date_created.isoformat(),
        "last_updated": db_graph.last_updated.isoformat(),
    }

    response = client.get(f"{ROUTER_PREFIX}/graphs/{db_graph.id}")

    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    assert payload == db_graph_dict


def test_get_graph__returns_error_if_graph_not_found(client: TestClient):
    """Test: Attempt to retrieve a graph that does not exist."""
    graph_id = 1
    response = client.get(f"{ROUTER_PREFIX}/graphs/{graph_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND

    payload = response.json()
    assert payload["detail"] == f"Graph {graph_id} does not exist."
