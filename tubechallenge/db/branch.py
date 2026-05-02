import logging
from pydantic import ValidationError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tubechallenge.db.graph import get_many as get_graphs
from tubechallenge.db.schemas import CreateBranch
from tubechallenge.db.tables import Branch, BranchStation, Line, Station

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create(
    branch_infos: list[dict], station_map: dict, session: Session
) -> list[Branch] | None:
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
    graph_ids = [branch_info["graph_id"] for branch_info in branch_infos]
    db_graph_ids = {g.id for g in get_graphs(session, graph_ids=graph_ids)}

    branches = []
    for branch_info in branch_infos:
        graph_id = branch_info.get("graph_id", None)
        if graph_id not in db_graph_ids:
            logger.error(f"Invalid graph ID {graph_id}")
            return None

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
                    "graph_id": graph_id,
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


def get_one(branch_id: int, session: Session) -> Branch:
    """Get branch record.

    Args:
        branch_id (int): ID of branch record.
        session (Session): database session.

    Returns:
        requested branch record.
    """
    return session.query(Branch).filter_by(id=branch_id).first()


def get_many(
    graph_id: int, session: Session, limit: int = 0, offset: int = 0
) -> list[Branch]:
    """Get all branch records related to a particular graph record.

    Args:
        graph_id (int): ID of related graph record.
        session (Session): database session.
        limit (int): maximum number of line records to retrieve.
        offset (int): index of first branch record to retrieve.

    Returns:
        list of branch records ordered by ID.
    """
    query = (
        session.query(Branch).filter_by(graph_id=graph_id).order_by(Branch.id)
    )
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return query.all()
