"""Independent replay of the saved official observations, with no network or clock."""

import hashlib
import json
from pathlib import Path

from contract import FeedSnapshot, NearbyInput, SnapshotSource, StationInformation, StationStatus

from .nearby import check_input, check_result, distance_meters, valid_coordinates, verdict


def check_live_input(value):
    return verdict(valid_coordinates(value.latitude, value.longitude), "query must have finite WGS84 coordinates")


def saved_arguments(value, workspace):
    key = json.dumps([value.longitude, value.latitude], allow_nan=False)
    path = Path(workspace) / ("live-" + hashlib.sha256(key.encode()).hexdigest() + ".json")
    record = json.loads(path.read_text(encoding="utf-8"))
    information, status = record["information"], record["status"]
    if information["version"] != "2.3" or status["version"] != "2.3":
        raise ValueError("saved feeds must be GBFS 2.3")

    def flag(value):
        if type(value) is bool:
            return value
        if type(value) is int and value in (0, 1):
            return value == 1
        raise ValueError("invalid saved feed flag")

    snapshot = FeedSnapshot(
        source=SnapshotSource.CITIBIKE_GBFS,
        information_last_updated=information["last_updated"],
        status_last_updated=status["last_updated"],
        station_information=[
            StationInformation(row["station_id"], row["name"], row["lat"], row["lon"])
            for row in information["data"]["stations"]
        ],
        station_status=[
            StationStatus(
                row["station_id"], flag(row["is_installed"]), flag(row["is_renting"]), row["num_bikes_available"]
            )
            for row in status["data"]["stations"]
        ],
    )
    return NearbyInput(value.longitude, value.latitude, snapshot)


def check_live_result(value, output, workspace, snapshot_output=False):
    checked = check_live_input(value)
    if not checked["valid"]:
        return checked
    try:
        arguments = saved_arguments(value, workspace)
        if snapshot_output:
            checked = check_input(arguments)
            if not checked["valid"]:
                return checked
            snapshot = arguments.snapshot
            nearby = [
                row
                for row in snapshot.station_information
                if distance_meters(value.latitude, value.longitude, row) <= 91.44
            ]
            identifiers = {row.station_id for row in nearby}
            expected = FeedSnapshot(
                snapshot.source,
                snapshot.information_last_updated,
                snapshot.status_last_updated,
                nearby,
                [row for row in snapshot.station_status if row.station_id in identifiers],
            )
            return verdict(
                output.longitude == value.longitude
                and output.latitude == value.latitude
                and output.snapshot == expected,
                "snapshot must exactly match the saved source feeds and requested coordinates",
            )
        return check_result(arguments, output)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return verdict(False, "missing or malformed saved live capture")
