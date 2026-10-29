# NYC Bike Station Finder

A `nanoagent.plugin/v0001` plugin that fetches official Citi Bike station data and
finds every station within 100 yards of NYC coordinates that is installed, renting,
and has at least one available bike. A deterministic verifier checks the complete
answer against the captured observations. No API key is required by this plugin;
the host's conversational agent uses its own configured model credentials.

## Tools

| Tool | Purpose |
|---|---|
| `get_live_snapshot` | Fetch official GBFS feeds once per location per task run, save raw observations, and return normalized data for nearby stations |
| `find_nearby_stations` | Calculate the complete matching station list from coordinates and a fixed snapshot |

| Task | Runner | Input |
|---|---|---|
| `find-live-stations` | `agent`, using both tools; reference `null` | Longitude and latitude only; default for current availability |
| `find-nearby-stations` | `tool`, using `find_nearby_stations`; reference `null` | Coordinates and a supplied snapshot; offline replay |

## Use in RUSH Lab

Install/update version 0.2.0, then request:

> Use find-live-stations at latitude 40.7359, longitude -73.9911.

These are approximate coordinates for the Union Square example, not a verified
geocoding result. The agent should never request station data from the user for
this task. It calls `get_live_snapshot`, passes its snapshot and the original
coordinates to `find_nearby_stations`, and submits the resulting station list.
It can inspect the returned data; the verifier decides whether its answer is correct.

This plugin does not geocode addresses or landmarks. If only a place name is
supplied, the agent should ask for coordinates or confirmation of an approximate
location. Queries are within 100 yards of a point, not an entire neighborhood.

Each fresh live task fetches official GBFS 2.3 discovery, station information,
and station status. The tool returns all stations within the search radius,
including closed or empty stations, while retaining the full feeds in the workspace
for independent completeness checks. Repeated snapshot calls for the same coordinates in that run
reuse the saved capture; they do not refresh it. Timestamps describe the feed
observations, not guaranteed availability on arrival. Network or malformed-feed
errors fail explicitly rather than returning a substitute snapshot or empty answer.

## Exact specification

- Coordinates are named `longitude` and `latitude` in WGS84 decimal degrees. NYC
  city membership is a caller precondition; numeric ranges are validated without
  a city boundary geofence.
- Snapshot information and status have separate Unix timestamps and an explicit
  source (`citibike-gbfs` or `synthetic`). The observed pair is authoritative even
  when timestamps differ. Replay accepts historic data without a freshness test.
- Join by `station_id`. Both lists require unique nonempty IDs and identical ID
  sets. Missing counterparts, duplicates, blank names, invalid coordinates,
  negative timestamps, and negative bike counts fail. Two empty lists are valid.
- Eligibility is `is_installed` and `is_renting` and `num_bikes_available >= 1`.
  Return availability does not affect rental eligibility. Counts include all bike types.
- Use Haversine distance with Earth radius **6,371,008.8 meters** and include
  distance **<= 91.44 meters** (100 international yards). Compare unrounded binary64
  values without additional radius tolerance.
- Return `NearbyOutput.stations`, sorted lexicographically by `station_id`, without
  duplicates. Copy `station_id`, `name`, `latitude`, `longitude`, and
  `num_bikes_available` exactly from the snapshot. No matches is `{"stations": []}`.

## Deterministic verification

The verifier uses no model, network, clock, or runtime implementation imports.
For the live task it reads the run's saved raw information/status feeds, normalizes
fields independently, validates the data, independently calculates distances, and
compares every station and field. Missing evidence, omissions, extras, duplicates,
changed fields, or incorrect ordering fail. Snapshot-tool output must also match
these observations exactly. The replay task checks its supplied snapshot directly.
NanoAgent validates contract types, isolates verification, and executes it twice.

The saved capture is evidence produced by trusted plugin code, not a cryptographic
attestation of the external feed. The verifier proves correctness relative to those
observations; it cannot prove provider accuracy, geocoding accuracy, or present-day
availability. The live task exposes no arbitrary file-writing or shell tool to its
agent. Its only writes are capture records within its run workspace.

## Layout

```text
nanoagent.yaml             Typed manifest, network/workspace permissions, tasks/tools
contract.py               Typed input/output declarations
LICENSE                   MIT license for plugin code
pyproject.toml, uv.lock    Independent package and locked dependencies
src/plugin/__main__.py    Typed MCP stdio server
src/plugin/live.py        Run-scoped official capture and snapshot retrieval
src/plugin/capture.py     GBFS normalization and optional external capture command
src/plugin/nearby.py      Station search and input checks
verifier/                 Independent deterministic checks and saved-feed replay
tests/                    Synthetic fixtures, search/capture/verifier tests
ui/                       Standard NanoAgent schema renderer
product/                  Marketplace description and original generic bike icon
```

The live task needs network access only to `gbfs.citibikenyc.com` and
`gbfs.lyft.com`, and write access only to `workspace`. The replay calculation
and verifier perform no network requests. `.env` declares no required variables.

Keep validation logs, report evidence, packages, and captured datasets outside
this repository. The publishing checker rejects arbitrary extra top-level folders.
`tests/fixtures/mixed.json` is synthetic; expected IDs are `10` and `2` in that order.
It is not a historical observation or a claim of current availability.

## Develop and run

Use Python 3.12+, Git, and uv. From this plugin's root:

```bash
uv sync --frozen --extra dev
uv run --frozen pytest -v
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv sync --project ../nanoagent/nanoagent
uv run --project ../nanoagent/nanoagent nanoagent plugin inspect "$PWD"
```

For offline replay, create an external YAML run configuration and a NEW run folder:

```bash
mkdir -p ../citibike-nearby-evidence
cat > ../citibike-nearby-evidence/fixture.yaml <<EOF_CONFIG
_ > nanoagent.cli.plugin.PluginRunConfig:
plugin: "$PWD"
task: find-nearby-stations
arguments: "$PWD/tests/fixtures/mixed.json"
inputs: []
timeout: 60.0
EOF_CONFIG
uv run --project ../nanoagent/nanoagent nanoagent plugin run \
  config="$PWD/../citibike-nearby-evidence/fixture.yaml" \
  home="$PWD/../citibike-nearby-evidence/fixture-replay"
```

The live task additionally needs the host's agent configuration; use the RUSH Lab
UI with its model configured. Its typed task arguments are simply:

```json
{"longitude": -73.9911, "latitude": 40.7359}
```

For an external capture without an agent:

```bash
cat > ../citibike-nearby-evidence/capture.yaml <<'EOF_CONFIG'
_ > plugin.capture.CaptureConfig:
longitude: -73.9911
latitude: 40.7359
discovery_url: https://gbfs.citibikenyc.com/gbfs/2.3/gbfs.json
timeout_seconds: 30.0
EOF_CONFIG
uv run --frozen python -m plugin.capture \
  config="$PWD/../citibike-nearby-evidence/capture.yaml" \
  home="$PWD/../citibike-nearby-evidence/new-capture-run"
```

Use `arguments.json` from this capture as the replay task's input. GBFS integer
0/1 flags normalize to booleans; other flag values and unsupported versions fail.
There are no retries or substitute feeds. Mismatched station ID sets fail strictly.

## Publish and validate in the desktop app

1. Run tests, lint, formatting, inspection, packaging, and task checks; preserve
   evidence outside the repository.
2. Push this independent repository to your public GitHub account.
3. Publish using your authenticated CLI:
   `rush publish https://rush-lab.org https://github.com/YOUR_USERNAME/citibike-nearby`.
4. Update/install version 0.2.0 in RUSH Lab. Run the live task with coordinates,
   confirm no user snapshot is requested, and record the result and verifier verdict.
5. Submit the public GitHub URL and incorporate evidence into your milestone report.

To package:

```bash
uv run --project ../nanoagent/nanoagent nanoagent plugin pack \
  "$PWD" "$PWD/../citibike-nearby-evidence/citibike-nearby-v0.2.0.tar.gz"
```

Existing evidence for version 0.1.0 does not validate this version. Desktop UI
validation and marketplace publication must be recorded separately for 0.2.0.

## Data and limitations

Official sources: [Citi Bike System Data](https://citibikenyc.com/system-data),
[GBFS discovery](https://gbfs.citibikenyc.com/gbfs/2.3/gbfs.json), and
[Data Sharing Policy](https://citibikenyc.com/data-sharing-policy). The MIT code
license does not license third-party data. Review the policy before redistributing
captures; keep live snapshots out of the public code repository.

Spherical distance differs from walking distance; feeds may be inaccurate or
observed at different times; station-set changes may cause strict capture failure;
and binary64 rounding applies at the radius boundary. The icon is original generic
bike artwork, without an operator logo or claim of affiliation.
