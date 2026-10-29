"""Optional preparation command; never called by a task or its verifier.

Run from the plugin root: uv run python -m plugin.capture config=/path/capture.yaml home=/path/new-capture
"""

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from omegaconf import MISSING
from slimconfig import Config, Folder, Layout, Run, build_output

from contract import FeedSnapshot, NearbyInput
from plugin.nearby import validate_input


def normalize_snapshot(information: dict, status: dict) -> FeedSnapshot:
    """Preserve exactly the fields the task uses; reject unsupported or malformed feeds."""
    if information["version"] != "2.3" or status["version"] != "2.3":
        raise ValueError("capture requires GBFS 2.3 feeds")

    def flag(value):
        if type(value) is bool:
            return value
        if type(value) is int and value in (0, 1):
            return value == 1
        raise ValueError("GBFS rental/installed flags must be booleans or integers 0/1")

    return build_output(
        {
            "source": "citibike-gbfs",
            "information_last_updated": information["last_updated"],
            "status_last_updated": status["last_updated"],
            "station_information": [
                {"station_id": row["station_id"], "name": row["name"], "latitude": row["lat"], "longitude": row["lon"]}
                for row in information["data"]["stations"]
            ],
            "station_status": [
                {
                    "station_id": row["station_id"],
                    "is_installed": flag(row["is_installed"]),
                    "is_renting": flag(row["is_renting"]),
                    "num_bikes_available": row["num_bikes_available"],
                }
                for row in status["data"]["stations"]
            ],
        },
        FeedSnapshot,
    )


def fetch_json(url: str, timeout: float) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"gbfs.citibikenyc.com", "gbfs.lyft.com"}:
        raise ValueError("capture only accepts official Citi Bike HTTPS feed hosts")
    with urlopen(url, timeout=timeout) as response:
        data = response.read(16 * 1024 * 1024 + 1)
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("feed exceeds the 16 MiB capture limit")
    return json.loads(data)


@dataclass
class CaptureConfig(Config):
    longitude: float = MISSING
    latitude: float = MISSING
    discovery_url: str = MISSING
    timeout_seconds: float = MISSING


@dataclass
class CaptureLayout(Layout):
    arguments: NearbyInput
    feeds: Folder


class Capture(Run):
    config: CaptureConfig
    layout: CaptureLayout

    def main(self) -> int:
        cfg = self.config
        if cfg.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        discovery = fetch_json(cfg.discovery_url, cfg.timeout_seconds)
        urls = {feed["name"]: feed["url"] for feed in discovery["data"]["en"]["feeds"]}
        information = fetch_json(urls["station_information"], cfg.timeout_seconds)
        status = fetch_json(urls["station_status"], cfg.timeout_seconds)
        snapshot = normalize_snapshot(information, status)
        arguments = NearbyInput(longitude=cfg.longitude, latitude=cfg.latitude, snapshot=snapshot)
        validate_input(arguments)
        for name, data in (("discovery", discovery), ("station_information", information), ("station_status", status)):
            (Path(self.layout.feeds) / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")
        self.layout.arguments = arguments
        print(f"Captured {len(snapshot.station_information)} stations; arguments.json is the fixed task input.")
        print(
            "Source: Citi Bike official GBFS. Review https://citibikenyc.com/data-sharing-policy before redistribution."
        )
        return 0


if __name__ == "__main__":
    Capture().run()
