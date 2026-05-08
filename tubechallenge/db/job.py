import logging
from pydantic import ValidationError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tubechallenge.db.graph import get_one as get_graph
from tubechallenge.db.schemas import CreateJob, UpdateJob
from tubechallenge.db.tables import Job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create(job_info: dict, session: Session) -> Job | None:
    """Create new job record.

    Args:
        job_info (dict): data required to create job record.
        session (Session): database session.

    Returns:
        created job record.
    """
    try:
        # Validate input data for job and create record
        validated_job = CreateJob(**job_info)

        if not get_graph(graph_id=validated_job.graph_id, session=session):
            logger.error(f"Invalid graph ID {validated_job.graph_id}")
            return None

        # Commit to database
        new_job = Job(**validated_job.model_dump())
        session.add(new_job)
        session.commit()
        session.refresh(new_job)
        logger.info(f"Job record created: {new_job.id}")

    except ValidationError as err:
        logger.error(f"Validation failed for job {job_info}: {err}")
        return None
    except SQLAlchemyError as err:
        session.rollback()
        logger.error(f"Database error: {err}")
        return None

    return new_job


def get_one(job_id: int, session: Session) -> Job:
    """Get job record.

    Args:
        job_id (int): ID of job record to retrieve.
        session (Session): database session.

    Returns:
        requested job record.
    """
    return session.query(Job).filter_by(id=job_id).first()


def get_many(
    graph_id: int, session: Session, limit: int = 0, offset: int = 0
) -> list[Job]:
    """Get all job records related to a particular graph record.

    Args:
        graph_id (int): ID of related graph record.
        session (Session): databae record.
        limit (int): maximum number of job records to retrieve.
        offset (int): index of first job record to retrieve.

    Returns:
        list of job records ordered by ID.
    """
    query = session.query(Job).filter_by(graph_id=graph_id).order_by(Job.id)

    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return query.all()


def update(job_id: int, job_info: dict, session: Session) -> Job | None:
    """Update job record.

    Args:
        job_id (int): ID of job record to update.
        job_info (dict): data to update job record.
        session (Session): database session.

    Returns:
        updated job record.
    """
    db_job = get_one(job_id, session)
    if not db_job:  # if job record does not exist
        logger.info("Job record does not exist: {job_id}")
        return None

    # Verify data
    try:
        updated_job = UpdateJob(**job_info)
    except ValidationError as err:
        logger.error(f"Validation failed for job {job_info}: {err}")
        return None

    # Update
    try:
        update_data = updated_job.model_dump(
            exclude_unset=True, exclude_none=True
        )

        # Only write to database if there is something to update
        if update_data:
            for field, value in update_data.items():
                setattr(db_job, field, value)

            session.commit()
            session.refresh(db_job)
            logger.debug(f"Job record updated: {db_job.id}")

        return db_job

    except SQLAlchemyError as err:
        session.rollback()
        logger.error(f"Database error: {err}")
        return None
