# MapTool Sync Integration

DMA currently includes an experimental MapTool adapter, but the transport assumption behind it is not verified against a stock local MapTool install.

Recent local validation on macOS showed that starting a normal MapTool server from
`File -> Start Server...` produces an `rptools-maptool+tcp://...` connection URI for MapTool
clients, not a documented HTTP REST API. That means the current DMA adapter should be treated as
placeholder code until we define a real bridge.

What we verified locally:

- MapTool's game server uses a TCP client connection URI such as `rptools-maptool+tcp://host:port/`
- the game-server port is not an HTTP endpoint that DMA can `curl`
- the stock app did not expose a confirmed `/auth/login` or `/maps/{id}` REST surface during testing

What remains true in the repo:

- the Phase 4 DM panel and live mechanics snapshot model are still useful target UX
- the current adapter code and `/api/maptool` routes can serve as a contract draft for a future bridge
- the actual transport still needs to be implemented against real MapTool behavior

The normalized token shape now preserves optional mechanics fields as well:

- `hp_current`
- `hp_max`
- `initiative`
- `conditions`

That lets the Phase 4 DM panel show a read-only combat snapshot after a sync.

## Configuration

If you experiment with a custom HTTP bridge or sidecar, DMA uses these environment variables:

- `MAPTOOL_BASE_URL`: Base URL for the experimental HTTP bridge expected by DMA.
- `MAPTOOL_USERNAME` and `MAPTOOL_PASSWORD`: Credentials used when an `Authorization` header is not supplied by the caller.
- `MAPTOOL_TIMEOUT_SECONDS`: Request timeout in seconds (default `10`).
- `MAPTOOL_MAX_RETRIES`: Maximum attempts for a MapTool request before surfacing an error (default `3`).

Example `.env` snippet for a future bridge:

```bash
MAPTOOL_BASE_URL=http://localhost:5000/api
MAPTOOL_USERNAME=gm
MAPTOOL_PASSWORD=change-me
MAPTOOL_TIMEOUT_SECONDS=10
MAPTOOL_MAX_RETRIES=3
```

Do not point `MAPTOOL_BASE_URL` at a normal MapTool `rptools-maptool+tcp://...` server URI or at
the raw port from `Start Server...`. That port is for MapTool clients, not DMA's HTTP adapter.

## Current Status

Right now the repo has:

1. a live-session UX target in the DM panel
2. an experimental HTTP adapter contract in code
3. no verified stock-MapTool HTTP endpoint that satisfies that contract

Because of that, `/api/maptool/*` and `/api/live/maptool-sync` should currently be treated as
integration scaffolding rather than production-ready MapTool support.

## Recommended Next Steps

The most realistic integration options now look like:

1. build a MapTool plugin or macro bridge that exports scene/token/combat state to DMA
2. build a local sidecar that talks to MapTool over its real transport and exposes HTTP to DMA
3. pivot the short-term integration to campaign exports, logs, or other file-based sync instead of live socket integration

## Recommended Bridge Design

The most practical path for this repo is:

1. keep DMA's existing HTTP contract
2. add a small local bridge process that MapTool can call into or write to
3. let that bridge normalize MapTool state into DMA's existing `CampaignMapState` shape

In other words:

- MapTool remains the source of truth for the live table
- the bridge becomes the translation layer
- DMA stays an HTTP consumer and does not need to speak MapTool's native transport directly

### Why This Path Fits Best

A direct DMA-to-MapTool transport implementation would couple the backend tightly to MapTool's
runtime details and make testing much harder. A bridge keeps the DMA app clean and lets us:

- preserve the current `/api/maptool/*` and `/api/live/maptool-sync` route shapes
- test the bridge and DMA independently
- swap transport strategies later without rewriting the DM panel
- support a file or push-based fallback if full live sync proves awkward

### Proposed Architecture

The proposed components are:

1. `MapTool`
   The GM's running VTT session and campaign state.
2. `maptool-bridge`
   A small local helper that either:
   - receives pushed state from a MapTool macro/plugin, or
   - reads exported files/snapshots from a watched folder.
3. `DMA backend`
   Continues to call an HTTP endpoint expecting normalized map payloads.

Recommended flow:

1. the GM triggers a `Sync to DMA` macro or plugin action inside MapTool
2. MapTool exports current map/token/combat state to the local bridge
3. the bridge converts that payload into DMA's normalized schema
4. DMA pulls from the bridge through the existing adapter contract
5. DMA stores the snapshot in live context and updates the DM panel

### Bridge Transport Options

The bridge can be built in stages.

#### Option A: Push JSON From MapTool

Best first milestone.

- Add a MapTool macro or plugin command that exports:
  - current map id/name
  - visible tokens
  - token coordinates
  - notes and GM notes when available
  - initiative when available
  - conditions and HP when available
- Send that JSON to a local bridge endpoint such as:
  - `POST /bridge/map-state`
- The bridge caches the most recent snapshot per map and exposes:
  - `GET /maps/{map_id}`

This is the lowest-risk route because DMA does not need to understand MapTool's native server
protocol.

#### Option B: File Export + Watcher

Best fallback if HTTP from MapTool is awkward.

- MapTool exports JSON or text files to a known local folder
- the bridge watches that folder
- the bridge parses the export and serves the normalized HTTP response to DMA

This is slower than live push, but simple and robust.

#### Option C: Native Protocol Sidecar

Highest complexity and probably not the first slice.

- The bridge speaks MapTool's real runtime protocol directly
- The bridge discovers maps/tokens/combat state without any explicit macro export

This should only be attempted after proving the exact protocol and permissions model.

## Concrete Payload Contract

DMA already has a good normalized target shape in [backend/models/maptool.py](/Users/noah/Google%20Drive/AI%20projects/DMA-main/backend/models/maptool.py).

The bridge should serve a payload compatible with:

```json
{
  "id": "harbor-docks",
  "name": "Greyhaven Docks",
  "tokens": [
    {
      "id": "captain-mira",
      "name": "Captain Mira",
      "x": 14,
      "y": 7,
      "notes": "Holding the line",
      "gm_notes": "Knows the smugglers are backed by House Vane",
      "layer": "objects",
      "hp_current": 22,
      "hp_max": 35,
      "initiative": 18,
      "conditions": ["frightened 1"]
    }
  ],
  "fog_state": "partial",
  "light_state": "dim"
}
```

That shape matches what the current adapter already expects from `GET /maps/{map_id}`.

## First Implementation Slice

The smallest credible implementation would be:

1. leave DMA's existing adapter and routes in place
2. build a tiny `maptool-bridge` HTTP service with:
   - `POST /bridge/map-state`
   - `GET /maps/{map_id}`
   - `POST /auth/login` as a simple local token gate if needed
3. manually post sample JSON from a script or fixture
4. confirm `/api/live/maptool-sync` works end-to-end against the bridge

After that, connect MapTool to the bridge through either:

- a macro that posts JSON
- a plugin that posts JSON
- or a watched export file

### Prototype In This Repo

This repo now includes a first local bridge prototype:

- script: [scripts/maptool_bridge.py](/Users/noah/Google%20Drive/AI%20projects/DMA-main/scripts/maptool_bridge.py)
- test: [tests/unit/test_maptool_bridge.py](/Users/noah/Google%20Drive/AI%20projects/DMA-main/tests/unit/test_maptool_bridge.py)
- run command: `make maptool-bridge`
- demo pusher: [scripts/push_maptool_fixture.py](/Users/noah/Google%20Drive/AI%20projects/DMA-main/scripts/push_maptool_fixture.py)
- demo test: [tests/unit/test_push_maptool_fixture.py](/Users/noah/Google%20Drive/AI%20projects/DMA-main/tests/unit/test_push_maptool_fixture.py)
- payload-file pusher: [scripts/push_maptool_payload_file.py](/Users/noah/Google%20Drive/AI%20projects/DMA-main/scripts/push_maptool_payload_file.py)
- payload-file test: [tests/unit/test_push_maptool_payload_file.py](/Users/noah/Google%20Drive/AI%20projects/DMA-main/tests/unit/test_push_maptool_payload_file.py)
- payload-dir watcher: [scripts/watch_maptool_payload_dir.py](/Users/noah/Google%20Drive/AI%20projects/DMA-main/scripts/watch_maptool_payload_dir.py)
- payload-dir watcher test: [tests/unit/test_watch_maptool_payload_dir.py](/Users/noah/Google%20Drive/AI%20projects/DMA-main/tests/unit/test_watch_maptool_payload_dir.py)
- MapTool handoff assets: [assets/maptool/bridge/README.md](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/README.md)
- macro template: [assets/maptool/bridge/dma-sync-bridge.macro.txt](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/dma-sync-bridge.macro.txt)
- mapping template: [assets/maptool/bridge/property-mapping.example.json](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/property-mapping.example.json)
- install checklist: [assets/maptool/bridge/macro-install-checklist.md](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/macro-install-checklist.md)

Default behavior:

- binds to `127.0.0.1:5005`
- accepts `POST /bridge/map-state`
- serves `GET /maps/{map_id}`
- exposes `POST /auth/login` when username/password are configured
- keeps the latest pushed snapshot in memory

Example manual push:

```bash
curl -X POST http://127.0.0.1:5005/bridge/map-state \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "harbor-docks",
    "name": "Greyhaven Docks",
    "tokens": [
      {
        "id": "captain-mira",
        "name": "Captain Mira",
        "x": 14,
        "y": 7,
        "hp_current": 22,
        "hp_max": 35,
        "initiative": 18,
        "conditions": ["frightened 1"]
      }
    ]
  }'
```

Then DMA can target that bridge with:

```bash
MAPTOOL_BASE_URL=http://127.0.0.1:5005
```

### Demo Loop

The quickest end-to-end demo path is now:

1. Run `make maptool-bridge`
2. In another shell, run `make push-maptool-fixture`
3. Start DMA with `MAPTOOL_BASE_URL=http://127.0.0.1:5005 make dev`
4. Call:

```bash
curl -X POST http://127.0.0.1:8000/api/live/maptool-sync \
  -H 'Content-Type: application/json' \
  -d '{"map_id":"harbor-docks"}'
```

5. Open `http://127.0.0.1:8000/dm-panel` and inspect the Session Mechanics panel

### File-Based Real Export Path

For a more realistic MapTool handoff than the hardcoded fixture:

1. Export a JSON file from MapTool that matches:
   [assets/maptool/bridge/sample-map-state.json](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/sample-map-state.json)
2. Push that file into the bridge:

```bash
make push-maptool-payload FILE=assets/maptool/bridge/sample-map-state.json
```

3. Run DMA sync as usual:

```bash
curl -X POST http://127.0.0.1:8000/api/live/maptool-sync \
  -H 'Content-Type: application/json' \
  -d '{"map_id":"harbor-docks"}'
```

This gives us a real integration seam for a future MapTool macro even before direct HTTP posting
from inside MapTool is finalized.

If MapTool can export JSON files but not post them directly, you can also watch an export folder:

```bash
make watch-maptool-payloads DIR=/path/to/maptool/export-dir
```

Every changed `*.json` file in that folder will be validated and pushed into the bridge.

### Trusted Macro Starter

The repo now includes a concrete starter macro template for MapTool:

- [dma-sync-bridge.macro.txt](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/dma-sync-bridge.macro.txt)

Use it together with:

- [property-mapping.example.json](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/property-mapping.example.json)
- [macro-install-checklist.md](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/macro-install-checklist.md)

Important caveat:

- the macro template is intentionally a campaign-adaptation starter, not a guaranteed plug-and-play
  script for every framework
- `REST.post()` requires a trusted macro and external macro access enabled in MapTool
- HP, initiative, and condition extraction still depend on how your campaign stores them

## Suggested Repository Shape

If we implement the bridge in this repo, a clean location would be:

- `scripts/maptool_bridge.py` for the first prototype, or
- `backend/bridges/maptool/` if we want it to become a maintained subsystem

If the bridge stays outside DMA, the repo should still keep:

- the normalized payload schema in `backend/models/maptool.py`
- the adapter contract in `backend/services/maptool_adapter.py`
- the DM panel and live-session integration in Phase 4

## Success Criteria

The bridge is good enough for the next phase once we can:

1. start MapTool normally
2. trigger a local export or sync action
3. hit `POST /api/live/maptool-sync` in DMA
4. see current token positions plus initiative and HP pressure in `/dm-panel`
5. repeat the flow without editing DMA config beyond bridge URL and token

## Existing API Contract Draft

The current codebase still exposes these draft routes:

- `POST /api/maptool/pull`
- `POST /api/maptool/push`
- `POST /api/live/maptool-sync`

They describe the payload shape DMA would like to consume from a future bridge, but they should not
be read as proof that stock MapTool already exposes this HTTP API.

## Target UX

If a real bridge is added later, the intended DMA flow is still:

1. Open DMA at `http://127.0.0.1:8000/dm-panel`.
2. Fill in the live scene state and set `MapTool Map ID`.
3. Provide bridge credentials or an `Authorization` header when relevant.
4. Click `Sync MapTool`.

The equivalent API call would remain:

```bash
curl -X POST http://127.0.0.1:8000/api/live/maptool-sync \
  -H 'Content-Type: application/json' \
  -d '{"map_id":"YOUR_MAP_ID"}'
```

## What Success Looks Like

Once a real bridge exists, a successful sync should populate the live snapshot with a `maptool`
section containing:

- the pulled map id and name
- normalized token data
- initiative ordering when present
- HP pressure summaries when HP fields are present
- condition summaries when token conditions are present

## DM panel usage

The `/dm-panel` page now includes:

- a `MapTool Map ID` field in the live state form
- a `Session Mechanics` panel with optional `Authorization Header`
- a sync action that stores the latest pulled map in live context

This is intentionally read-only for mechanics at the moment. The goal is to keep the panel fast and useful during play without turning it into a full MapTool replacement.

## Troubleshooting

- Do not use the port from `File -> Start Server...` as `MAPTOOL_BASE_URL`; that is a TCP game-server port, not the experimental HTTP bridge DMA expects.
- If `MAPTOOL_BASE_URL` points at `http://localhost:5000/api`, verify some other local app is not already using port `5000`.
- `502` from DMA currently usually means the experimental adapter could not reach a custom bridge, not that stock MapTool is misconfigured.
