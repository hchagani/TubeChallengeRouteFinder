from datetime import datetime, timezone
import pytest
from unittest.mock import ANY, MagicMock, Mock, patch

from fastapi import BackgroundTasks, Response, status

from tubechallenge.api import graph
from tubechallenge.db.enums import StatusFlag
from tubechallenge.db.tables import Graph


@pytest.fixture
def background_tasks() -> BackgroundTasks:
    return BackgroundTasks()


@pytest.fixture
def response() -> Response:
    return Response()


def test_create_graph__starts_background_fill_db_task(
    background_tasks: BackgroundTasks, response: Response
):
    with patch("tubechallenge.api.graph.graph.create") as mock_create:
        with patch("tubechallenge.api.graph.fill_db") as mock_fill:
            mock_create.return_value = {
                "graph_id": 1, "status": StatusFlag.PENDING,
            }

            result = graph.create_graph(background_tasks, response)

            assert response.status_code == status.HTTP_202_ACCEPTED
            assert result["message"] == "Database build started."
            assert result["status"] == StatusFlag.PENDING.value

            assert len(background_tasks.tasks) == 1
            assert background_tasks.tasks[0].func == mock_fill


def test_create_graph__reports_database_build_in_progress(
    background_tasks: BackgroundTasks, response: Response
):
    with patch("tubechallenge.api.graph.graph.create") as mock_create:
        with patch("tubechallenge.api.graph.fill_db") as mock_fill:
            mock_create.return_value = {
                "graph_id": 1,
                "status": StatusFlag.PENDING,
                "state": "conflict",
            }

            result = graph.create_graph(background_tasks, response)

            assert response.status_code == status.HTTP_409_CONFLICT
            assert result["message"] == "Database build already in progress."
            assert result["status"] == StatusFlag.PENDING.value

            assert len(background_tasks.tasks) == 0


def test_create_graph__reports_completed_graph_exists(
    background_tasks: BackgroundTasks, response: Response
):
    with patch("tubechallenge.api.graph.graph.create") as mock_create:
        with patch("tubechallenge.api.graph.fill_db") as mock_fill:
            mock_create.return_value = {
                "graph_id": 1, "status": StatusFlag.COMPLETED
            }

            result = graph.create_graph(background_tasks, response)

            assert response.status_code == status.HTTP_200_OK
            assert result["message"] == "Database already exists."
            assert result["status"] == StatusFlag.COMPLETED.value

            assert len(background_tasks.tasks) == 0


def test_create_graph__rebuild_flag_passed_correctly(
    background_tasks: BackgroundTasks, response: Response
):
    with patch("tubechallenge.api.graph.graph.create") as mock_create:
        with patch("tubechallenge.api.graph.fill_db") as mock_fill:
            mock_create.return_value = {
                "graph_id": 1, "status": StatusFlag.PENDING
            }

            result = graph.create_graph(
                background_tasks, response, rebuild=True
            )

            assert response.status_code == status.HTTP_202_ACCEPTED
            assert result["message"] == "Database build started."
            assert result["status"] == StatusFlag.PENDING.value

            mock_create.assert_called_once_with(session=ANY, rebuild=True)


def test_get_graph__returns_database(response: Response):
    with patch("tubechallenge.api.graph.graph.get_one") as mock_get:
        mock_get.return_value = Graph(id=1, status=StatusFlag.COMPLETED)
        mock_session = Mock()

        result = graph.get_graph(response, session=mock_session, graph_id=1)

        assert response.status_code == status.HTTP_200_OK
        assert result["id"] == 1
        assert result["status"] == StatusFlag.COMPLETED.value

        mock_get.assert_called_once()


def test_get_graph__no_database_record(response: Response):
    with patch("tubechallenge.api.graph.graph.get_one") as mock_get:
        mock_get.return_value = None
        mock_session = Mock()

        result = graph.get_graph(response, session=mock_session, graph_id=1)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert result["id"] is None
        assert result["status"] is None
        assert result["message"] == "Graph does not exist yet."

        mock_get.assert_called_once()


def test_get_graph__returns_database_record_no_graph_id(response: Response):
    with patch("tubechallenge.api.graph.graph.get_many") as mock_get:
        mock_get.return_value = [Graph(id=1, status=StatusFlag.COMPLETED)]
        mock_session = Mock()

        result = graph.get_graph(response, session=mock_session)

        assert response.status_code == status.HTTP_200_OK
        assert result["id"] == 1
        assert result["status"] == StatusFlag.COMPLETED.value

        mock_get.assert_called_once()


def test_get_graph__no_database_record_no_graph_id(response: Response):
    with patch("tubechallenge.api.graph.graph.get_many") as mock_get:
        mock_get.return_value = []
        mock_session = Mock()

        result = graph.get_graph(response, session=mock_session)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert result["id"] is None
        assert result["status"] is None
        assert result["message"] == "Graph does not exist yet."

        mock_get.assert_called_once()
