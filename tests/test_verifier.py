import copy
import math

import pytest
from slimconfig import build_output

import verifier
from contract import NearbyInput, NearbyOutput
from plugin.nearby import find_nearby_stations


def task_verdict(arguments, output):
    return verifier.verify_task(
        "find-nearby-stations", build_output(arguments, NearbyInput), build_output(output, NearbyOutput), None, "unused"
    )


def test_accepts_handwritten_correct_result(arguments, expected):
    assert task_verdict(arguments, expected)["valid"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "empty",
        "extra",
        "duplicate",
        "order",
        "name",
        "latitude",
        "longitude",
        "count",
        "invented",
        "nonfinite",
    ],
)
def test_rejects_incorrect_result(arguments, expected, mutation):
    if mutation == "missing":
        expected["stations"].pop()
    elif mutation == "empty":
        expected["stations"] = []
    elif mutation == "extra":
        expected["stations"].append({**expected["stations"][0], "station_id": "far"})
    elif mutation == "duplicate":
        expected["stations"].append(copy.deepcopy(expected["stations"][0]))
    elif mutation == "order":
        expected["stations"].reverse()
    elif mutation == "name":
        expected["stations"][0]["name"] = "Fabricated station"
    elif mutation == "latitude":
        expected["stations"][0]["latitude"] += 0.001
    elif mutation == "longitude":
        expected["stations"][0]["longitude"] += 0.001
    elif mutation == "count":
        expected["stations"][0]["num_bikes_available"] += 1
    elif mutation == "invented":
        expected["stations"][0]["station_id"] = "invented"
    else:
        expected["stations"][0]["latitude"] = float("nan")
    assert not task_verdict(arguments, expected)["valid"]


@pytest.mark.parametrize("identifier", ["empty", "closed", "uninstalled", "far"])
def test_ineligible_station_cannot_be_added(arguments, expected, identifier):
    info = next(row for row in arguments["snapshot"]["station_information"] if row["station_id"] == identifier)
    status = next(row for row in arguments["snapshot"]["station_status"] if row["station_id"] == identifier)
    expected["stations"].append({**info, "num_bikes_available": status["num_bikes_available"]})
    expected["stations"].sort(key=lambda row: row["station_id"])
    assert not task_verdict(arguments, expected)["valid"]


@pytest.mark.parametrize(
    "mutation",
    [
        "nan",
        "infinity",
        "latitude",
        "longitude",
        "duplicate_information",
        "duplicate_status",
        "missing_status",
        "extra_status",
        "negative_count",
        "empty_name",
        "empty_id",
        "station_coordinates",
        "negative_timestamp",
    ],
)
def test_invalid_inputs_fail_runtime_and_verifier(arguments, tmp_path, mutation):
    snapshot = arguments["snapshot"]
    if mutation == "nan":
        arguments["latitude"] = float("nan")
    elif mutation == "infinity":
        arguments["longitude"] = float("inf")
    elif mutation == "latitude":
        arguments["latitude"] = 91.0
    elif mutation == "longitude":
        arguments["longitude"] = -181.0
    elif mutation == "duplicate_information":
        snapshot["station_information"].append(copy.deepcopy(snapshot["station_information"][0]))
    elif mutation == "duplicate_status":
        snapshot["station_status"].append(copy.deepcopy(snapshot["station_status"][0]))
    elif mutation == "missing_status":
        snapshot["station_status"].pop()
    elif mutation == "extra_status":
        snapshot["station_status"].append({**snapshot["station_status"][0], "station_id": "unknown"})
    elif mutation == "negative_count":
        snapshot["station_status"][0]["num_bikes_available"] = -1
    elif mutation == "empty_name":
        snapshot["station_information"][0]["name"] = " "
    elif mutation == "empty_id":
        snapshot["station_information"][0]["station_id"] = ""
    elif mutation == "station_coordinates":
        snapshot["station_information"][0]["longitude"] = float("nan")
    else:
        snapshot["status_last_updated"] = -1
    given = build_output(arguments, NearbyInput)
    assert not verifier.verify_input("find_nearby_stations", given)["valid"]
    assert not verifier.verify_task("find-nearby-stations", given, NearbyOutput(stations=[]), None, "unused")["valid"]
    with pytest.raises(ValueError):
        find_nearby_stations(given, tmp_path)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_snapshot",
        "extra_key",
        "string_coordinate",
        "bool_coordinate",
        "missing_count",
        "float_count",
        "bool_count",
        "int_flag",
        "unknown_source",
    ],
)
def test_contract_rejects_malformed_input(arguments, mutation):
    if mutation == "missing_snapshot":
        del arguments["snapshot"]
    elif mutation == "extra_key":
        arguments["radius"] = 100
    elif mutation == "string_coordinate":
        arguments["latitude"] = "40.741"
    elif mutation == "bool_coordinate":
        arguments["latitude"] = True
    elif mutation == "missing_count":
        del arguments["snapshot"]["station_status"][0]["num_bikes_available"]
    elif mutation == "float_count":
        arguments["snapshot"]["station_status"][0]["num_bikes_available"] = 1.5
    elif mutation == "bool_count":
        arguments["snapshot"]["station_status"][0]["num_bikes_available"] = True
    elif mutation == "int_flag":
        arguments["snapshot"]["station_status"][0]["is_renting"] = 1
    else:
        arguments["snapshot"]["source"] = "unknown"
    with pytest.raises(ValueError):
        build_output(arguments, NearbyInput)


@pytest.mark.parametrize("output", [None, {}, {"stations": None}, {"stations": [{}]}, {"stations": [], "ok": True}])
def test_contract_rejects_missing_or_malformed_output(output):
    with pytest.raises(ValueError):
        build_output(output, NearbyOutput)


def test_verification_is_repeatable(arguments, expected):
    assert task_verdict(arguments, expected) == task_verdict(arguments, expected)


def test_all_entrypoints_apply_the_same_check(arguments, expected):
    given = build_output(arguments, NearbyInput)
    made = build_output(expected, NearbyOutput)
    assert verifier.verify_input("find_nearby_stations", given)["valid"]
    assert verifier.verify_output("find_nearby_stations", given, made, "unused")["valid"]
    assert not verifier.verify_input("unknown", given)["valid"]
    assert not verifier.verify_output("unknown", given, made, "unused")["valid"]
    assert not verifier.verify_task("unknown", given, made, None, "unused")["valid"]


def test_inclusive_exact_boundary():
    # A controlled equatorial case isolates the inclusive floating-point threshold.
    edge = math.degrees(91.44 / 6371008.8)
    arguments = {
        "latitude": 0.0,
        "longitude": 0.0,
        "snapshot": {
            "source": "synthetic",
            "information_last_updated": 0,
            "status_last_updated": 0,
            "station_information": [{"station_id": "edge", "name": "Boundary", "latitude": edge, "longitude": 0.0}],
            "station_status": [
                {"station_id": "edge", "is_installed": True, "is_renting": True, "num_bikes_available": 1}
            ],
        },
    }
    expected = {"stations": [{**arguments["snapshot"]["station_information"][0], "num_bikes_available": 1}]}
    assert task_verdict(arguments, expected)["valid"]
    assert not task_verdict(arguments, {"stations": []})["valid"]


def test_empty_answer_is_valid_only_when_expected(arguments):
    arguments["snapshot"]["station_information"] = []
    arguments["snapshot"]["station_status"] = []
    assert task_verdict(arguments, {"stations": []})["valid"]
