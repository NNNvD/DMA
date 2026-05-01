# MapTool Bridge Assets

This folder is the handoff bundle for moving from the repo's demo fixture toward a real
MapTool-originated bridge payload.

## What Is Here

- [sample-map-state.json](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/sample-map-state.json)
  A known-good payload in the same shape DMA expects from the bridge.
- [macro-starter-notes.md](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/macro-starter-notes.md)
  A practical starter plan for a trusted MapTool macro.
- [dma-sync-bridge.macro.txt](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/dma-sync-bridge.macro.txt)
  A concrete starter macro template for posting current map state to the bridge.
- [property-mapping.example.json](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/property-mapping.example.json)
  A campaign-specific field mapping checklist for HP, initiative, conditions, and notes.
- [macro-install-checklist.md](/Users/noah/Google%20Drive/AI%20projects/DMA-main/assets/maptool/bridge/macro-install-checklist.md)
  A step-by-step checklist for installing and adapting the trusted macro in MapTool.

## Practical First Workflow

If direct HTTP from MapTool is awkward, use a file-based handoff first:

1. Export MapTool state into a JSON file shaped like `sample-map-state.json`.
2. Push that file into the local bridge:

```bash
python3 -m scripts.push_maptool_payload_file --file assets/maptool/bridge/sample-map-state.json
```

Or with `make`:

```bash
make push-maptool-payload FILE=assets/maptool/bridge/sample-map-state.json
```

3. Run DMA live sync against the same `map_id`.

## Why This Helps

This keeps the gap between MapTool and DMA small:

- MapTool only needs to produce JSON
- the bridge continues to validate the payload
- DMA keeps the same `/api/live/maptool-sync` contract

## Concrete Next Human Step

The best next manual step is:

1. copy `dma-sync-bridge.macro.txt` into a trusted GM or `Lib:` macro in MapTool
2. adapt the placeholder property names using `property-mapping.example.json`
3. test against one token first
4. only then expand to all combatants on the current map

## MapTool Macro References

These official docs were the basis for the starter notes:

- `REST.post()`:
  https://wiki.rptools.info/index.php/REST.post
- `getTokens()`:
  https://wiki.rptools.info/index.php/getTokens
- Macro permissions / external access:
  https://wiki.rptools.info/index.php/MapTool_Preferences
