import math
from numba import njit
import numpy as np


EARTH_RADIUS = 6_371_000  # radius of Earth in metres
DEG2RAD = math.pi / 180.0
TRAVEL_SPEED = 1000.0  # metres per minute


@njit(cache=True, fastmath=True)
def get_distance(
    phi_1: float, lambda_1: float, phi_2: float, lambda_2: float
) -> float:
    """Find the distance between a pair of points on the surface of a sphere
    using the Haversine formula.

    Args:
        phi_1 (float): latitude coordinate of first point in radians.
        lambda_1 (float): longitude coordinate of first point in radians.
        phi_2 (float): latitude coordinates of second point in radians.
        lambda_2 (float): longitude coordinates of second point in radians.

    Returns:
        Distance between first and second points in metres.
    """
    delta_phi = phi_2 - phi_1
    delta_lambda = lambda_2 - lambda_1

    hav_delta_phi = np.sin(delta_phi * 0.5) ** 2
    hav_delta_lambda = np.sin(delta_lambda * 0.5) ** 2

    # Calculate distance
    h = hav_delta_phi + np.cos(phi_1) * np.cos(phi_2) * hav_delta_lambda

    # Protect against floating point errors
    if h < 0.0:
        h = 0.0
    elif h > 1.0:
        h = 1.0

    return 2.0 * EARTH_RADIUS * np.arcsin(np.sqrt(h))


@njit(cache=True, fastmath=True)
def get_heuristic(
    origin_phi: float,
    origin_lambda: float,
    destination_phi: float,
    destination_lambda: float,
) -> float:
    """Calculate most optimistic travel time between stations.

    Args:
        origin_phi: latitude coordinate of origin station in degrees.
        origin_lambda: longitude coordinate of origin station in degrees.
        destination_phi: latitude coordinate of destination station in degrees.
        destination_lambda: longitude coordinate of destination station in
          degrees.

    Returns:
        Travel time between origin and destination stations in minutes.
    """
    phi_1 = origin_phi * DEG2RAD
    lambda_1 = origin_lambda * DEG2RAD
    phi_2 = destination_phi * DEG2RAD
    lambda_2 = destination_lambda * DEG2RAD

    distance = get_distance(phi_1, lambda_1, phi_2, lambda_2)

    return int(distance / TRAVEL_SPEED + 0.5)


def get_bounding_box(
    latitude: float, longitude: float, bb_side: float
) -> tuple[float, float, float, float]:
    """Get boundaries of bounding box in latitude and longitude coordinates in
    degrees.

    Args:
        latitude (float): latitude coordinate of centre of bounding box.
        longitude (float): longitude coordinate of centre of bounding box.
        bb_side (float): length of side of bounding box in metres.

    Returns:
        tuple of bounding box boundaries in degrees.
    """
    delta_phi = (bb_side * 0.5 / EARTH_RADIUS) / DEG2RAD
    delta_lambda = delta_phi / math.cos(latitude * DEG2RAD)

    phi_min = latitude - delta_phi
    phi_max = latitude + delta_phi
    lambda_min = longitude - delta_lambda
    lambda_max = longitude + delta_lambda

    return phi_min, phi_max, lambda_min, lambda_max
