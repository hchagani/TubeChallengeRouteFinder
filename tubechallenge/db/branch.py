import logging
from pydantic import ValidationError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tubechallenge.db.schemas import CreateBranch
from tubechallenge.db.tables import Branch, BranchStation, Line, Station

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create(
    branch_infos: list[dict], station_map: dict, session: Session
) -> list[Branch]:
    """Create a new branch record and branch_station associations.

    Args:
        branch_infos (list[dict]): data required to create branch records and
          associations for stations that comprise each branch.
        station_map (dict): mapping between Transport for London and database
          station IDs.
        session (Session): database session.

    Returns:
        list of created branch records.
    """
    branches = []
    for branch_info in branch_infos:
        # Extract station sequence and look up station IDs to build
        # associations for stations on branch
        station_sequence = branch_info.pop("sequence")
        branch_station_infos = []
        for sequence, station in enumerate(station_sequence):
            try:
                station_id = station_map[station]
            except KeyError as err:
                logger.error(f"Station {station} has no ID in map")
                return None

            if session.get(Station, station_id) == None:
                logger.error(
                    f"Station {station_id} does not exist for station {station}"
                )
                return None

            branch_station_infos.append(
                {
                    "station_id": station_map[station],
                    "sequence": sequence,
                }
            )

        # Ensure that record for line exists in database
            if session.get(Line, branch_info["line_id"]) == None:
                logger.error(
                    f"Line {branch_info['line_id']} does not exist for branch {branch_info}"
                )
                return None

        try:
            CreateBranch(**branch_info, branchstations=branch_station_infos)
        except ValidationError as err:
            logger.error(f"Validation failed for branch {branch_info}: {err}")
            return None

        # Create branch record and branch_station associations
        branches.append(
            Branch(
                **branch_info,
                branchstations=[
                    BranchStation(**info) for info in branch_station_infos
                ],
            )
        )

    # Commit to database
    try:
        session.add_all(branches)
        session.commit()
    except SQLAlchemyError as err:
        session.rollback()
        logger.error(f"Database error: {err}")
        return None

    for branch in branches:
        session.refresh(branch)
        logger.info(f"Branch record created: {branch.id}")

    return branches


def get_one(branch_id: int, session: Session):
    """Get branch record."""
    return session.query(Branch).filter_by(id=branch_id).first()


def get_many(session: Session, limit: int = 0, offset: int = 0):
    """Get all branch records."""
    query = session.query(Branch)
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return query.all()
