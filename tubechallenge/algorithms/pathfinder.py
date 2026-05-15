from collections import Counter
from datetime import datetime
import heapq
import itertools
import json
import jsonschema
import logging
import numpy as np
from pathlib import Path
from typing import IO
from uuid import uuid4

from sqlalchemy.orm import Session

from tubechallenge.algorithms.constants import PARK_STATION_IDS
from tubechallenge.db import line, station
from tubechallenge.db.db import SessionLocal
from tubechallenge.db.enums import ModeOfTransport
from tubechallenge.db.tables import Station
from tubechallenge.utils.haversine import get_bounding_box, get_heuristic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CURRENT_DIR = Path(__file__).resolve().parent
TUBECHALLENGE_ROOT = CURRENT_DIR.parent


class InvalidJourneysFileError(Exception):
    """Raised when journeys file has missing or duplicate station pairs."""


def reconstruct_path(
    final_state: tuple[Station, int, bool],
    g_score: dict[tuple[Station, int | None], float],
    came_from: dict[tuple[Station, int | None], tuple[Station, int | None]],
) -> list[tuple[str, int, float]]:
    """Reconstruct path from A* pathfinding algorithm.

    Args:
        final_state (tuple): database record for destination station, database
          line ID for mode of transport to reach destination, flag to indicate
          whether route starts with a tube journey.
        g_score (dict): journey times to stations.
        came_from (dict): chain of stations explored by pathfinding algorithm.

    Returns:
        list of tuples of station name, line ID and travel time in order.
    """
    path = []

    # Trace path back to origin station
    current_state = final_state
    current_line = None
    while current_state in came_from:
        if current_line != current_state[1]:
            path.append(
                (
                    current_state[0].name,
                    current_state[1],
                    g_score[current_state]
                ),
            )
        current_line = current_state[1]
        current_state = came_from[current_state]

    # Add starting station to path
    path.append(
        (current_state[0].name, current_state[1], g_score[current_state])
    )
    path.reverse()  # Start at origin station

    return path


def get_surrounding_stations(
    graph_id: int,
    stations_by_id: dict[int, Station],
    latitude: float,
    longitude: float,
    session: Session,
    bb_side: float = 2000.0
) -> dict[int, Station]:
    """Get station records from database that lie within a region, defined by a
    bounding box.

    Args:
        graph_id (int): ID of graph record that stations belong to.
        stations_by_id (dict[int, Station]): map of station database IDs to
          station records.
        latitude (float): latitude coordinate of centre of bounding box.
        longitude (float): longitude coordinate of centre of bounding box.
        session (Session): database session.
        bb_side (float): length of side of bounding box in metres.

    Returns:
        updated map of station database IDs to station database records.
    """
    lat_min, lat_max, lon_min, lon_max = get_bounding_box(
        latitude, longitude, bb_side
    )
    stations = station.get_many(
        graph_id=graph_id,
        latitude_min=lat_min,
        latitude_max=lat_max,
        longitude_min=lon_min,
        longitude_max=lon_max,
        session=session,
    )

    for stn in stations:
        # Insert station if it has not been retrieved before
        stations_by_id.setdefault(stn.id, stn)

    return stations_by_id


def get_stations(
    graph_id: int,
    station_ids: list[int],
    stations_by_id: dict[int, Station],
    session: Session,
) -> dict[int, Station]:
    """Get stations of interest and their surrounding stations to reduce
    database lookups.

    Args:
        graph_id (int): ID of graph record that stations belong to.
        station_ids (list[int]): database IDs for stations of interest.
        stations_by_id (dict[int, Station]): map of station database IDs to
          station database records.
        session (Session): database session.

    Returns:
        map of station database IDs to station database records.
    """
    stations_by_id = {}
    for station_id in station_ids:
        db_station = session.get(Station, station_id)
        stations_by_id = get_surrounding_stations(
            graph_id=graph_id,
            stations_by_id=stations_by_id,
            latitude=db_station.latitude,
            longitude=db_station.longitude,
            session=session,
        )

    return stations_by_id


def astar(
    graph_id: int,
    origin_id: int,
    destination_id: int,
    line_is_tube: dict[int, bool],
):
    """Implement A* pathfinding algorithm to find shortest path between
    stations.

    Args:
        graph_id (int): ID for graph record that stations belong to.
        origin_id (int): origin station database ID.
        destination_id (int): destination station database ID.
        line_is_tube (dict): indicates whether the line database ID represents
          a tube line.
    """
    counter = itertools.count()

    with SessionLocal() as session:
        stations_by_id = {}
        # Retrieve stations that are near origin and destination to reduce
        # database lookups
        stations_by_id = get_stations(
            graph_id=graph_id,
            station_ids=[origin_id, destination_id],
            stations_by_id=stations_by_id,
            session=session,
        )
        start_station = stations_by_id[origin_id]
        final_station = stations_by_id[destination_id]

        start_state = (start_station, None, None)

        open_set = []
        heapq.heappush(open_set, (0, next(counter), start_state))

        came_from = {}
        g_score = {start_state: 0}

        best_paths = {}
        while open_set:
            _, _, current_state = heapq.heappop(open_set)
            current_station, current_line, started_with_tube = current_state

            # Reconstruct path if we have arrived at destination
            if current_station == final_station:
                path = reconstruct_path(
                    final_state=current_state,
                    g_score=g_score,
                    came_from=came_from,
                )
                duration = path[-1][2]

                tube_end = line_is_tube.get(path[-1][1], False)
                key = (started_with_tube, tube_end)

                if key not in best_paths or duration < best_paths[key]["duration"]:
                    best_paths[key] = {
                        "duration": duration,
                        "tube_start": started_with_tube,
                        "tube_end": tube_end,
                        "path": path,
                    }

                continue  # look for other paths

            # Stop searching if no better solution exists and we have found a
            # tube-only path
            if (True, True) in best_paths:
                best_tube_tube = best_paths[(True, True)]["duration"]
                if open_set and open_set[0][0] > best_tube_tube:
                    break

            for conn in current_station.connections_from:
                # Check connection is active
                if not conn.active:
                    continue

                next_station = stations_by_id.get(conn.to_station.id)
                if not next_station:
                    get_surrounding_stations(
                        graph_id=graph_id,
                        stations_by_id=stations_by_id,
                        latitude=conn.to_station.latitude,
                        longitude=conn.to_station.longitude,
                        session=session,
                    )
                    next_station = stations_by_id[conn.to_station_id]
                next_line = conn.line_id

                cost = conn.time  # travel time between stations

                # Line change incurs penalty of 2 minutes (time for changing
                # platforms) plus half time between services (waiting time on
                # platform)
                if current_line is not None and next_line != current_line:
                    cost += 2 + conn.interval / 2

                # Establish whether first leg started with tube train
                if started_with_tube is None:
                    next_started_with_tube = line_is_tube.get(next_line, False)
                else:
                    next_started_with_tube = started_with_tube
                next_state = (next_station, next_line, next_started_with_tube)

                temp_g = g_score[current_state] + cost

                # Check that g-score is an improvement on journey time to this
                # station before replacing path to it
                if temp_g < g_score.get(next_state, np.inf):
                    came_from[next_state] = current_state
                    g_score[next_state] = temp_g

                    f_score = temp_g + get_heuristic(
                        next_station.latitude,
                        next_station.longitude,
                        final_station.latitude,
                        final_station.longitude,
                    )

                    heapq.heappush(
                        open_set, (f_score, next(counter), next_state)
                    )

        candidates = sorted(
            best_paths.values(), key=lambda c: c["duration"]
        )

        return {
            "origin": start_station.name,
            "destination": final_station.name,
            "candidates": candidates,
        }


def get_journey_times_and_routes(
    station_list: list[str], journeys_file: Path
) -> list:
    """Ensure path file conforms to schema and contains routes for all stations
    in station list.

    Args:
        station_list (list[str]): list of station IDs.
        journeys_file (Path): path to journeys file.

    Returns:
        list of journey details between stations in station list.
    """
    with journeys_file.open("r", encoding="utf-8") as f:
        journeys_info = json.load(f)

    schema_file = TUBECHALLENGE_ROOT / "schemas" / "journeys.json"
    with schema_file.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    # Validate journeys file against schema
    jsonschema.validate(instance=journeys_info, schema=schema)

    # Check for duplicate journeys between stations
    station_pairs = [tuple(entry[0]) for entry in journeys_info]
    counter = Counter(station_pairs)
    duplicates = [pair for pair, count in counter.items() if count > 1]
    if len(duplicates) > 0:
        raise InvalidJourneysFileError(
            f"Duplicate pairs in journeys file: {duplicates}"
        )

    # Check for any missing journeys between stations
    station_pairs = set(station_pairs)
    station_ids = [db_station.id for db_station in station_list]
    missing_pairs = [
        pair for pair in itertools.permutations(
            station_ids, 2
        ) if pair not in station_pairs
    ]
    if len(missing_pairs) > 0:
        raise InvalidJourneysFileError(
            f"Missing pairs in journeys file: {missing_pairs}"
        )

    return journeys_info


def rename_journeys_file(journeys_file: Path):
    """Rename journeys file to prevent the overwriting of pre-computed paths.
    Use time stamp and UUID to create a unique file name.

    Args:
        journeys_file (Path): path to original journeys file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid4().hex

    backup_name = f"{journeys_file.stem}_{timestamp}_{unique_id}{journeys_file.suffix}"
    backup_path = journeys_file.with_name(backup_name)
    journeys_file.rename(backup_path)


def get_paths(
    graph_id: int,
    station_list: list[str] | None = None,
    journeys_filename: str = "journeys.json",
) -> list:
    """Get optimal paths between stations.

    Args:
        graph_id (int): ID of graph record that stations belong to.
        station_list (list[str]): list of station IDs between which to find a
          path.
        journeys_filename (str): name of file in data directory that contains,
          or will contain, journey details between stations in station list.

    Returns:
        list of journey details between stations in station list.
    """
    if not station_list:
        station_list = PARK_STATION_IDS

    with SessionLocal() as session:
        station_list = station.get_many(
            graph_id=graph_id, session=session, station_ids=station_list
        )
        line_list = line.get_many(graph_id=graph_id, session=session)

    # Identify tube lines
    line_is_tube = {
        ln.id: ln.mode == ModeOfTransport.TUBE.value for ln in line_list
    }

    # Check for pre-computed journeys
    journeys_file = TUBECHALLENGE_ROOT / "data" / journeys_filename
    try:
        return get_journey_times_and_routes(station_list, journeys_file)
    except FileNotFoundError as err:
        logger.error(f"File not found: {err}.")
    except (json.JSONDecodeError, jsonschema.exceptions.ValidationError) as err:
        logger.error(f"Invalid JSON: {err}.")
        rename_journeys_file(journeys_file)
    except InvalidJourneysFileError as err:
        logger.error(f"Invalid journeys file: {err}.")
        rename_journeys_file(journeys_file)

    logger.info(f"Creating new journeys file {journeys_filename}")

    journeys = {}
    for origin, destination in itertools.permutations(station_list, 2):
        reconstructed_journeys = astar(
            graph_id, origin.id, destination.id, line_is_tube
        )

        journeys[(origin.id, destination.id)] = reconstructed_journeys

    journey_details = [[k, v] for k, v in journeys.items()]
    with journeys_file.open("w", encoding="utf-8") as f:
        json.dump(journey_details, f, indent=4)

    return journey_details
