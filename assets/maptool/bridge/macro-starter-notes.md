# MapTool Macro Starter Notes

This is a starter plan for a **trusted GM macro** that sends current map state to DMA's local
bridge. It is intentionally conservative: use it as a checklist and adaptation guide, not as a
drop-in guaranteed script for every campaign.

## Preconditions

In MapTool:

1. Put the macro on a trusted location such as a GM macro or `Lib:` token macro.
2. Enable external macro access in Preferences.
3. Confirm the bridge is running locally, for example at `http://127.0.0.1:5005`.

The RPTools wiki notes that `REST.post()` can only be used in a trusted macro, and external macro
access must be enabled for HTTP-capable macro functions.

## Recommended Macro Shape

The most practical first macro is:

1. gather token ids with `getTokens("json", ...)`
2. build a JSON payload containing:
   - current map id
   - current map name
   - token list
   - optional fog/light summaries if your campaign tracks them
3. call `REST.post(bridgeUrl + "/bridge/map-state", payload, "application/json; charset=UTF-8", 1)`

## Token Fields To Export

Aim for this minimum token shape:

```json
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
```

The exact source for `hp_current`, `hp_max`, `initiative`, and `conditions` depends on how your
campaign stores them:

- token properties
- token states
- initiative panel values
- custom framework macros or lib-token helpers

## Practical Implementation Strategy

Use two macros instead of one giant macro:

1. `DMA Build Token Payload`
   Returns a JSON object for one token id.
2. `DMA Sync Bridge`
   Loops through token ids, appends each token payload into an array, then posts the full map JSON.

That split makes it easier to adapt property names for a specific campaign framework.

## Lowest-Risk Rollout

Start with:

- selected tokens only, or
- visible tokens on the current map, or
- all tokens on the TOKEN layer

Then add:

- GM notes
- HP and initiative
- conditions/state mapping
- fog/light metadata

## File-Based Fallback

If direct `REST.post()` turns out to be inconvenient, the same macro can instead:

1. output the JSON to a dialog or chat
2. save or copy it into a file that matches `sample-map-state.json`
3. send it to DMA via:

```bash
python3 -m scripts.push_maptool_payload_file --file /path/to/exported-map-state.json
```

That still gets you into the bridge with a real MapTool-originated payload.
