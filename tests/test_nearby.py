import copy
import math

import pytest
from slimconfig import build_output, plain_output

from contract import NearbyInput
from plugin.nearby import distance_meters, find_nearby_stations


def test_mixed_fixture_matches_handwritten_expected(arguments, expected, tmp_path):
    given = build_output(arguments, NearbyInput)
    assert plain_output(find_nearby_stations(given, tmp_path)) == expected
    assert not list(tmp_path.iterdir())


def test_no_matches(arguments, tmp_path):
    arguments["longitude"] = -74.01
    assert find_nearby_stations(build_output(arguments, NearbyInput), tmp_path).stations == []


def test_empty_feed_is_a_valid_snapshot(arguments, tmp_path):
    arguments["snapshot"]["station_information"] = []
    arguments["snapshot"]["station_status"] = []
    assert find_nearby_stations(build_output(arguments, NearbyInput), tmp_path).stations == []


def test_feed_order_does_not_change_result(arguments, expected, tmp_path):
    arguments["snapshot"]["station_information"].reverse()
    arguments["snapshot"]["station_status"].reverse()
    assert plain_output(find_nearby_stations(build_output(arguments, NearbyInput), tmp_path)) == expected


@pytest.mark.parametrize("offset, included", [(91.439, True), (91.441, False)])
def test_nyc_radius_boundary(arguments, tmp_path, offset, included):
    arguments["snapshot"]["station_information"] = [
        {
            "station_id": "edge",
            "name": "Synthetic boundary",
            "latitude": arguments["latitude"] + math.degrees(offset / 6371008.8),
            "longitude": arguments["longitude"],
        }
    ]
    arguments["snapshot"]["station_status"] = [
        {
            "station_id": "edge",
            "is_installed": True,
            "is_renting": True,
            "num_bikes_available": 1,
        }
    ]
    result = find_nearby_stations(build_output(arguments, NearbyInput), tmp_path)
    assert bool(result.stations) is included


def test_exact_radius_in_distance_kernel():
    # At the equator this construction avoids subtracting two large latitudes.
    edge = math.degrees(91.44 / 6371008.8)
    assert distance_meters(0, 0, edge, 0) == 91.44
    assert distance_meters(0, 0, 0, edge) == 91.44


def test_great_circle_geometry():
    assert distance_meters(40.74, -73.99, 40.74, -73.99) == 0
    assert distance_meters(0, 0, 0, 90) == pytest.approx(math.pi * 6371008.8 / 2)
    assert math.isfinite(distance_meters(0, 0, 0, 180))


def test_snapshot_is_not_modified(arguments, tmp_path):
    given = build_output(arguments, NearbyInput)
    before = copy.deepcopy(plain_output(given))
    find_nearby_stations(given, tmp_path)
    assert plain_output(given) == before
