import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tubechallenge.api.app import app
from tubechallenge.db.db import get_session


@pytest.fixture
def client(db_session: Session):
    """FastAPI test client for API tests.

    Args:
        db_session (Session): database session.

    Returns:
        client for testing.
    """
    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_session, None)
