import math

from sqlalchemy.orm import Session

from tubechallenge.db import station
from tubechallenge.db.tables import Connection
from tubechallenge.utils.haversine import get_bounding_box, get_distance

DEG2RAD = math.pi / 180.0


def get_running_connections(
    graph_id: int, run_line_id: int, session: Session
) -> list[Connection]:
    """Estimate time taken to run between two stations within a local region.
    Regions are restricted to vicinity of tube stations.

    Args:
        graph_id (int): related graph ID.
        run_line_id (int): ID for line that represents running between stations.
        session (Session): database session.

    Returns:
        list of running routes between stations.
    """
    connections = {}

    # Get all tube stations
    tube_statons = station.get_many(
        graph_id=graph_id, is_tube=True, session=session
    )

    bb_side = 2700.0 / 1.3  # more realistic distance in curvy city streets (km)
    running_speed = 170.0  # metres per minute
    for tube_station in tube_stations:
        lat_min, lat_max, lon_min, lon_max = get_bounding_box(
            tube_station.latitude, tube_station.longitude, bb_side
        )
        stations_in_range = station.get_many(
            graph_id=graph_id,
            latitude_min=lat_min,
            latitude_max=lat_max,
            longitude_min=lon_min,
            longitude_max=lon_max,
            session=session,
        )

        for stn in stations_in_range:
            if stn.id == tube_station.id:
                continue

            distance = get_distance(
                phi_1=stn.latitude * DEG2RAD,
                lambda_1=stn.longitude * DEG2RAD,
                phi_2=tube_station.latitude * DEG2RAD,
                lambda_2=tube_station.longitude * DEG2RAD,
            )
            if distance <= bb_side:
                if not connections.get((tube_station.id, stn.id)):
                    connections[(tube_station.id, stn.id)] = {
                        "graph_id": graph_id,
                        "from_station_id": tube_station.id,
                        "to_station_id": stn.id,
                        "line_id": run_line_id,
                        "time": math.ceil(distance / running_speed),
                        "interval": 0,
                    }
                    connections[(stn.id, tube_station.id)] = {
                        "graph_id": graph_id,
                        "from_station_id": stn.id,
                        "to_station_id": tube_station.id,
                        "line_id": run_line_id,
                        "time": math.ceil(distance / running_speed),
                        "interval": 0,
                    }

    return list(connections.values())
