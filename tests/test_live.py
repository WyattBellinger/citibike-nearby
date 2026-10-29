import copy
import json
from unittest.mock import patch

import pytest
from slimconfig import build_output

import verifier
from contract import LiveInput, NearbyInput
from plugin.live import capture_live_snapshot, snapshot_path
from plugin.nearby import find_nearby_stations


def capture(arguments, workspace):
    snapshot = arguments["snapshot"]
    info = {
        "version": "2.3",
        "last_updated": snapshot["information_last_updated"],
        "data": {
            "stations": [
                {"station_id": s["station_id"], "name": s["name"], "lat": s["latitude"], "lon": s["longitude"]}
                for s in snapshot["station_information"]
            ]
        },
    }
    status = {
        "version": "2.3",
        "last_updated": snapshot["status_last_updated"],
        "data": {"stations": snapshot["station_status"]},
    }
    discovery = {
        "data": {
            "en": {
                "feeds": [
                    {"name": "station_information", "url": "https://gbfs.lyft.com/info"},
                    {"name": "station_status", "url": "https://gbfs.lyft.com/status"},
                ]
            }
        }
    }
    value = LiveInput(arguments["longitude"], arguments["latitude"])
    with patch("plugin.live.fetch_json", side_effect=[discovery, info, status]) as fetch:
        output = capture_live_snapshot(value, workspace)
        assert fetch.call_count == 3
    return value, output


def test_capture_search_and_independent_verification(arguments, expected, tmp_path):
    value, snapshot = capture(arguments, tmp_path)
    assert {s.station_id for s in snapshot.snapshot.station_information} == {
        "10",
        "2",
        "empty",
        "closed",
        "uninstalled",
    }
    assert verifier.verify_output("get_live_snapshot", value, snapshot, tmp_path)["valid"]
    given = NearbyInput(value.longitude, value.latitude, snapshot.snapshot)
    output = find_nearby_stations(given, tmp_path)
    assert [s.station_id for s in output.stations] == [s["station_id"] for s in expected["stations"]]
    first = verifier.verify_task("find-live-stations", value, output, None, tmp_path)
    assert first["valid"]
    assert first == verifier.verify_task("find-live-stations", value, output, None, tmp_path)
    with patch("plugin.live.fetch_json", side_effect=AssertionError("must not refetch")):
        assert capture_live_snapshot(value, tmp_path) == snapshot


@pytest.mark.parametrize("mutation", ["omit", "count", "invent", "delete_capture", "corrupt_capture", "raw_change"])
def test_live_verifier_rejects_bad_answers_and_missing_evidence(arguments, tmp_path, mutation):
    value, snapshot = capture(arguments, tmp_path)
    output = find_nearby_stations(NearbyInput(value.longitude, value.latitude, snapshot.snapshot), tmp_path)
    if mutation == "omit":
        output.stations.pop()
    elif mutation == "count":
        output.stations[0].num_bikes_available += 1
    elif mutation == "invent":
        output.stations.append(copy.deepcopy(output.stations[0]))
    elif mutation == "delete_capture":
        snapshot_path(value, tmp_path).unlink()
    elif mutation == "corrupt_capture":
        snapshot_path(value, tmp_path).write_text("bad json")
    else:
        path = snapshot_path(value, tmp_path)
        record = json.loads(path.read_text())
        for row in record["status"]["data"]["stations"]:
            row["num_bikes_available"] = 0
        path.write_text(json.dumps(record))
    assert not verifier.verify_task("find-live-stations", value, output, None, tmp_path)["valid"]


def test_snapshot_output_cannot_substitute_data_or_location(arguments, tmp_path):
    value, output = capture(arguments, tmp_path)
    output.snapshot.station_status[0].num_bikes_available += 1
    assert not verifier.verify_output("get_live_snapshot", value, output, tmp_path)["valid"]
    value.latitude += 0.01
    assert not verifier.verify_task("find-live-stations", value, output, None, tmp_path)["valid"]


def test_snapshot_cannot_omit_a_nearby_station(arguments, tmp_path):
    value, output = capture(arguments, tmp_path)
    output.snapshot.station_information.pop()
    output.snapshot.station_status.pop()
    assert not verifier.verify_output("get_live_snapshot", value, output, tmp_path)["valid"]


def test_network_failure_is_an_error_not_an_empty_answer(tmp_path):
    value = LiveInput(-73.989, 40.741)
    with patch("plugin.live.fetch_json", side_effect=OSError("offline")), pytest.raises(OSError, match="offline"):
        capture_live_snapshot(value, tmp_path)
    assert not snapshot_path(value, tmp_path).exists()


@pytest.mark.parametrize("latitude", [float("nan"), float("inf"), 91.0])
def test_invalid_location_does_not_fetch(latitude, tmp_path):
    value = LiveInput(-73.989, latitude)
    assert not verifier.verify_input("get_live_snapshot", value)["valid"]
    with patch("plugin.live.fetch_json") as fetch, pytest.raises(ValueError):
        capture_live_snapshot(value, tmp_path)
    fetch.assert_not_called()


def test_live_contract_needs_no_snapshot():
    assert build_output({"longitude": -73.989, "latitude": 40.741}, LiveInput).latitude == 40.741
