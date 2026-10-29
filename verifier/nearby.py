"""Independent deterministic oracle over the host-supplied task input."""

import math


def verdict(valid, message, **details):
    return {"valid": valid, "score": float(valid), "message": message, "details": details}


def valid_coordinates(latitude, longitude):
    return math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180


def check_input(value):
    if not valid_coordinates(value.latitude, value.longitude):
        return verdict(False, "query coordinates must be finite WGS84 values")
    snapshot = value.snapshot
    if snapshot.information_last_updated < 0 or snapshot.status_last_updated < 0:
        return verdict(False, "feed timestamps must be nonnegative")
    information = snapshot.station_information
    statuses = snapshot.station_status
    information_ids = [station.station_id for station in information]
    status_ids = [station.station_id for station in statuses]
    for identifiers in (information_ids, status_ids):
        if any(not identifier.strip() for identifier in identifiers) or len(identifiers) != len(set(identifiers)):
            return verdict(False, "station IDs must be nonempty and unique in each feed")
    if set(information_ids) != set(status_ids):
        return verdict(False, "station information and status IDs do not match")
    if any(not station.name.strip() for station in information):
        return verdict(False, "station names must be nonempty")
    if any(not valid_coordinates(station.latitude, station.longitude) for station in information):
        return verdict(False, "station coordinates must be finite WGS84 values")
    if any(status.num_bikes_available < 0 for status in statuses):
        return verdict(False, "available-bike counts must be nonnegative")
    return verdict(True, "input is valid")


def check_result(arguments, output):
    checked = check_input(arguments)
    if not checked["valid"]:
        return checked
    information = {station.station_id: station for station in arguments.snapshot.station_information}
    expected = {}
    for status in arguments.snapshot.station_status:
        if not status.is_installed or not status.is_renting or status.num_bikes_available == 0:
            continue
        station = information[status.station_id]
        a = math.sin(math.radians(station.latitude - arguments.latitude) / 2) ** 2
        a += (
            math.cos(math.radians(arguments.latitude))
            * math.cos(math.radians(station.latitude))
            * math.sin(math.radians(station.longitude - arguments.longitude) / 2) ** 2
        )
        distance = 12_742_017.6 * math.asin(math.sqrt(max(0.0, min(1.0, a))))
        if distance <= 91.44:
            expected[status.station_id] = (
                station.name,
                station.latitude,
                station.longitude,
                status.num_bikes_available,
            )
    submitted_ids = [station.station_id for station in output.stations]
    if submitted_ids != sorted(expected):
        return verdict(
            False,
            "station IDs must be the complete matching list, sorted without duplicates",
            expected_ids=sorted(expected),
            submitted_ids=submitted_ids,
        )
    for station in output.stations:
        actual = (station.name, station.latitude, station.longitude, station.num_bikes_available)
        if actual != expected[station.station_id]:
            return verdict(False, "station fields differ from the supplied snapshot", station_id=station.station_id)
    return verdict(True, "all and only qualifying stations match the snapshot", station_count=len(expected))
