# Private campaign rehearsal

This local-only profile uses a verified copy of explicitly selected private
campaign data. It is neither a fictional fixture nor a connection to the live
campaign. Simulated history, notes, approvals and reports remain in that copy.

## Preparation contract

`scripts.prepare_private_rehearsal` requires explicit source DB/private-root,
campaign/session ID, isolated MCP Python and a new ignored `.codex-temp/`
workspace. It selects only the named campaign within shared private assets,
refuses symlinks, snapshots SQLite through its backup API, copies private files,
and verifies file hashes before activation. Original stores are not migrated.

An unversioned legacy SQLite copy is compared against a separately generated
0003 baseline by table/column names, types, nullability and primary keys. Column
ordering is irrelevant. Only a matching copied database is stamped and upgraded
through 0007. Unknown schema differences stop activation. Original tables and
overlay prose are not silently converted into approved history or canonical facts.

The snapshot, working pair, hash manifest, binding and `REHEARSAL_READY.json`
remain private. A distinct `private-rehearsal` onboarding mode sets `fixture_only`
to false and publication to false. The isolated binding has its own recovery
epoch, physical paths and an explicit selected-session link. Agents/operators
reject bindings to the original sources, missing verification markers and stores
outside the permitted ignored rehearsal root. Existing fictional profiles remain
supported. The trusted local OS/operator remains part of the boundary.

Do not reuse an activated workspace as a new setup target. `--resume-snapshot`
is restricted to a failed, unactivated copy whose source, snapshot and working
contents still verify; it never repairs an edited rehearsal by overwriting it.

## Browser and material access

`python -m scripts.serve_private_rehearsal --binding "<rehearsal>/binding.json"`
starts the actual API/panel on localhost. Use `python3` on macOS/Linux (untested).
The page title and fixed header explicitly say PRIVATE REHEARSAL. The selected
session note and map are configured without changing campaign source notes.
External reference fetching is disabled, and a rehearsal-only Content Security
Policy restricts browser resources/connections to the local server and local
data/blob assets. Remote portraits may therefore be unavailable.

The existing bounded `campaign_read_notes` tool supports `item_id=catalog` for
note headers and selected `room`/`bestiary` entries. Rooms use exact `map_id/room_id`
identities. Full entries are GM-only, campaign-filtered, bounded and cited with
their file hash. The tool cannot accept a filesystem path or open arbitrary PDFs.
Copied PDFs remain local references, not automatically ingested/model-readable
books. No additional MCP tools, shell permissions or approval-grant tools are added.

## External model consent

The native DMA agent runs through the Codex service. Its selected tool results
can include private session notes, dossiers and GM-only room/adventure material.
Obtain explicit authorization for that destination and data scope before starting
a native real-material rehearsal. Local copy creation/browser checks do not
substitute for this permission. Do not send the entire overlay/books by default.
No Discord publishing or public Git upload is part of the rehearsal.

## Limits

The command-center state and original overlay notes are operational/unreviewed
sources until reconciled; they are not accepted session logs merely because they
exist. Use a baseline confirmation before role-playing. Keep the workflow sidecar
with the rehearsal's recovery set. Completed simulated approvals apply only to
the rehearsal identity and epoch. Copy verification is not proof of a concurrent
multi-store transactional snapshot: original writers must remain quiescent while
snapshotting, and any detected change stops activation.
