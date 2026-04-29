import math
import pytest
import random

from tubechallenge.utils import haversine


@pytest.fixture
def earth_radius() -> int:
    """Returns Earth's radius in metres."""
    return 6_371_000


def test_get_distance__identical_points():
    """Test Haversine distance function returns zero distance for identical
    points.
    """
    centre_lat = 0.0
    centre_lon = 0.0
    periphery_lat = 0.0
    periphery_lon = 0.0

    distance = haversine.get_distance(
        centre_lat, centre_lon, periphery_lat, periphery_lon
    )

    assert distance == 0.0


def test_get_distance__antipodal_points(earth_radius: int):
    """Test Haversine distance function returns maximal distance on sphere,
    which in the case of Earth would be pi * Earth's radius.
    """
    centre_lat = 0.0
    centre_lon = 0.0
    periphery_lat = 0.0
    periphery_lon = math.pi

    distance = haversine.get_distance(
        centre_lat, centre_lon, periphery_lat, periphery_lon
    )

    assert math.isclose(distance, math.pi * earth_radius, rel_tol=1e-6)


def test_get_distance__poles_independent_of_longitude(earth_radius: int):
    """Test Haversine distance function returns correct distances for poles
    irrespective of longitude.
    """
    centre_lat = 0.0
    centre_lon = 0.0

    north_pole_lat = math.pi / 2.0
    north_pole_lon = random.random() * 2.0 * math.pi - math.pi  # (-pi, pi)
    south_pole_lat = -math.pi / 2.0
    south_pole_lon = random.random() * 2.0 * math.pi - math.pi  # (-pi, pi)

    distance_north_pole = haversine.get_distance(
        centre_lat, centre_lon, north_pole_lat, north_pole_lon
    )
    distance_south_pole = haversine.get_distance(
        centre_lat, centre_lon, south_pole_lat, south_pole_lon
    )

    expected_distance = (math.pi / 2.0) * earth_radius
    assert math.isclose(distance_north_pole, expected_distance, rel_tol=1e-6)
    assert math.isclose(distance_south_pole, expected_distance, rel_tol=1e-6)
