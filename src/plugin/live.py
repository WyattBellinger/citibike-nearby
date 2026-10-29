"""Capture once per location and run; expose the same data to the task agent."""

import hashlib
import json
import math
from pathlib import Path

from slimconfig import build_output, plain_output

from contract import FeedSnapshot, LiveInput, LiveSnapshotOutput, NearbyInput
from plugin.capture import fetch_json, normalize_snapshot
from plugin.nearby import distance_meters, validate_input

DISCOVERY_URL = "https://gbfs.citibikenyc.com/gbfs/2.3/gbfs.json"


def snapshot_path(value: LiveInput, workspace: Path) -> Path:
    key = json.dumps([value.longitude, value.latitude], allow_nan=False)
    return workspace / ("live-" + hashlib.sha256(key.encode()).hexdigest() + ".json")


def capture_live_snapshot(value: LiveInput, workspace: Path) -> LiveSnapshotOutput:
    if not (
        math.isfinite(value.latitude)
        and math.isfinite(value.longitude)
        and -90 <= value.latitude <= 90
        and -180 <= value.longitude <= 180
    ):
        raise ValueError("query coordinates must be finite WGS84 values")
    path = snapshot_path(value, workspace)
    if path.exists():
        return get_live_snapshot(value, workspace)
    discovery = fetch_json(DISCOVERY_URL, 15.0)
    urls = {feed["name"]: feed["url"] for feed in discovery["data"]["en"]["feeds"]}
    information = fetch_json(urls["station_information"], 15.0)
    status = fetch_json(urls["station_status"], 15.0)
    snapshot = normalize_snapshot(information, status)
    validate_input(NearbyInput(value.longitude, value.latitude, snapshot))
    # Keep the full raw feeds as evidence, but avoid sending thousands of distant
    # stations through the model's context and back into a tool call.
    nearby = [
        row
        for row in snapshot.station_information
        if distance_meters(value.latitude, value.longitude, row.latitude, row.longitude) <= 91.44
    ]
    identifiers = {row.station_id for row in nearby}
    snapshot = FeedSnapshot(
        snapshot.source,
        snapshot.information_last_updated,
        snapshot.status_last_updated,
        nearby,
        [row for row in snapshot.station_status if row.station_id in identifiers],
    )
    output = LiveSnapshotOutput(value.longitude, value.latitude, snapshot)
    # Keep the source observations with the normalized snapshot for replay/audit.
    record = {"output": plain_output(output), "discovery": discovery, "information": information, "status": status}
    with path.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, allow_nan=False)
    return output


def get_live_snapshot(value: LiveInput, workspace: Path) -> LiveSnapshotOutput:
    """Read the pinned capture. Never fetch again or substitute other data."""
    record = json.loads(snapshot_path(value, workspace).read_text(encoding="utf-8"))
    output = build_output(record["output"], LiveSnapshotOutput)
    if output.longitude != value.longitude or output.latitude != value.latitude:
        raise ValueError("saved snapshot belongs to a different query")
    validate_input(NearbyInput(output.longitude, output.latitude, output.snapshot))
    return output
