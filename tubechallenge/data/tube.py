from collections import Counter
import logging
import numpy as np
from operator import itemgetter
import requests
import sys
import time

from tubechallenge.db.enums import ModeOfTransport
from tubechallenge.db.tables import Line

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Transport for London infrastructures
LINE = "Line"
STATION = "StopPoint"

# Used to calculate frequencies
FIRST_HOUR = 8
LAST_HOUR = 20
TOTAL_TIME = LAST_HOUR + 1 - FIRST_HOUR  # [FIRST_HOUR, LAST_HOUR)

TURNHAM_GREEN_ID = "940GZZLUTNG"


class InvalidURLError(Exception):
    """Throw an exception when there is an issue with the URL."""

    def __init__(self, url: str, status_code: int, message=None):
        self.url = url
        self.status_code = status_code
        self.message = message or f"Request to '{url}' failed with status code {status_code}"
        super().__init__(self.message)


def get_url(infrastructure: str, url_suffix: str) -> dict:
    """Make a request to the Transport for London API and convert response into
    a dictionary.

    Args:
        infrastructure (str): transport infrastructure requested,
          e.g. Line, StopPoint (tube station).
        url_suffix (str): URL suffix containing detailed request.

    Returns:
        a dictionary of the response.
    """
    tfl_url = "/".join(["https://api.tfl.gov.uk/", infrastructure, url_suffix])

    for attempt in range(10):
        r = requests.get(tfl_url)
        if r.status_code == requests.status_codes.codes.ok:
            return r.json()

        if r.status_code == requests.status_codes.codes.too_many_requests:
            # request limit may have been exceeded so wait
            time.sleep(5 * (attempt + 1))
            continue

        break  # anything else

    raise InvalidURLError(tfl_url, r.status_code)


def get_tube_lines(graph_id: int) -> list[dict[str, str]]:
    """Acquire IDs and names of tube lines from Transport for London API.

    Args:
        graph_id (int): related graph ID.

    Returns:
        list of tube line IDs and names.
    """
    mode = ModeOfTransport.TUBE.value
    url_suffix = f"Mode/{mode}"
    tube_lines = []
    for tube_line in get_url(infrastructure=LINE, url_suffix=url_suffix):
        try:
            tube_lines.append(
                {
                    "line_id": tube_line["id"],
                    "name": tube_line["name"],
                    "mode": mode,
                    "graph_id": graph_id,
                }
            )
        except InvalidURLError as err:
            logger.error(f"{err}")
            continue  # log and move on to next line

    return tube_lines


def get_tube_stations(
    graph_id: int,
    routes: dict,
    tube_station_ids: set[str],
    tube_stations: [list[dict]],
) -> list[dict]:
    """
    Acquire IDs, names and locations of tube stations on a particlar tube line.

    Args:
        graph_id (int): related graph ID.
        routes (dict): route data for a particular tube line from Transport for
          London's API.
        tube_station_ids (set[str]): station IDs that have been added to the
          database.
        tube_stations (list[dict]): list of tube station IDs, names, and
          latitude and logitude coordinates.

    Returns:
        list of tube stations IDs, names, and latitude and longitude
          coordinates.
    """
    def append_station(
        station_id: str,
        name: str,
        zone: int,
        latitude: float,
        longitude: float,
        tube_station_ids: set[str],
        tube_stations: list[dict],
    ):
        """Append a unique station to the list of stations.

        Args:
            station_id (str): Transport for London's station ID.
            name (str): station name.
            latitude (float): station's latitude coordinate.
            longitude (float): station's longitude coordinate.
            tube_station_ids (set[str]): station IDs that have been added to
              the database.
            tube_stations (list[dict]): list of tube station IDs, names, and
              latitude and longitude coordinates.
        """
        if station_id not in tube_station_ids:
            tube_stations.append(
                {
                    "station_id": station_id,
                    "name": name.removesuffix(" Underground Station"),
                    "zone": zone,
                    "latitude": latitude,
                    "longitude": longitude,
                    "graph_id": graph_id,
                }
            )
            tube_station_ids.add(station_id)

    for tube_station in routes.get("stations", []):

        # There are three types of stations:
        # 1. Underground stations which only have tube connections
        if tube_station["stopType"] == "NaptanMetroStation":
            append_station(
                station_id=tube_station["id"],
                name=tube_station["name"],
                zone=tube_station["zone"],
                latitude=tube_station["lat"],
                longitude=tube_station["lon"],
                tube_station_ids=tube_station_ids,
                tube_stations=tube_stations,
            )

        # 2. Travel hubs where interchange with other forms of transport is
        # possible
        if tube_station["stopType"] == "TransportInterchange":
            try:
                hub = get_url(
                    infrastructure=STATION, url_suffix=tube_station["id"]
                )
            except InvalidURLError as err:
                logger.error(f"{err}")
                continue  # log and move to next tube station

            for line_group in hub.get("lineGroup", []):
                if routes["lineId"] in line_group.get("lineIdentifier", []):
                    if tube_station.get("zone"):
                        append_station(
                            station_id=line_group["stationAtcoCode"],
                            name=hub["commonName"],
                            zone=tube_station["zone"],
                            latitude=hub["lat"],
                            longitude=hub["lon"],
                            tube_station_ids=tube_station_ids,
                            tube_stations=tube_stations,
                        )

    return tube_stations


def get_tube_branches(
    graph_id: int, routes: dict, db_line_id: int, tube_branches: list[dict]
) -> list[dict]:
    """Create branches for a particular tube line.

    Args:
        graph_id (int): related graph ID.
        routes (dict): route data for a particular tube line from Transport for
          London's API.
        db_line_id (int): line ID from database.

    Returns:
        list of branch names, corresponding line IDs, and the sequence of
          stations.
    """
    for branch in routes.get("stopPointSequences", []):
        sequence = []
        try:
            for tube_station in branch["stopPoint"]:
                sequence.append(tube_station["stationId"])

            # Remove Turnham Green from Piccadilly line
            if routes["lineName"] == "Piccadilly" and TURNHAM_GREEN_ID in sequence:
                sequence.remove(TURNHAM_GREEN_ID)

            branch_name = " ".join(
                [
                    routes["lineName"],
                    sequence[0],
                    "to",
                    sequence[-1]],
            )
            direction = branch["direction"]
            tube_branches.append(
                {
                    "name": branch_name,
                    "line_id": db_line_id,
                    "direction": direction,
                    "sequence": sequence,
                    "graph_id": graph_id,
                }
            )

        except IndexError as err:
            logger.info("Sequence contains no stations. Skipping.")
            continue

    return tube_branches


def get_tube_stations_and_branches(
    graph_id: int, tube_lines: list[Line]
) -> list[dict]:
    """Go through each tube line:
        1. Aquire IDs, names and locations of tube stations.
        2. Derive information for branches from the station sequence.

    Args:
        graph_id (int): related graph ID.
        tube_lines (list[Line]): list of tube lines in database.

    Returns:
        tube_stations (list[dict]): list of tube stations IDs, names, and
          latitude and longitude coordinates.
        tube_branches (list[dict]): list of branch names, corresponding line
          IDs and station sequences.
    """
    tube_station_ids = set()
    tube_stations = []
    tube_branches = []

    for tube_line in tube_lines:
        try:
            url_suffix = f"{tube_line.line_id}/Route/Sequence/all"
            routes = get_url(infrastructure=LINE, url_suffix=url_suffix)

            tube_stations = get_tube_stations(
                graph_id=graph_id,
                routes=routes,
                tube_station_ids=tube_station_ids,
                tube_stations=tube_stations,
            )
            tube_branches = get_tube_branches(
                graph_id=graph_id,
                routes=routes,
                db_line_id=tube_line.id,
                tube_branches=tube_branches,
            )

        except InvalidURLError as err:
            logger.error(f"{err}")
            continue  # log and move to next line

    return tube_stations, tube_branches


def get_number_of_trains(schedules: list, s_idx_list: list[int]) -> Counter:
    """Get number of trains running on each service within a time window.

    Args:
        schedules (list): list of schedules separated according to day from
          Transport for London's API.
        s_idx_list (list[int]): list of station interval indexes for services
          that we are interested in.

    Returns:
        Counter object that gives number of each service within time window.
    """
    # Schedules are separated by day, so use the following priority when
    # selecting a schedule
    priority_schedule_names = [
        "Daily",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    counter = Counter()
    for name in priority_schedule_names:
        for schedule in schedules:
            if name in schedule["name"]:
                for journey in schedule["knownJourneys"]:
                    # Count trains within limits (FIRST_HOUR, LAST_HOUR + 1]
                    if int(journey["hour"]) >= FIRST_HOUR and int(journey["hour"]) <= LAST_HOUR:
                        if journey["intervalId"] in s_idx_list:
                            counter[journey["intervalId"]] += 1

                return counter

    return counter  # empty counter indicates that no services exist


def get_tube_services(
    timetable: dict, first_station_id: str, second_station_id: str
) -> list[dict]:
    """Get list of stations, travel times and total number of trains within a
    specified time window for a particular service.

    Args:
        timetable (dict): timetable data from the Transport for London API.
        first_station_id (str): Transport for London's ID for service's
          originating station.
        second_station_id (str): Transport for London's ID for second station
          in branch.

    Returns:
        list of tube services with list of stations served, travel times
          between stations and total number of trains within specified time
          window.
    """
    services = {}
    try:
        routes = timetable["timetable"]["routes"]
        for r_idx, route in enumerate(routes):
            station_intervals = route["stationIntervals"]
            s_idx_list = []

            for s_idx, station_interval in enumerate(station_intervals):
                station_list = [first_station_id]
                intervals = station_interval.get("intervals", [])
                if intervals:
                    if intervals[0]["stopId"] != second_station_id:
                        continue  # only interested in current branch
                cumulative_travel_times =[]

                # Get list of stations and calculate travel times between them
                for station in intervals:
                    station_list.append(station["stopId"])
                    cumulative_travel_times.append(station["timeToArrival"])
                arrival_times = np.array(cumulative_travel_times)
                shifted_times = np.concatenate(([0], arrival_times[:-1]))
                travel_times = arrival_times - shifted_times

                services[(r_idx, s_idx)] = {
                    "stations": station_list,
                    "times": travel_times,
                    "n_trains": 0,  # initialise in case there are no valid journeys
                }
                s_idx_list.append(s_idx)

            schedules = timetable["timetable"]["routes"][r_idx]["schedules"]
            counter = get_number_of_trains(schedules, s_idx_list)
            for s_idx, counts in counter.items():
                services[(r_idx, s_idx)]["n_trains"] = counts

    except KeyError as err:
        logger.error(f"{err}")
        sys.exit(1)

    return list(services.values())


def synchronise_journey_and_interval_times(
    connections: dict,
    first_station_id: str,
    second_station_id: str,
    line_id: str,
) -> None:
    """Synchronise journey and interval times. Time between stops and the
    interval between trains should be the same regardless of direction:
      1. Time between stops should be the mean between inbound and outbound
        services, rounded to the nearest integer.
      2. The interval between trains should be the minimum as some services
        will not appear on some branches, e.g. Upmister to Earl's Court will
        fail to take the Westbound service starting at Tower Hill into account.
        The Eastbound service to Tower Hill will be captured by the branch
        Earl's Court to Upmister.

    Args:
        connections (dict): dictionary of connections between adjacent
          stations.
        first_station_id (str): Transport for London ID for originating
          station.
        second_station_id (str): Transport for London ID for destination
          station.
        line_id (str): Transport for London ID for tube line.
    """
    key_1 = (first_station_id, second_station_id, line_id)
    key_2 = (second_station_id, first_station_id, line_id)

    mean_journey_time = round(
        (connections[key_1]["time"] + connections[key_2]["time"]) / 2
    )
    connections[key_1]["time"] = mean_journey_time
    connections[key_2]["time"] = mean_journey_time

    minimum_interval = min(
        connections[key_1]["interval"], connections[key_2]["interval"]
    )
    connections[key_1]["interval"] = minimum_interval
    connections[key_2]["interval"] = minimum_interval


def get_tube_connections(
    graph_id: int, branch_infos: list[dict], line_map: dict, station_map: dict
) -> list[dict]:
    """Go through each branch calculating journey times between adjacent
    stations.

    Args:
        graph_id (int): related graph ID.
        branch_infos (list[dict]): cleaned data on tube line branches extracted
          from Transport for London's API.
        line_map (dict): mapping between database and Transport for London line
          IDs.
        station_map (dict): mapping between Transport for London and database
          line IDs.

    Returns:
        list of station IDs, line IDs and journey times between adjacent
          stations.
    """
    connections = {}

    for branch_info in branch_infos:
        # Get timetable for each branch from API
        tfl_line_id = line_map[branch_info["line_id"]]
        first_station_id = branch_info["sequence"][0]
        last_station_id = branch_info["sequence"][-1]
        direction = branch_info["direction"]
        url_suffix = f"{tfl_line_id}/Timetable/{first_station_id}?direction={direction}"
        try:
            timetable = get_url(infrastructure=LINE, url_suffix=url_suffix)
        except InvalidURLError as err:
            logger.error(f"{err}")
            continue  # log and move to next branch

        # Get all possible services that depart from the branch's starting
        # station
        services = get_tube_services(
            timetable=timetable,
            first_station_id=first_station_id,
            second_station_id=branch_info["sequence"][1],
        )
        # Log a warning if no services for branch exist
        if len(services) == 0:
            logger.warning(
                f"Branch {branch_info['name']} has no services within time window. Skipping..."
            )
            continue
        # Use service that calls most stations including the branch's final
        # station to determine journey times between stations. This cuts out
        # any fast or semi-fast services on the Metropolitan line.
        sorted_services = sorted(
            services,
            key=lambda service: (
                last_station_id in service["stations"],
                len(service["stations"]),
            ),
            reverse=True,
        )
        # Cut off branch at last station. In the case of the Circle line, the
        # final station at Edgware Road appears twice in the branch, so use
        # last occurrence of station.
        station_list = sorted_services[0]["stations"]
        # However, Piccadilly line trains stop at Turnham Green in the early
        # morning or late evening, so this station should be removed from the
        # list
        if tfl_line_id == "piccadilly" and TURNHAM_GREEN_ID in station_list:
            station_list.remove(TURNHAM_GREEN_ID)

        # Curtail station list at last station in current branch
        last_station_pos = len(station_list)
        for i in range(len(station_list), 0, -1):
            if station_list[i - 1] == last_station_id:
                last_station_pos = i
                break
        station_list = station_list[:last_station_pos]
        times_between_stations = sorted_services[0]["times"][:last_station_pos - 1]

        # Build connections
        for i in range(len(times_between_stations)):
            from_station_id, to_station_id = station_list[i:i + 2]
            if from_station_id == to_station_id:
                continue
            time = times_between_stations[i]
            services = [service for service in services if to_station_id in service["stations"]]
            train_count = sum([service["n_trains"] for service in services])
            if train_count == 0:
                logger.warning(
                    f"No services between {from_station_id} to {to_station_id} exist within time window. Skipping..."
                )
                break
            connections[(from_station_id, to_station_id, tfl_line_id)] = {
                "graph_id": graph_id,
                "from_station_id": station_map[from_station_id],
                "to_station_id": station_map[to_station_id],
                "line_id": branch_info["line_id"],
                "time": time,
                "interval": round((TOTAL_TIME * 60) / train_count),  # minutes
            }

            if connections.get((to_station_id, from_station_id, tfl_line_id)):
                try:
                    synchronise_journey_and_interval_times(
                        connections=connections,
                        first_station_id=from_station_id,
                        second_station_id=to_station_id,
                        line_id=tfl_line_id,
                    )
                except KeyError as err:
                    logger.error(f"{err}")
                    sys.exit(1)

    return list(connections.values())
