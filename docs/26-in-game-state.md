# In-Game State in the DM panel

The top-right overview groups **location, day, time, weather and environmental
effects**. Location includes an optional linked dungeon map instead of a separate
Map card. Scene, Focus and Active NPC counters are no longer shown. Conversation
with DMA happens in the dedicated agent in Codex or the IDE; the browser chat
workbench is explicitly archived.

## DM controls

Choose **Edit state** to set a location or room, linked map, exposure (outdoors,
indoors, underground), climate, campaign calendar, day/month/year and time of day.
Location suggestions include known campaign locations, settlements and maps;
free text is allowed. Selecting a linked map loads it in Map Room. A location's
configured exposure and climate are used when that known location is selected.

Changes save when a field changes or loses focus. **Save In-Game State** explicitly
saves the current form; **Done** saves before closing. Unsaved or failed edits
remain visible. Saves share the combat write queue and use the live-state revision;
a stale panel is told to refresh and reconcile rather than overwrite newer state.
Reloading restores saved values and conditions. Opening a session preserves these
values and the tracker; it does not insert a campaign-specific starting room.

Weather and environmental effects have independent **Automatic** and **Manual
override** modes. Automatic weather uses location/exposure, climate, season,
date and time. Automatic effects consider exposure, weather and available natural
light. Indoors and underground do not inherit outdoor rain, wind or visibility
hazards. Local lighting, terrain or magical hazards can be entered as a manual
environment override.

A manual override stays pinned when location, day or time changes. Switch that
field back to Automatic to resume updates. **Generate new weather** rerolls only
automatic weather; it is disabled while weather is manually overridden. It does
not clear an environmental override. A reroll may legitimately produce the same
weather description. Generated conditions remain stable on refresh and ordinary
combat saves; they do not change with the computer's clock.

These are descriptive scene suggestions, not automatic PF2e condition changes,
damage, numerical penalties or authoritative rules. They do not fetch real-world
weather or use a paid model. The initial generator uses a small reproducible
climate/season table. Regional climate models, forecast continuity and automatic
travel/time advancement are later improvements.

## Campaign calendars

Existing calendars with month-name strings remain supported. Calendar details can
also define structured months with lengths and seasons, weekday names and an
optional weekday anchor:

```json
{
  "months": [
    {"name": "Bloom", "days": 30, "season": "spring"},
    {"name": "Frost", "days": 30, "season": "winter"}
  ],
  "weekdays": ["Emberday", "Tideday", "Bellday"],
  "current_date": {"year": 12, "month": "Bloom", "day": 1, "weekday": "Emberday"}
}
```

The current campaign date seeds an unset live date. Structured months provide
season lookup and day-length validation. Weekdays are calculated only when all
month lengths and an anchor weekday are available, using a fixed-length calendar
year. `weekday_anchor`, when supplied, has the same date/weekday shape as
`current_date` and takes precedence as that anchor. Intercalary/leap-day calendars
are not inferred: use the weekday override where their rules differ. Arbitrary
campaign month names work without Gregorian assumptions. If no seasonal mapping
exists, set Season explicitly; the overview otherwise says season is not set.

The calendar name, weekday and season can also be entered manually for a calendar
that is not configured in campaign records. Selecting a different campaign
calendar loads its current date. A weekday override remains explicit until it is
cleared; a blank override resumes any available calendar calculation.

## Storage and service boundary

Inputs live under `live-session-state.in_game_state` in the existing revisioned
SQL context row. `GET /api/live/session-state` includes the resolved
`in_game_state` view and available campaign calendars.
`PATCH /api/live/in-game-state` takes a complete `state` input object and required
`expected_revision`. It updates this workspace state without replacing combat.
Legacy live-state/combat writes preserve the environment inputs. Reset Live State
clears both workspaces.

This is session-local operational state: setting the day does **not** rewrite the
accepted campaign calendar, private overlay, session log, player report or staged
agent approvals. Accepting a debrief into campaign canon remains a separate
reviewed operation. The backend retains old scene fields and the legacy helper
API for compatibility, without displaying their former browser controls.
