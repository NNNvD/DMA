"""Private operator-owned interview drafts. No campaign/canon/publication writes.

The store is deliberately not an MCP tool: confirmation, preferences and report
approval are supplied by the trusted operator runner, never agent output.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


QUESTIONS = {
    "prep": [
        (
            "direction",
            "Where should preparation focus?",
            [
                "Continue the previous handoff",
                "Town / social play",
                "Travel / exploration",
                "Another direction",
            ],
        ),
        (
            "priorities",
            "What matters most this session?",
            [
                "Resolve an open lead",
                "Character spotlight",
                "A balanced session",
                "Other priorities",
            ],
        ),
        (
            "constraints",
            "Any time, tone or preparation constraints?",
            [
                "Use saved preferences",
                "Keep it short",
                "Allow more detail",
                "Describe constraints",
            ],
        ),
        (
            "readiness",
            "What should the runbook include or flag?",
            [
                "Opening and likely branches",
                "NPCs, clues and encounters",
                "Missing maps / rules / rulings",
                "All of these",
            ],
        ),
    ],
    "debrief": [
        (
            "account",
            "What happened? Correct or extend the captured notes.",
            [
                "Use captured notes as a starting point",
                "Add missing events",
                "Correct the account",
                "Uncertain: retain for review",
            ],
        ),
        (
            "changes",
            "Which outcomes need campaign review?",
            [
                "NPCs / relationships",
                "Discoveries / resources",
                "Rulings / consequences",
                "None or uncertain",
            ],
        ),
        (
            "revealed",
            "Enter ONLY what players learned, for the player-report draft.",
            [],
        ),
        (
            "intentions",
            "What do players intend next?",
            [
                "Continue the current lead",
                "Return to town",
                "Travel elsewhere",
                "Not sure yet",
            ],
        ),
        (
            "handoff",
            "What should the next preparation remember?",
            [
                "Unresolved hooks",
                "Character spotlight",
                "Resources or rules to prepare",
                "Other / none",
            ],
        ),
    ],
}


def questions_for(data):
    questions = QUESTIONS[data["kind"]]
    if data["answers"].get("mode") == "quick":
        keys = (
            {"direction", "priorities", "constraints"}
            if data["kind"] == "prep"
            else {"account", "revealed", "intentions"}
        )
        return [item for item in questions if item[0] in keys]
    return questions


class WorkflowConflict(ValueError):
    pass


class GuidedStore:
    def __init__(self, path: Path, scope: dict, guard=None):
        self.path = Path(path).absolute()
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise ValueError("Workflow store must not be a symlink")
        self.scope = dict(scope)
        self.guard = guard
        self.scope_key = digest(scope)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflows(id TEXT PRIMARY KEY, scope TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS preferences(scope TEXT, key TEXT, value TEXT, PRIMARY KEY(scope,key));
                CREATE TABLE IF NOT EXISTS retries(scope TEXT, key TEXT, request TEXT, result TEXT, PRIMARY KEY(scope,key));
                CREATE TABLE IF NOT EXISTS reminders(scope TEXT, workflow TEXT, source TEXT, PRIMARY KEY(scope,workflow,source));
                CREATE TABLE IF NOT EXISTS preference_events(scope TEXT, data TEXT);
            """
            )

    @contextmanager
    def _db(self):
        if self.guard:
            self.guard()
        if self.path.is_symlink():
            raise ValueError("Workflow store changed")
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _read(self, db, identifier):
        row = db.execute(
            "SELECT data FROM workflows WHERE id=? AND scope=?",
            (identifier, self.scope_key),
        ).fetchone()
        if not row:
            raise LookupError("Workflow not found in this operator/campaign/epoch")
        return json.loads(row[0])

    def start(self, session, kind):
        if (
            kind not in QUESTIONS
            or not isinstance(session, str)
            or not 1 <= len(session) <= 128
        ):
            raise ValueError("Select prep/debrief and an explicit session ID")
        data = {
            "id": str(uuid4()),
            "session_id": session,
            "kind": kind,
            "revision": 1,
            "status": "in_progress",
            "answers": {},
            "history": [],
            "drafts": {},
            "report_approval": None,
            "created_at": time.time(),
        }
        with self._db() as db:
            db.execute(
                "INSERT INTO workflows VALUES (?,?,?)",
                (data["id"], self.scope_key, canonical(data)),
            )
        return data

    def list(self):
        with self._db() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT data FROM workflows WHERE scope=? ORDER BY rowid DESC LIMIT 100",
                    (self.scope_key,),
                )
            ]

    def read(self, identifier):
        with self._db() as db:
            return self._read(db, identifier)

    def _mutate(self, identifier, revision, action, key, value, request_key):
        if (
            not isinstance(value, str)
            or len(value) > 50000
            or not isinstance(request_key, str)
            or not 1 <= len(request_key) <= 128
        ):
            raise ValueError("Bounded text and a retry key are required")
        request = canonical([identifier, revision, action, key, value])
        with self._db() as db:
            previous = db.execute(
                "SELECT request,result FROM retries WHERE scope=? AND key=?",
                (self.scope_key, request_key),
            ).fetchone()
            if previous:
                if previous[0] != request:
                    raise WorkflowConflict("Retry key reused for a different answer")
                return json.loads(previous[1])
            data = self._read(db, identifier)
            if type(revision) is not int or data["revision"] != revision:
                raise WorkflowConflict("Workflow changed; reread before correcting")
            if action == "answer":
                valid = {item[0] for item in QUESTIONS[data["kind"]]} | {
                    "notes",
                    "feedback",
                    "mode",
                }
                if key not in valid:
                    raise ValueError("Unknown interview field")
                data["answers"][key] = value
                data["drafts"] = {}
                data["report_approval"] = None
                data["status"] = "in_progress"
            elif action == "draft":
                if key != "runbook":
                    raise ValueError("Only private runbook suggestions can be stored")
                data["drafts"][key] = {
                    "content": value,
                    "status": "draft",
                    "audience": "gm_only",
                    "input_revision": revision,
                }
                data["report_approval"] = None
                data["status"] = (
                    "draft_ready"
                    if all(item[0] in data["answers"] for item in questions_for(data))
                    else "in_progress"
                )
            else:
                raise ValueError("Unsupported operation")
            data["history"].append(
                {
                    "action": action,
                    "field": key,
                    "text": value,
                    "source": "operator" if action == "answer" else "agent_proposal",
                    "time": time.time(),
                }
            )
            data["revision"] += 1
            if len(canonical(data)) > 500000:
                raise ValueError(
                    "Workflow exceeds the bounded context size; start a separate workflow"
                )
            db.execute(
                "UPDATE workflows SET data=? WHERE id=? AND scope=?",
                (canonical(data), identifier, self.scope_key),
            )
            db.execute(
                "INSERT INTO retries VALUES (?,?,?,?)",
                (self.scope_key, request_key, request, canonical(data)),
            )
            return data

    def answer(self, identifier, revision, field, text, request_key):
        return self._mutate(identifier, revision, "answer", field, text, request_key)

    def save_draft(self, identifier, revision, field, text, request_key):
        return self._mutate(identifier, revision, "draft", field, text, request_key)

    def preferences(self):
        with self._db() as db:
            return {
                key: value
                for key, value in db.execute(
                    "SELECT key,value FROM preferences WHERE scope=?", (self.scope_key,)
                )
            }

    def preference(self, key, value):
        choices = {
            "detail": {"short", "balanced", "detailed"},
            "feedback": {"ask", "off"},
            "reminders": {"show", "off"},
        }
        if key not in choices or (value is not None and value not in choices[key]):
            raise ValueError("Only explicit operating preferences are supported")
        with self._db() as db:
            db.execute(
                "INSERT INTO preference_events VALUES (?,?)",
                (
                    self.scope_key,
                    canonical(
                        {
                            "key": key,
                            "value": value,
                            "source": "operator",
                            "time": time.time(),
                        }
                    ),
                ),
            )
            if value is None:
                db.execute(
                    "DELETE FROM preferences WHERE scope=? AND key=?",
                    (self.scope_key, key),
                )
            else:
                db.execute(
                    "INSERT OR REPLACE INTO preferences VALUES (?,?,?)",
                    (self.scope_key, key, value),
                )

    def remind_once(self, identifier, source):
        with self._db() as db:
            self._read(db, identifier)
            return (
                db.execute(
                    "INSERT OR IGNORE INTO reminders VALUES (?,?,?)",
                    (self.scope_key, identifier, source),
                ).rowcount
                == 1
            )

    def packet(self, data):
        answers = data["answers"]
        if data["kind"] == "prep":
            return {
                "status": "draft",
                "audience": "gm_only",
                "runbook": data["drafts"].get("runbook", {}).get("content")
                or "\n\n".join(f"{key}: {value}" for key, value in answers.items()),
            }
        revealed = answers.get("revealed", "")
        revealed = "" if revealed == "[skipped]" else revealed
        report = (
            f"# Session {data['session_id']} recap\n\n{revealed}" if revealed else ""
        )
        return {
            "status": "draft",
            "audience": "gm_only",
            "session_id": data["session_id"],
            "gm_log": "\n\n".join(
                f"{key}: {value}" for key, value in answers.items() if key != "feedback"
            ),
            # Deliberately no model transformation or GM-context summarization.
            "player_report": report,
            "player_report_short": "\n".join(revealed.splitlines()[:5]),
            "candidate_review": answers.get("changes", "Not reviewed"),
            "handoff": {
                "intentions": answers.get("intentions", "Uncertain"),
                "preparation": answers.get("handoff", ""),
            },
            "publication": "unavailable",
            "canon": "unchanged",
        }

    def preview(self, identifier):
        data = self.read(identifier)
        intent = self._report_intent(data)
        return {**intent, "intent_hash": digest(intent)}

    def _report_intent(self, data):
        packet = self.packet(data)
        return {
            "scope": self.scope,
            "workflow_id": data["id"],
            "revision": data["revision"],
            "audience": "group_players",
            "packet": {
                key: packet.get(key, "")
                for key in ("player_report", "player_report_short")
            },
        }

    def approve_report(self, preview):
        # Trusted runner only, after a real interactive exact-preview confirmation.
        with self._db() as db:
            data = self._read(db, preview["workflow_id"])
            intent = self._report_intent(data)
            if (
                preview != {**intent, "intent_hash": digest(intent)}
                or data["kind"] != "debrief"
                or not intent["packet"]["player_report"]
            ):
                raise WorkflowConflict(
                    "Player report or workflow changed; inspect again"
                )
            data["report_approval"] = {
                "intent_hash": preview["intent_hash"],
                "revision": data["revision"],
                "audience": "group_players",
                "status": "approved_to_share",
                "time": time.time(),
            }
            db.execute(
                "UPDATE workflows SET data=? WHERE id=? AND scope=?",
                (canonical(data), data["id"], self.scope_key),
            )
