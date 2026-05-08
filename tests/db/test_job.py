import logging
import pytest
import random
from typing import Callable

from sqlalchemy.orm import Session

from tubechallenge.db import job
from tubechallenge.db.enums import JobType, StatusFlag
from tubechallenge.db.tables import Graph, Job


@pytest.fixture
def generate_job_infos() -> Callable:
    def _generate_job_infos(graph_id: int, n_jobs: int = 1) -> list[dict]:
        """Generate data for job records.

        Args:
            graph_id (int): graph record ID to relate to job records.
            n_jobs (int): number of job records to generate.

        Returns:
            data required to create job record.
        """
        jobs = []
        for _ in range(n_jobs):
            # Randomise job type
            job_type = random.choice(
                [JobType.ROUTE_GENERATION.value, JobType.FIND_SOLUTION.value]
            )
            jobs.append({"graph_id": graph_id, "job_type": job_type})

        return jobs

    return _generate_job_infos


@pytest.fixture
def db_jobs(generate_job_infos: Callable, db_resource: Callable) -> Callable:
    def _db_jobs(graph_id: int, n_jobs: int = 1) -> list[Job]:
        """Generate records for jobs in database.

        Args:
            graph_id (int): graph record ID to relate to job records.
            n_jobs (int): number of job records to generate.

        Returns:
            job records that have been written to database.
        """
        job_infos = generate_job_infos(graph_id, n_jobs)

        return db_resource(job_infos, Job)

    return _db_jobs


def test_create_job(
    db_graphs: Callable,
    generate_job_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a job record in the database."""
    new_graph = db_graphs()[0]  # create graph that job will belong to

    job_info = generate_job_infos(graph_id=new_graph.id)[0]

    with caplog.at_level(logging.INFO):
        new_job = job.create(job_info, db_session)
    assert "Job record created" in caplog.records[0].message

    assert new_job.job_type == job_info["job_type"]
    assert new_job.status == StatusFlag.PENDING.value  # default value
    assert new_job.progress == 0.0  # default value
    assert new_job.error_message is None
    assert new_job.graph_id == new_graph.id

    # Check graph is associated with job
    db_graph = db_session.get(Graph, new_graph.id)
    assert len(db_graph.jobs) == 1


def test_create_job__graph_does_not_exist(
    generate_job_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a job record in the database with a graph ID that does not
    exist. Logs an error and returns None.
    """
    job_info = generate_job_infos(graph_id=1)[0]

    with caplog.at_level(logging.ERROR):
        new_job = job.create(job_info, db_session)
    assert "Invalid graph ID" in caplog.records[0].message

    assert new_job is None


def test_create_job__invalid_job_type(
    db_graphs: Callable,
    generate_job_infos: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Create a job record in the database with an invalid job type. Logs
    an error and returns None.
    """
    new_graph = db_graphs()[0]  # create graph that job will belong to

    job_info = generate_job_infos(graph_id=new_graph.id)[0]
    job_info["job_type"] = "find_generation"

    with caplog.at_level(logging.ERROR):
        new_job = job.create(job_info, db_session)
    assert "Validation failed for job" in caplog.records[0].message

    assert new_job is None


def test_get_job(db_graphs: Callable, db_jobs: Callable, db_session: Session):
    """Test: Get a single job record from the database."""
    new_graph = db_graphs()[0]

    db_job = db_jobs(graph_id=new_graph.id)[0]

    job_rec = job.get_one(db_job.id, db_session)

    assert job_rec.id == db_job.id
    assert job_rec.date_created == db_job.date_created
    assert job_rec.last_updated == db_job.last_updated
    assert job_rec.status == db_job.status
    assert job_rec.progress == db_job.progress
    assert job_rec.error_message == db_job.error_message
    assert job_rec.graph_id == db_job.graph_id


def test_get_jobs(db_graphs: Callable, db_jobs: Callable, db_session: Session):
    """Test: Get multiple job records from the database."""
    new_graph = db_graphs()[0]

    n_jobs = 3
    db_recs = db_jobs(graph_id=new_graph.id, n_jobs=n_jobs)
    db_recs = sorted(db_recs, key=lambda jb: jb.id)

    job_recs = job.get_many(graph_id=new_graph.id, session=db_session)
    job_recs = sorted(job_recs, key=lambda jb: jb.id)

    assert isinstance(job_recs, list)
    assert len(job_recs) == n_jobs
    for job_rec, db_rec in zip(job_recs, db_recs):
        assert job_rec.id == db_rec.id
        assert job_rec.date_created == db_rec.date_created
        assert job_rec.last_updated == db_rec.last_updated
        assert job_rec.status == db_rec.status
        assert job_rec.progress == db_rec.progress
        assert job_rec.error_message == db_rec.error_message
        assert job_rec.graph_id == db_rec.graph_id


def test_get_jobs__with_limit_and_offset(
    db_graphs: Callable, db_jobs: Callable, db_session: Session
):
    """Test: Get a certain number of records (limit) from the database after a
    particular record (offset).
    """
    new_graph = db_graphs()[0]

    n_jobs = 6
    db_recs = db_jobs(graph_id=new_graph.id, n_jobs=n_jobs)
    db_recs = sorted(db_recs, key=lambda jb: jb.id)

    limit = 3
    offset = 2
    job_recs = job.get_many(
        graph_id=new_graph.id, limit=limit, offset=offset, session=db_session
    )  # this should return sorted by job ID

    assert isinstance(job_recs, list)
    assert len(job_recs) == limit
    for job_rec, db_rec in zip(job_recs, db_recs[offset:offset + limit + 1]):
        assert job_rec.id == db_rec.id
        assert job_rec.date_created == db_rec.date_created
        assert job_rec.last_updated == db_rec.last_updated
        assert job_rec.status == db_rec.status
        assert job_rec.progress == db_rec.progress
        assert job_rec.error_message == db_rec.error_message
        assert job_rec.graph_id == db_rec.graph_id


def test_update_job(
    db_graphs: Callable,
    db_jobs: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Update job record with new status and error message."""
    # Check job in database has pending status and no error message
    new_graph = db_graphs()[0]
    new_job = db_jobs(graph_id=new_graph.id)[0]
    assert new_job.status == StatusFlag.PENDING
    assert new_job.error_message is None
    original_date_created = new_job.date_created
    original_last_updated = new_job.last_updated

    error_message = "Job failed"
    job_info = {"status": StatusFlag.FAILED, "error_message": error_message}
    with caplog.at_level(logging.DEBUG):
        updated_job = job.update(
            job_id=new_job.id, job_info=job_info, session=db_session
        )
    assert "Job record updated" in caplog.records[0].message

    assert updated_job is not None
    assert isinstance(updated_job, Job)
    assert updated_job.id == new_job.id
    assert updated_job.status == job_info["status"].value
    assert updated_job.progress == new_job.progress
    assert updated_job.error_message == error_message
    assert updated_job.graph_id == new_graph.id
    assert updated_job.date_created == original_date_created
    assert updated_job.last_updated > original_last_updated


def test_update_job__job_record_does_not_exist(
    db_session: Session, caplog: pytest.LogCaptureFixture
):
    """Test: Attempt to update a job record that does not exist. Should log an
    error and return None.
    """
    with caplog.at_level(logging.INFO):
        updated_job = job.update(job_id=1, job_info={}, session=db_session)

    assert "Job record does not exist" in caplog.records[0].message
    assert updated_job is None


def test_update_job__progress_is_of_invalid_data_type(
    db_graphs: Callable,
    db_jobs: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Attempt to update progress field with an invalid data type. Should
    log an error and return None.
    """
    new_graph = db_graphs()[0]
    new_job = db_jobs(graph_id=new_graph.id)[0]
    job_info = {"progress": "one-third"}

    with caplog.at_level(logging.ERROR):
        updated_job = job.update(
            job_id=new_job.id, job_info=job_info, session=db_session
        )

    assert "Validation failed for job" in caplog.records[0].message
    assert updated_job is None


def test_update_job__nothing_to_update_should_not_write_to_database(
    db_graphs: Callable,
    db_jobs: Callable,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Test: Attempt to update job with empty dictionary. Should not update
    record.
    """
    new_graph = db_graphs()[0]
    new_job = db_jobs(graph_id=new_graph.id)[0]
    original_date_created = new_job.date_created
    original_last_updated = new_job.last_updated

    job_info = {}  # no fields to update
    with caplog.at_level(logging.DEBUG):
        updated_job = job.update(
            job_id=new_job.id, job_info=job_info, session=db_session
        )

    # No confirmation message in logs
    assert len(caplog.records) == 0

    assert updated_job is not None
    assert isinstance(updated_job, Job)
    assert updated_job.id == new_job.id
    assert updated_job.status == new_job.status
    assert updated_job.progress == new_job.progress
    assert updated_job.error_message == new_job.error_message
    assert updated_job.graph_id == new_job.graph_id
    assert updated_job.date_created == original_date_created
    assert updated_job.last_updated == original_last_updated
