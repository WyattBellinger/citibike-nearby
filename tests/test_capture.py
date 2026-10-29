import copy
from unittest.mock import patch

import pytest

from plugin.capture import fetch_json, normalize_snapshot


def raw_feeds():
    info = {
        "version": "2.3",
        "last_updated": 100,
        "data": {
            "stations": [
                {"station_id": "a", "name": "Synthetic", "lat": 40.741, "lon": -73.989, "capacity": 20},
            ]
        },
    }
    status = {
        "version": "2.3",
        "last_updated": 110,
        "data": {
            "stations": [
                {"station_id": "a", "is_installed": 1, "is_renting": 1, "num_bikes_available": 2, "is_returning": 0},
            ]
        },
    }
    return info, status


def test_normalization_preserves_task_fields_and_timestamps():
    information, status = raw_feeds()
    before = copy.deepcopy((information, status))
    snapshot = normalize_snapshot(information, status)
    assert snapshot.source.value == "citibike-gbfs"
    assert snapshot.information_last_updated == 100
    assert snapshot.status_last_updated == 110
    assert snapshot.station_information[0].name == "Synthetic"
    assert snapshot.station_status[0].num_bikes_available == 2
    assert snapshot.station_status[0].is_renting is True
    assert (information, status) == before


@pytest.mark.parametrize("flag", ["1", 2, -1, None])
def test_bad_flags_are_not_coerced(flag):
    information, status = raw_feeds()
    status["data"]["stations"][0]["is_renting"] = flag
    with pytest.raises(ValueError):
        normalize_snapshot(information, status)


def test_unsupported_feed_version_fails():
    information, status = raw_feeds()
    information["version"] = "3.0"
    with pytest.raises(ValueError, match="2.3"):
        normalize_snapshot(information, status)


def test_missing_status_field_fails():
    information, status = raw_feeds()
    del status["data"]["stations"][0]["num_bikes_available"]
    with pytest.raises(KeyError):
        normalize_snapshot(information, status)


def test_feed_errors_propagate_without_a_substitute():
    with (
        patch("plugin.capture.urlopen", side_effect=OSError("network unavailable")),
        pytest.raises(OSError, match="network unavailable"),
    ):
        fetch_json("https://gbfs.citibikenyc.com/gbfs/2.3/gbfs.json", 10)


def test_unofficial_feed_host_is_rejected():
    with pytest.raises(ValueError, match="official"):
        fetch_json("https://example.org/feed.json", 10)
