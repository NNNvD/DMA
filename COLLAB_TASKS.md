# Collaboration Tasks

Planning pointer updated: 2026-10-28. Historical task entries below were last
updated on 2026-04-21.

## Current Engineering Sequence

Use W0-W6 in [the roadmap](docs/05-roadmap-and-milestones.md) and
[the session-cycle and Discord plan](docs/22-agent-session-cycle-and-discord.md).
The browser is the session workspace; a dedicated external campaign agent will
handle preparation, live assistance, and debrief. W0's field-level ownership,
tool/approval contract, and fictional paired recovery are verified in
[the W0 contract](docs/23-agent-operating-and-data-contract.md). W1 is sufficient
for the local fictional GM workflow: [dedicated Codex setup, guarded staging/review
and restart](docs/25-campaign-agent-review-and-acceptance.md) are verified.
The [completion record](docs/work-records/2026-10-28-w1-campaign-agent-completion.md)
distinguishes native host, protocol, operator simulation and platform evidence.
Next implement the [guided workflow and feedback contract](docs/27-guided-agent-workflows-and-feedback.md):
W2a durable interviews, capture, preferences/feedback and interactive entry; W2b
debrief, reviewed log, player-report drafts and handoff; W4a guided preparation;
then local W5 rehearsal and the tested setup/before/during/after DM manual.
Optional approved Discord publishing follows that usability gate. Discord player
questions follow the core rehearsal and player access tests.

W2a implementation update: [the guided operator-runner prototype](docs/28-guided-agent-prototype.md)
now supplies private revisioned interviews, capture, confirmed preferences,
prep/debrief drafting and restart. It does not close the full manual gate: native
human usability, canonical packet-to-W1 review integration, richer reminder/report
management and recovery including the private workflow sidecar remain required.

M1-M5 remain supporting engineering workstreams. Implemented combat reliability
and atomic session-update promotion/provenance are reused. Full CI, prep source
evidence, live recovery readiness, and post-archive browser checks remain
open gates. The session review panel stays archived; the external agent is the
intended review surface. The existing local checkpoint requirements still apply.

No human input is required to start fixture-based W2 implementation.
Real campaign attachment requires an approved binding/backup plan.
Before connecting Discord, request the chosen server/channel and publication
authority; before always-on operation, resolve hosting, model budget, and retention.
These are future configuration decisions, not blockers to the core local workflow.

The older input requests and completion entries below are historical. Reevaluate
their need and destination before acting on them: Obsidian is legacy compatibility,
private campaign data uses the root overlay, and real MapTool work is deferred to
M5. Available source files should be inspected before requesting new samples.

This file is the shared workboard for human tasks, incoming source material, and handoff notes between you and Codex.

## How We Use This File

- Codex can add or update concrete tasks for you here.
- You can drop source material into the folders listed below.
- When you add new material, note it briefly under `Incoming Material` so I know what changed.
- If something is anonymized or partial, that is still useful. Please do not wait for “perfect” samples.

## Drop Zones

- Pathbuilder 2 character exports:
  `assets/imports/pathbuilder/`
- Session logs, recaps, or post-session notes:
  `assets/imports/session-logs/`
- Campaign notes, lore docs, faction notes, world summaries:
  `assets/imports/campaign-notes/`
- Miscellaneous reference material:
  `assets/imports/misc/`

Once files are in place, Codex can preview or import them in bulk with:

- `make preview-assets`
- `make import-assets`

## File Naming Suggestions

- Pathbuilder 2 exports:
  `pc-<character-name>-pathbuilder.json`
- Session logs:
  `session-<number>-log.md`
- Campaign notes:
  `campaign-<topic>.md`

## Current Tasks For Noah

These are helpful when convenient, but not blocking the current engineering work.

- [ ] Drop 1 or 2 anonymized Pathbuilder 2 JSON exports into `assets/imports/pathbuilder/`
  The most useful next samples are:
  1. a spellcaster
  2. a higher-level character with runes, magic gear, or other more complex data
- [ ] Drop 1 anonymized session log into `assets/imports/session-logs/`
  Ideal format:
  session recap, named NPCs, location changes, loot/items, and any calendar/date notes
- [ ] Drop 1 campaign note sample into `assets/imports/campaign-notes/`
  Ideal format:
  location/faction/NPC references in the style you actually use
- [ ] For the MapTool bridge path, identify one real combat map/campaign whose token properties we can inspect
  Most useful details:
  1. the exact property names for current HP and max HP
  2. where initiative is stored
  3. how conditions/states are represented
  4. whether notes / GM notes are used on tokens
- [ ] Paste or screenshot the relevant MapTool token property schema for one PC token and one NPC token
  That is enough to turn the starter macro into a campaign-specific version

## Incoming Material

- 2026-03-25:
  Pathbuilder 2 JSON sample for Conan was shared in chat and used to build initial importer support.
- 2026-04-20:
  Existing import corpus was archived to `assets/archive/pre-abomination-vaults-playtest-2026-04-20/imports/` so the active `assets/imports/` tree now contains only the two Abomination Vaults PDFs for the new PF2e play-test.
- 2026-04-20:
  The legacy `obsidian-test-vault/` was removed and replaced with `obsidian-abomination-vaults-vault/`, a fresh play-test vault scaffold created from `dma-abomination-vaults.db` plus manual starter notes for the new campaign.
- 2026-04-20:
  The two Abomination Vaults PDFs were imported into `dma-abomination-vaults.db` as `reference` documents, and the fresh vault was re-exported so they now appear under `obsidian-abomination-vaults-vault/Library/References/`.
- 2026-04-20:
  Added two starter campaign-note imports for the Abomination Vaults play-test. The fresh database now contains 26 seeded campaign entities plus 2 imported references, and the vault export reflects those entities under `Campaign/`.
- 2026-04-21:
  Added `Abomination Vaults 2 - Hands of the Devil.pdf` and `Abomination Vaults 3 - Eyes of Empty Death.pdf` to the active GM reference corpus, imported them into `dma-abomination-vaults.db`, and re-exported the vault so `Library/References/` now contains all four core books.
- 2026-04-21:
  Normalized the Abomination Vaults map set into `assets/imports/misc/private-local/media/abomination-vaults/maps/` and regenerated ingestion sidecars/manifests for 46 tracked map/media assets.
- 2026-04-21:
  Upgraded the Obsidian exporter to write richer YAML frontmatter, clearer note sections, source-reference excerpts for entity notes, and bounded PDF image extraction into `Library/Assets/` for reference documents.

## Notes For Codex

- Prefer real user formats over generic synthetic formats once samples exist.
- Keep importers backwards-compatible with the current deterministic text formats where reasonable.
- Update this file when new human input would materially unblock the next slice of work.
- Use the drop-zone preview/batch importer before asking the user to hand-enter content already available as files.
- As of 2026-04-10, synthetic Phase 2 validation is green via `make phase2-check`; the next high-value validation step is running the batch importer against real sample files when they are available.
- As of 2026-04-19, the local MapTool bridge demo path is green end-to-end with synthetic data, including `/api/live/maptool-sync` and DM-panel mechanics. The main blocker for a real MapTool macro is campaign-specific token property/state mapping.

## MapTool Follow-Ups

These are logged for later because they depend on real campaign data or manual MapTool setup.

- [ ] Adapt `assets/maptool/bridge/dma-sync-bridge.macro.txt` to the actual campaign property names once a real MapTool campaign sample is available
- [ ] Verify whether direct `REST.post()` from a trusted MapTool macro is comfortable enough, or whether file export + watcher should be the default workflow
- [ ] Decide whether to keep the bridge as a script under `scripts/` or promote it into a maintained subsystem
- [ ] Explore whether initiative and conditions can be read reliably from the active MapTool framework without custom per-campaign wiring
- [ ] If macro export proves brittle, investigate a plugin or sidecar approach as the next integration step
- [ ] For the Abomination Vaults play-test, switch DMA onto a fresh database before importing the new PDFs if we want the runtime state to be truly "from scratch"
- [ ] Import party character sheets once they are ready, then re-export the vault so PCs, sheet versions, and party-facing links join the current campaign baseline

## Done Recently

- [x] Added structured campaign entity import for notes
- [x] Added generic text PC sheet import
- [x] Added session update import flow
- [x] Added initial Pathbuilder 2 JSON import support
- [x] Added drop-zone batch import with dry-run preview
- [x] Added PC dossier and session-history read endpoints
- [x] Added a dedicated `make phase2-check` target and completed a full synthetic verification pass
- [x] Verified the local MapTool bridge demo end-to-end with synthetic live mechanics data
- [x] Added bridge fixture push, payload-file push, and payload-directory watch workflows
