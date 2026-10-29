"""The complete task input, including its immutable normalized GBFS snapshot."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    FIND_NEARBY_STATIONS = "find_nearby_stations"
    GET_LIVE_SNAPSHOT = "get_live_snapshot"


class Task(Enum):
    FIND_NEARBY_STATIONS = "find-nearby-stations"
    FIND_LIVE_STATIONS = "find-live-stations"


class SnapshotSource(Enum):
    SYNTHETIC = "synthetic"
    CITIBIKE_GBFS = "citibike-gbfs"


@dataclass
class StationInformation(Output):
    station_id: str
    name: str
    latitude: float
    longitude: float


@dataclass
class StationStatus(Output):
    station_id: str
    is_installed: bool
    is_renting: bool
    num_bikes_available: int


@dataclass
class FeedSnapshot(Output):
    source: Annotated[SnapshotSource, "Synthetic fixture or data from Citi Bike's official GBFS feed"]
    information_last_updated: Annotated[int, "station_information timestamp, Unix seconds"]
    status_last_updated: Annotated[int, "station_status timestamp, Unix seconds"]
    station_information: list[StationInformation]
    station_status: list[StationStatus]


@dataclass
class NearbyInput(Output):
    longitude: Annotated[float, "Query longitude in WGS84 decimal degrees; query location is in NYC"]
    latitude: Annotated[float, "Query latitude in WGS84 decimal degrees; query location is in NYC"]
    snapshot: Annotated[FeedSnapshot, "Fixed snapshot, supplied in full and never refreshed during the task"]


@dataclass
class LiveInput(Output):
    longitude: Annotated[float, "Query longitude in WGS84 decimal degrees; query location is in NYC"]
    latitude: Annotated[float, "Query latitude in WGS84 decimal degrees; query location is in NYC"]


@dataclass
class LiveSnapshotOutput(Output):
    longitude: float
    latitude: float
    snapshot: Annotated[
        FeedSnapshot,
        "Captured stations within 100 yards, including closed/empty stations; full feeds retained for verification",
    ]


@dataclass
class AvailableStation(Output):
    station_id: str
    name: str
    latitude: float
    longitude: float
    num_bikes_available: int


@dataclass
class NearbyOutput(Output):
    stations: Annotated[list[AvailableStation], "All qualifying stations, sorted lexicographically by station_id"]


TOOLS = {
    Tool.FIND_NEARBY_STATIONS: (NearbyInput, NearbyOutput),
    Tool.GET_LIVE_SNAPSHOT: (LiveInput, LiveSnapshotOutput),
}
TASKS = {
    Task.FIND_NEARBY_STATIONS: (NearbyInput, NearbyOutput),
    Task.FIND_LIVE_STATIONS: (LiveInput, NearbyOutput),
}
