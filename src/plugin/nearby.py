"""Station search. The verifier implements its own checks and calculation."""

import math
from pathlib import Path

from contract import AvailableStation, NearbyInput, NearbyOutput

EARTH_RADIUS_METERS = 6_371_008.8
SEARCH_RADIUS_METERS = 91.44


def validate_input(value: NearbyInput) -> None:
    def coordinates(latitude: float, longitude: float) -> bool:
        return (
            math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180
        )

    if not coordinates(value.latitude, value.longitude):
        raise ValueError("query coordinates must be finite WGS84 latitude/longitude")
    snapshot = value.snapshot
    if snapshot.information_last_updated < 0 or snapshot.status_last_updated < 0:
        raise ValueError("feed timestamps must be nonnegative Unix seconds")
    information_ids = set()
    for station in snapshot.station_information:
        if not station.station_id.strip() or station.station_id in information_ids:
            raise ValueError("station information IDs must be nonempty and unique")
        if not station.name.strip() or not coordinates(station.latitude, station.longitude):
            raise ValueError("station names must be nonempty and coordinates must be finite WGS84 values")
        information_ids.add(station.station_id)
    status_ids = set()
    for status in snapshot.station_status:
        if not status.station_id.strip() or status.station_id in status_ids:
            raise ValueError("station status IDs must be nonempty and unique")
        if status.num_bikes_available < 0:
            raise ValueError("available-bike counts must be nonnegative")
        status_ids.add(status.station_id)
    if information_ids != status_ids:
        raise ValueError("station information and status must have identical station ID sets")


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    half_lat = math.radians(lat2 - lat1) / 2
    half_lon = math.radians(lon2 - lon1) / 2
    haversine = math.sin(half_lat) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(half_lon) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(min(1.0, max(0.0, haversine))))


def find_nearby_stations(value: NearbyInput, workspace: Path) -> NearbyOutput:
    validate_input(value)
    statuses = {station.station_id: station for station in value.snapshot.station_status}
    matches = []
    for station in value.snapshot.station_information:
        status = statuses[station.station_id]
        if not (status.is_installed and status.is_renting and status.num_bikes_available >= 1):
            continue
        distance = distance_meters(value.latitude, value.longitude, station.latitude, station.longitude)
        if distance <= SEARCH_RADIUS_METERS:
            matches.append(
                AvailableStation(
                    station_id=station.station_id,
                    name=station.name,
                    latitude=station.latitude,
                    longitude=station.longitude,
                    num_bikes_available=status.num_bikes_available,
                )
            )
    return NearbyOutput(stations=sorted(matches, key=lambda station: station.station_id))
