# DMA Sync Macro Install Checklist

Use this checklist when turning the starter macro into a working trusted macro inside MapTool.

## 1. Create The Macro

1. Open the `GM` macro panel or a `Lib:` token macro location.
2. Create a new macro named `DMA Sync Bridge`.
3. Paste the contents of:
   [dma-sync-bridge.macro.txt](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/dma-sync-bridge.macro.txt)

## 2. Make It Trusted

The RPTools docs note that `REST.post()` only works in a trusted macro.

To keep the macro trusted:

1. Put it in a trusted GM or `Lib:` location.
2. Do not allow players to edit it.
3. In Preferences, enable external macro access.

Reference:
- `REST.post()`:
  https://wiki.rptools.info/index.php/REST.post
- Preferences / external macro access:
  https://wiki.rptools.info/index.php/MapTool_Preferences

## 3. Map Campaign Properties

Open:
[property-mapping.example.json](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/property-mapping.example.json)

Decide what your campaign uses for:

- current HP
- max HP
- initiative
- conditions or states
- token notes / GM notes
- token layer
- map id and map name

Then replace the placeholder property names and helper lines in the macro.

## 4. Start Small

Before exporting all tokens:

1. limit the token query to selected tokens or the TOKEN layer
2. verify one token payload in chat
3. only then post the full payload to the bridge

## 5. Validate The JSON

If direct HTTP posting is awkward, export the payload to a file shaped like:
[sample-map-state.json](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/sample-map-state.json)

Then validate and push it with:

```bash
make push-maptool-payload FILE=/path/to/map-state.json
```

## 6. Verify In DMA

With the bridge and DMA running:

```bash
curl -X POST http://127.0.0.1:8000/api/live/maptool-sync \
  -H 'Content-Type: application/json' \
  -d '{"map_id":"harbor-docks"}'
```

Then open:

- `http://127.0.0.1:8000/dm-panel`

You should see initiative order, conditions, and low-HP highlights in the Session Mechanics panel.
