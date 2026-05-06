from copy import deepcopy

from sqlalchemy.orm import Session

from tubechallenge.db import (
    branch,
    connection,
    db,
    enums,
    graph,
    line,
    station,
)
from tubechallenge.data.tube import (
    get_tube_connections,
    get_tube_lines,
    get_tube_stations_and_branches,
)
from tubechallenge.data.foot import get_running_connections


def fill_db(graph_id: int):
    """Fill database corresponding to graph ID. Methods to obtain stations and
    modes of transport, and calculate journey times are called and the results
    are written to the database.

    Args:
        graph_id (int): ID for database (i.e. graph) to fill.
    """
    with db.SessionLocal() as session:
        # Do not refill database if it has been filled previously
        db_graph = graph.get_one(graph_id=graph_id, session=session)
        if db_graph:
            if db_graph.status == enums.StatusFlag.COMPLETED:
                return

        # Commence filling database
        graph.update(
            graph_id=graph_id,
            graph_info={"status": enums.StatusFlag.RUNNING},
            session=session,
        )

        # Tube lines
        line_infos = get_tube_lines(graph_id)
        new_lines = line.create(line_infos=line_infos, session=session)
        if new_lines is None:
            graph.update(
                graph_id=graph_id,
                graph_info={"status": enums.StatusFlag.FAILED},
                session=session,
            )
            return

        # Tube stations
        station_infos, branch_infos = get_tube_stations_and_branches(
            graph_id, new_lines
        )
        new_stations = station.create(
            station_infos=station_infos, session=session
        )
        if new_stations is None:
            graph.update(
                graph_id=graph_id,
                graph_info={"status": enums.StatusFlag.FAILED},
                session=session,
            )
            return

        # Branches and BranchStations
        station_map = {
            new_station.station_id: new_station.id for new_station in new_stations
        }  # used to create BranchStation records
        new_branches = branch.create(
            branch_infos=deepcopy(branch_infos),
            station_map=station_map,
            session=session,
        )
        if new_branches is None:
            graph.update(
                graph_id=graph_id,
                graph_info={"status": enums.StatusFlag.FAILED},
                session=session,
            )
            return

        # Connections between adjacent stations
        line_map = {new_line.id: new_line.line_id for new_line in new_lines}
        connection_infos = get_tube_connections(
            graph_id=graph_id,
            branch_infos=branch_infos,
            line_map=line_map,
            station_map=station_map,
        )
        new_connections = connection.create(
            connection_infos=connection_infos,
            session=session,
        )
        if new_connections is None:
            graph.update(
                graph_id=graph_id,
                graph_info={"status": enums.StatusFlag.FAILED},
                session=session,
            )
            return

        # Create line to represent running between stations
        run_line = line.create(
            line_infos=[
                {
                    "line_id": "walk",
                    "name": "Walk",
                    "mode": enums.ModeOfTransport.FOOT.value,
                    "graph_id": graph_id,
                }
            ], session=session
        )
        run_connections_infos = get_running_connections(
            graph_id=graph_id, run_line_id=run_line[0].id, session=session
        )
        new_run_connections = connection.create(
            connection_infos=run_connections_infos, session=session
        )
        if new_run_connections is None:
            graph.update(
                graph_id=graph_id,
                graph_info={"status": enums.StatusFlag.FAILED},
                session=session,
            )
            return

        # Update graph record to indicate that it has been filled
        graph.update(
            graph_id=graph_id,
            graph_info={"status": enums.StatusFlag.COMPLETED},
            session=session,
        )
        return
