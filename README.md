# NYC Bike Station Finder

A `nanoagent.plugin/v0001` plugin for this task:

> Given longitude and latitude coordinates in New York City and a fixed Citi Bike
> feed snapshot, list every station within 100 yards that is open for rentals and
> has at least one available bike. Return each station's ID, name, coordinates,
> and available-bike count.

## Tools

| Tool | Does | Code |
|---|---|---|
| `find_nearby_stations` | Returns every matching station in the supplied snapshot | `src/plugin/nearby.py` |

### Tasks

| Task | Runner | Success condition |
|---|---|---|
| `find-nearby-stations` | `tool`, with `find_nearby_stations`; reference `null` | Complete list and all fields match the input and rules below |

### Exact specification

- Input: `NearbyInput` in `contract.py`: named `longitude` and `latitude` fields
  and an entire typed `snapshot`. Coordinates are WGS84 decimal degrees. An NYC
  query location is a task precondition; numeric ranges are checked, but
  administrative city membership is not geofenced.
- The normalized snapshot contains station information and status, their separate
  feed timestamps, and an explicit source label. This pair is authoritative even
  if timestamps differ. Historic snapshots are valid; there is no freshness test.
- Join by `station_id`. Both lists require unique, nonempty IDs and identical ID
  sets. Missing counterparts, duplicate IDs, blank names, invalid coordinates,
  negative timestamps, and negative bike counts fail. Two empty lists are valid.
- Open for rentals means `is_installed` and `is_renting` are both true, with
  `num_bikes_available >= 1`. Return availability does not affect bike rental.
  Counts include all available bike types.
- Use Haversine great-circle distance with Earth radius **6,371,008.8 meters**.
  Include distance **<= 91.44 meters**, exactly 100 international yards. Compare
  unrounded binary64 values with no additional radius tolerance.
- Output: `NearbyOutput.stations`, sorted lexicographically by `station_id`,
  without duplicates. Each record contains `station_id`, `name`, `latitude`,
  `longitude`, and `num_bikes_available`, copied exactly from the snapshot.
  No matches means `{"stations": []}`.
- Failures raise exceptions/MCP errors. There are no network calls, writes,
  substitute snapshots, or silent omissions during search or verification.

The host's typed arguments contain the fixed snapshot, so a reference tool is
unnecessary. The `tool` runner computes the result; RUSH's conversational agent
can invoke the task. This evaluates spatial retrieval, not model reasoning.

### Verification

`verifier/nearby.py` independently validates input, joins records, calculates
geographic distances, and compares the entire expected list and every field.
It imports only `math`, never the implementation. Omissions, extras, duplicates,
changed fields, and incorrect ordering fail with score 0. Correct results score 1.

`verifier/__init__.py` defines `verify_input`, `verify_output`, and `verify_task`.
NanoAgent validates types from `contract.py` first, isolates the verifier,
disables networking, and executes it twice to check repeatability. The task needs
no network or filesystem-write permissions, credentials, or environment variables.

## Layout

```text
nanoagent.yaml             Typed manifest, permissions, task and tool registration
contract.py               Every typed input and output declaration
README.md                 Specification and reproducible commands
LICENSE                   MIT license for plugin code
pyproject.toml, uv.lock    Independent package and locked dependencies
.gitignore, .env           Standard exclusions; empty environment requirements
src/plugin/__main__.py    Typed MCP stdio server
src/plugin/nearby.py      Station search and input checks
src/plugin/capture.py     Optional real GBFS capture and normalization command
tests/                    Search, verifier, contract, and capture tests
tests/fixtures/           Synthetic input and handwritten expected output
verifier/                 Independent deterministic checks; Python files only
ui/                       Standard NanoAgent schema renderer
product/                  Marketplace description and original generic bike icon
```

`tests/fixtures/mixed.json` has six **synthetic** stations near a real NYC point;
it is not a historical feed. Expected matches are IDs `10` and `2`, in that
order. Others are outside the radius, empty, closed, or uninstalled. These
fixtures never claim actual availability.

Keep run inputs, validation logs, packages, and report evidence **outside this
repository**. The assignment puts evidence in the report, and the publishing
checker rejects arbitrary extra top-level folders.

## Develop and run

Run commands from this plugin's root. Install Git, uv, and Python 3.12 or newer.
The scaffold requires `requires-python = ">=3.12"`; `uv.lock` pins the resolved
dependencies and SlimConfig Git revision.

```bash
uv sync --frozen --extra dev
uv run --frozen pytest -v
uv run --frozen ruff check .
```

### Run the fixture through NanoAgent

Prepare the adjacent checkout if its environment does not exist:

```bash
uv sync --project ../nanoagent/nanoagent
```

Create an external YAML run configuration. The result folder must be new:

```bash
mkdir -p ../citibike-nearby-evidence
cat > ../citibike-nearby-evidence/fixture.yaml <<EOF
_ > nanoagent.cli.plugin.PluginRunConfig:
plugin: "$PWD"
task: find-nearby-stations
arguments: "$PWD/tests/fixtures/mixed.json"
inputs: []
timeout: 60.0
EOF
uv run --project ../nanoagent/nanoagent nanoagent plugin inspect "$PWD"
uv run --project ../nanoagent/nanoagent nanoagent plugin run \
  config="$PWD/../citibike-nearby-evidence/fixture.yaml" \
  home="$PWD/../citibike-nearby-evidence/fixture-run"
```

A run writes `config.yaml`, `metadata.json`, `run.log`, `result.json`,
`verdict.json`, and `workspace/`. `result.json.output` must equal
`tests/fixtures/expected.json`. The command exits nonzero unless verification
passes. To change coordinates or snapshot, prepare another input JSON and point
the YAML run config's `arguments` at it. Configuration is YAML; JSON files are
typed task data as required by NanoAgent's launcher.

### Capture a real fixed snapshot

The optional helper is a separate preparation command with network access; it
is never called by the installed task or verifier. It discovers official GBFS
2.3 feeds, changes `lat`/`lon` to named fields, and normalizes boolean or integer
0/1 flags. Other flag values fail. Extra GBFS fields unrelated to the task are
excluded from normalized arguments. Raw responses remain with external evidence.

```bash
cat > ../citibike-nearby-evidence/capture.yaml <<'EOF'
_ > plugin.capture.CaptureConfig:
longitude: -73.989
latitude: 40.741
discovery_url: https://gbfs.citibikenyc.com/gbfs/2.3/gbfs.json
timeout_seconds: 30.0
EOF
uv run --frozen python -m plugin.capture \
  config="$PWD/../citibike-nearby-evidence/capture.yaml" \
  home="$PWD/../citibike-nearby-evidence/capture-run"
```

Use `capture-run/arguments.json` as a subsequent task run's `arguments`. Capture
fails on network errors, malformed feeds, unsupported versions, or mismatched ID
sets. It never retries, discards unmatched rows, or uses substitute data. Keep
the same captured arguments for repeatable replay.

### Publication and desktop validation

1. Run tests, lint, inspection, and a task run; preserve logs outside the repo.
2. Push this independent repository to your own public GitHub account. Keep live
   snapshots out of the repository as a standalone dataset.
3. Publish with your authenticated CLI:
   `rush publish https://rush-lab.org https://github.com/YOUR_USERNAME/citibike-nearby`.
4. Install the published plugin in RUSH Lab's desktop app and run the supplied
   synthetic task input. Record its result and displayed verifier verdict.
   The standard page/schema renderer requires no host changes. Changes to
   NanoAgent, the relay, or the page kit require a desktop rebuild and check.
5. Submit its GitHub URL and add the evidence to your milestone report. This
   plugin is one of the five required independent tasks.

To produce an inspected package:

```bash
uv run --project ../nanoagent/nanoagent nanoagent plugin pack \
  "$PWD" "$PWD/../citibike-nearby-evidence/citibike-nearby.tar.gz"
```

### Data and report questions

The code license does not license third-party data. Real captures use
[Citi Bike System Data](https://citibikenyc.com/system-data) and its public
[GBFS discovery feed](https://gbfs.citibikenyc.com/gbfs/2.3/gbfs.json).
Review the [Data Sharing Policy](https://citibikenyc.com/data-sharing-policy)
before redistribution: it allows source material in noncommercial reports/studies
and restricts standalone dataset distribution. The icon is original generic
artwork; there is no operator logo, affiliation, or endorsement.

- **Objective verification:** a precise predicate over fixed typed data and
  complete-list/field comparison decide correctness without a model.
- **Reproducibility:** synthetic fixtures, handwritten expectations, a committed
  lockfile, and YAML run instructions support offline replay. A snapshot's source
  label records provenance claimed by its provider; it is not authentication.
- **Incorrect and boundary outputs:** tests cover missing/malformed values,
  wrong results, omissions, extras, duplicate/unsorted IDs, eligibility, empty
  results, invalid coordinates, and the inclusive radius. Exact-radius arithmetic
  is isolated at the equator; NYC cases cover just inside and outside the boundary.
- **Limitations:** spherical distance differs from walking distance; feed locations
  and counts may be wrong; feed observations are not atomic; changing station sets
  can fail strict capture; historic snapshots are accepted intentionally; NYC city
  membership is a caller precondition; binary64 rounding applies at the boundary.
  Packaging inspection alone proves neither task correctness nor publication.
