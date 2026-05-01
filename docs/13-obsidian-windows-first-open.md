# Obsidian First-Open Guide For The Abomination Vaults Vault

This guide is for someone who:

- has just installed Obsidian on a Windows PC
- already has the local folder `obsidian-abomination-vaults-vault`
- wants to use that folder as their Obsidian vault the first time they open the app

## 1. Open The Existing Vault

1. Start Obsidian.
2. On the welcome screen, choose `Open folder as vault`.
3. Browse to the local folder named `obsidian-abomination-vaults-vault`.
4. Select that folder and confirm.

Obsidian will now treat that folder as the vault and open it directly.

## 2. Do You Need To Change Any Settings?

No mandatory settings changes are required just to use this vault.

The vault is already plain Markdown plus frontmatter, so it should open normally right away.

Recommended checks:

- Leave `Properties` enabled if Obsidian asks how to display note metadata.
  This vault uses YAML frontmatter on many notes.
- If the `Campaign Index`, `Library Index`, or `Notes Index` pages show a normal note with a link list, that is fine.
- If embedded `.base` views do not render as a dynamic table in your Obsidian install, you can still use the vault normally through the note links.
- The generated Bases files live in the top-level `Bases/` folder; they support the dashboards but usually do not need to be opened directly.

In other words:

- required: no extra setup
- optional: if your Obsidian version supports Bases views, keep that feature enabled
- fallback: if Bases is unavailable, the vault is still readable and usable

## 3. What To Open First

Start with:

- `00 Vault Guide`
- `Home`
- `Command Center/Start Here`
- `Command Center/Session Dashboard`
- `Campaign/Index`
- `Library/Index`
- `Notes/Index`

These act as the main entry points into the vault.

## 4. How To Read And Use The Vault

Use the vault like a campaign command center:

- `Command Center/Start Here` gives the high-level starting point
- `Command Center/Session Dashboard` is the best live-play cockpit and keeps the party table, tonight's prep, and the main trackers together
- `Command Center/Session 1 Prep` collects the opening-session checklist and embeds the most useful canonical note sections
- `Command Center/Party Overview` gives the GM a table view of the party's key stats, senses, languages, relevant skills, and tactical roles like healing, scouting, and frontline coverage
- `Command Center/Session Threat Fit` interprets those party strengths against the actual pressures of the opening session
- `Command Center/Timeline`, `NPC Roster`, and `Location Atlas` use embedded Bases views for browsing canonical notes
- `Command Center/Encounter Tracker` and `Treasure Tracker` embed the relevant sections from the canonical reference notes
- many embedded sections now sit inside foldable callouts, so you can expand only what you need during play
- `Campaign/Index` is the main dynamic browse page for locations, NPCs, factions, shops, and events
- `Library/Index` contains the imported reference books
- `Notes/Index` contains the imported DMA campaign notes
- editable sections such as `DM Working Notes`, `Player-Facing Summary`, `Session Changes`, and `DMA Editable Source` are safe places for GM additions

Practical reading flow:

1. Open `00 Vault Guide`
2. Open `Command Center/Start Here`
3. Open `Command Center/Session Dashboard`
4. Open `Command Center/Session 1 Prep`
5. Go to `Campaign/Index`
6. Open important places like `Otari`, `Gauntlight Keep`, and `Otari Graveyard`
7. Open key NPCs like `Wrin Sivinxi`, `Oseph Menhemes`, and `Belcorra Haruvex`
8. Use `Library/Index` when you want to cross-check the source books

## 5. What This Vault Is Best For

Use this vault for:

- browsing the current campaign model
- following links between people, places, and factions
- reading imported source notes and book references
- keeping a readable local campaign workspace
- making supported human edits that can later be synced back into DMA

Do not think of it as the only source of truth yet.
DMA's structured database is still the automation engine, and this vault is the readable human-facing view of that state.

## 6. When New DMA Data Arrives

When new party sheets, notes, or session logs are imported into DMA, the vault should be exported again so Obsidian reflects the latest campaign state.

If your GM plans to sync Obsidian edits back into DMA:

- safe to edit: `DM Working Notes`, `Player-Facing Summary`, `Session Changes`, and `DMA Editable Source`
- do not edit lines that begin with `<!-- dma:managed` or `<!-- dma:editable`
- do not remove YAML properties such as `dma_kind`, `entity_id`, `doc_id`, `stable_key`, or `vault_sync`
