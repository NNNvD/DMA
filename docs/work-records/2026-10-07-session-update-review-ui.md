# Session Update Review UI — 2026-10-07

Added a DM panel module for reviewing pending staged session updates. It loads
campaign-filtered pending drafts, displays the retained source plus parsed
candidate payloads and captured baselines, and sends accept/reject/defer actions
to the staged review API. Candidate rejection and session-log rejection require
reasons in the UI. Session-log approval/rejection remains separate and is enabled
only after each candidate has a final or deferred decision.

The UI renders source and candidate data as escaped text. A stale-baseline 409 is
shown with guidance to review the changed campaign fact and stage a fresh draft.
Finalized drafts are removed from the pending list. Draft staging, persistent
reviewer identity configuration, durable candidate-to-entity provenance, and
multi-candidate atomic promotion remain follow-up work.

No live campaign data or database migration was performed for this UI change.
