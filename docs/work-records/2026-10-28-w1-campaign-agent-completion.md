# W1 acceptance: dedicated campaign agent and guarded review

Date: 2026-10-28. Local Windows/PowerShell, Python 3.11, Codex CLI
`0.164.0-alpha.11.1`, branch `codex/local-reconciliation-20261027`.

**W1 meets its sufficient criteria for the local fictional GM workflow.** This
record closes the earlier read-only and review-primitive slices. It does not
claim excellent quality, macOS execution, live campaign attachment/migration,
full release CI, production deployment or human play-testing. W2 is next.

## Delivered behavior

- Durable campaign-only instructions, explicit campaign/GM binding, source
  citations and real source version/hash tokens support fresh conversations.
- The full profile has eight read tools and four guarded request/receipt tools.
  Staging first creates a pending operator request, retaining exact source text,
  attribution, parsed candidates, session ID and retry key. No draft/canon/log is
  accepted until the appropriate separately approved operation succeeds.
- Migration `20261028_0007` creates the separate `campaign_approvals` ledger.
  Approval binds the complete displayed intent and hash, current SQL values,
  draft revision, source/candidate data, campaign/session/binding/role/epoch,
  store paths, process OS identity, expiry and result. Generic context writes and
  model-supplied reviewer/approval labels cannot mint that record.
- The interactive operator console displays the bound review and requires
  `APPROVE <exact-hash>`. Piped confirmations fail. There is no approve/grant
  gateway command or MCP tool. Tests simulate the privileged operator separately;
  they are not evidence that a real DM completed a usability/play-test.
- The executor reserves SQLite's writer and uses caller-owned review
  transactions. Draft changes, promotion/provenance, or log/chunks and receipt
  consumption commit together. Retries return the retained result. Altered,
  stale, expired, revoked, wrong-operator and wrong-scope approvals fail.
- Stable staging retry keys prevent duplicate drafts and reject changed sources
  submitted with the same key. Completed staged receipts provide explicit,
  source-qualified session-to-draft associations for restart/resume; no title
  matching or silent SQL/overlay substitution is introduced.
- A backend health check runs before guarded MCP startup. The SDK stays in its
  isolated environment; a fixed stdio bridge uses the backend Python. The agent
  cannot choose a command, executable, database, root, actor or grant action.
- The dedicated Codex launcher ignores inherited user config, requires the exact
  DMA server/tool profile, disables shell/apps/plugins/browser/delegation, keeps
  a read-only filesystem, and loads the campaign instructions directly. It uses
  existing host authentication without copying credentials or changing global
  config. The final campaign answer prints normally; event evidence is opt-in.

## Acceptance evidence

| W1 criterion | Evidence |
| --- | --- |
| Load the chosen campaign and cite current records | Native Codex read conversation verified binding/GM/epoch, recovered saved sessions, cited an approved log and exact overlay note, and reported a missing NPC as missing. |
| Stage an update honestly | Native agent requested a fictional source, read its pending receipt, and reported that no source draft/fact had been accepted. Unapproved execution was rejected at the backend. |
| Separate trusted approval from the model | Exact fixture intent was checked by a separate test-driver operator; the native agent had no approval-grant capability. Actual console tests reject piped approval and the gateway rejects `approve`. |
| Review and resume in a fresh conversation | A new native Codex conversation read the approved receipt, consumed it once, recovered resulting draft 6/revision 1 through saved associations, cited it and requested a separate deferred candidate decision. The new receipt remained pending. |
| Full connected review flow | A real MCP SDK test opens three fresh processes through pending stage request, separate simulated operator grant, staged draft, candidate acceptance, promotion, distinct log approval, provenance and restart, including identical source citations and retained completed retries. |
| Missing/unavailable and conflict behavior | Tests reject unknown tools, authority/path overrides, stale/changed sources and candidates, foreign binding/epoch/operator, revoked/expired receipts and changes during execution. Transport timeout/cancellation stops the child and reports an unconfirmed result rather than inventing success. |
| Campaign/development privilege separation | Native inventory still advertises `apply_patch`; the campaign role refused it. That refusal alone was not treated as enforcement proof. A direct installed-Codex read-only sandbox canary could read the disposable file, but its write received `Access is denied` and the file stayed unchanged. Shell, browser, apps and grant tools were unavailable. |

Native evidence is retained only in the ignored
`.codex-temp/w1-complete-fixture-20261028/` workspace:

- `host-read-session-2.jsonl`: grounded reads and missing-source behavior.
- `host-stage-session.jsonl`: initial pending request; its first execute attempt
  stopped at a generic host prompt, so it was not counted as a backend denial.
- `host-receipt-denial-session.jsonl`: actual backend rejection of the unapproved
  receipt after narrowly configuring transport permission for that endpoint.
- `simulated-operator-stage-approval.json`: explicitly labelled operator simulation
  of the exact fictional source, never a human-approval or real-campaign claim.
- `host-resume-review-session.jsonl` and `native-resume-review.txt`: fresh native
  conversation, actual staged save and source-qualified pending review request.
- `campaign-workspace/development-canary.txt`: stayed `Fixture canary: unchanged`.

The configured `review_execute` transport permission permits an invocation, not
application approval. The native denial and SDK adversarial tests demonstrate
the independent ledger check. Instructions plus MCP annotations alone would not
provide that boundary. The initial attempt disabling Code Mode also disabled
MCP dispatch; its failure was corrected by enabling only the client's isolated
tool router, without enabling shell or application/development connectors.

The canary's first native model attempt refused the instruction; direct sandbox
testing then established enforcement. The installed CLI selects Windows with
`codex sandbox -- <command>`; an initial `windows` argument was treated as a
command, and a per-user Python install could not be spawned by the restricted
account. The successful test used the system PowerShell executable: read
succeeded, `Set-Content` raised `UnauthorizedAccessException`, and content was
unchanged. No sandbox/permission/hook-trust bypass flag was used.

## Automated verification

- **63 backend tests passed**: approval/staging and adversarial receipt cases,
  consistent restore epoch invalidation, existing transaction guards, review
  APIs, parser, ingestion, trusted legacy import and document behavior.
- **35 host/MCP tests passed** in the isolated SDK environment: reader, fixed
  gateway/error handling, restrictive launcher configuration, original read-only
  protocol and full guarded protocol/resume flow.
- **4 CLI/onboarding/recovery tests passed**: both fixture profiles, migration
  through 0007, actual console refusal of piped confirmation, unavailable grant
  command, and paired restore. No test skip substitutes for these protocol checks.
- **4 OS-identity tests passed**: misleading `USER`/`USERNAME`/`LOGNAME` values
  cannot supply identity, OS lookup failures stop approval rather than falling
  back to a reviewer label, and the POSIX UID branch has deterministic coverage.
  This branch test does not establish macOS runtime support.

That is **106 distinct focused tests**. A repeated 43-test security subset passed
under standard-library line tracing. Executable-line coverage was **94.5%**
(308/326) for the approval workflow, **100%** (17/17) for OS identity and **89.3%**
(67/75) for the gateway client. The ignored report is
`.codex-temp/w1-approval-coverage.json`; compiler line zero is excluded because it
is not a source statement. These are module line metrics, not branch or
repository-wide coverage claims.

Focused Ruff, Black and local documentation-link checks passed, as did
`git diff --check` (existing line-ending normalization warnings only). Tests
report the existing Starlette/AnyIO deprecation warning. Windows async tests
needed execution outside the restricted outer sandbox and new disposable
basetemp directories; no real campaign was selected. Existing full-repository
release gates and unrelated prior AoN/static findings remain separate; no full-CI
or release-readiness claim is made.

## Review rejections and retained boundaries

Automatic approval review rejected a custom-hook proposal because it bypassed
hook trust and allowed broad execution names. That code was not added or run.
The safer implementation retains the native read-only sandbox and verifies it
directly. Another rejected proposal would have removed recovery-epoch and
physical-store filters from session-association reads; those filters remain
intact. A consistent-restore test confirms old receipts and staged links do not
silently acquire a new scope. Neither rejection was bypassed or overridden.

## Limits and next work

The full deployment remains fixture-only at its console/gateway boundary. Live
attachment requires a reviewed binding/backup/onboarding plan and authorization;
no real overlay or campaign DB was read, copied or migrated here. Restoring or
relocating a pair requires stopped writers, epoch reconciliation and explicit
operator rebinding of associations. The agent never repairs scope by guessing
IDs or refreshing an expected token automatically.

The initial review fingerprint is deliberately conservative: every entity and
relationship row participates and displayed intent is capped at 500 KB. It can
invalidate approval on an unrelated world edit; narrowing it is a later quality
improvement. SQLite locking does not make external file writes transactional;
binding/association files are operator configuration and must be quiesced during
recovery/reconfiguration. Other DB engines and a compromised OS/operator account
are outside the verified boundary. Native `apply_patch` remains advertised but
does not receive write authority. The simple console is not yet a polished DM
review UI. macOS execution and representative human interaction are unverified.

Next is W2 guided/resumable debrief, uncertain/conflicting recollections,
corrections, GM log/player-report separation and next-session intentions. Reuse
these receipts and existing provenance rather than restoring archived panel
modules. Discord, live/overlay mutations, source acquisition and publication
remain unavailable. Current Combat stays card-based; all ten archived modules
remain archived. Nothing was committed, pushed or deployed.
