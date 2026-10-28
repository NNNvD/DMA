# DMA agent on another computer

The development branch includes agent instructions, database migrations, dependency
manifests, MCP reader/gateway, fixture and rehearsal generators, guided runner and
browser/API source. Generated bindings and private campaign stores are local inputs.
Windows/Python 3.11 is verified; macOS/Linux commands below remain untested.

## Get the code and install both environments

For a fresh clone, choose a new directory and check out the development branch:

```sh
git clone --branch codex/dma-agent-and-in-game-state-20261028 https://github.com/NNNvD/DMA.git DMA-main
cd DMA-main
```

For an existing checkout, preserve local edits before switching branches. Use
Python 3.11 and an installed, authenticated Codex CLI available on PATH. The native
launcher has been verified with CLI 0.164.0-alpha.11.1; repeat host/tool checks when
using another version. See [host restrictions](25-campaign-agent-review-and-acceptance.md).

Windows PowerShell:

```powershell
python -m venv .venv
& .venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
python -m venv .codex-temp/agent-env
& .codex-temp/agent-env/Scripts/python.exe -m pip install -r backend/requirements-agent-dev.txt
& .venv/Scripts/python.exe -m scripts.prepare_campaign_agent_fixture --workspace .codex-temp/w1-demo --agent-python .codex-temp/agent-env/Scripts/python.exe --review-tools
& .venv/Scripts/python.exe -m scripts.run_guided_campaign --binding .codex-temp/w1-demo/binding.json --kind prep --session next-session --mode guided
```

macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
python3 -m venv .codex-temp/agent-env
.codex-temp/agent-env/bin/python -m pip install -r backend/requirements-agent-dev.txt
.venv/bin/python -m scripts.prepare_campaign_agent_fixture --workspace .codex-temp/w1-demo --agent-python .codex-temp/agent-env/bin/python --review-tools
.venv/bin/python -m scripts.run_guided_campaign --binding .codex-temp/w1-demo/binding.json --kind prep --session next-session --mode guided
```

Run from the repository root and use a new workspace when generating a profile.
Keep the MCP environment separate because its Pydantic requirements differ from
the backend. The backend interpreter runs operator commands; the generator records
the isolated interpreter for MCP. No generated credentials belong in Git.
Use `--codex "<installed CLI path>"` on the runner if Codex is absent from PATH.
For protocol verification, follow [the connection checks](24-campaign-agent-setup.md).

## Use private campaign material

Acquire the latest `local-private-overlay/` bundle manually from the GM through
the approved private channel. Place it at the repository root, retaining
`local-private-overlay/project-root/`. Obtain the matching campaign SQLite store
privately as well; GitHub does not distribute campaign state, PDFs or maps.
Keep source writers stopped during paired copying. Obtain explicit authorization
before sending selected private/GM material to the model service.

Create a fresh rehearsal binding on the destination computer using
`scripts.prepare_private_rehearsal` with explicit `--source-db`, `--source-private`,
`--workspace`, `--agent-python`, `--campaign` and `--session` arguments. The private
root argument names the overlay's `assets/imports/misc/private-local` directory;
the workspace must be a new directory under `.codex-temp/`. See
[the rehearsal contract](29-private-rehearsal.md). This copies and verifies the
selected stores before migrating the copy; it does not activate the live campaign.

Run `scripts.serve_private_rehearsal --binding "<workspace>/binding.json"` with
the backend interpreter and open its printed localhost URL. Use the same binding
with `scripts.run_guided_campaign` for preparation or debrief, and the exact
session ID selected during generation. See [runner commands](28-guided-agent-prototype.md).

Bindings/config templates contain physical paths; approvals, associations and
guided preferences are scoped to paths, operator and recovery epoch. Do not copy
this computer's virtual environments or reuse its generated approvals/bindings
as a portable profile. A fresh profile starts new workflow state. Continuing old
rehearsal history requires a separately reviewed recovery/rebinding operation,
including the private `guided-workflows.sqlite3` sidecar. Keep those files private.

The full guided manual, canonical closure integration and automatic Discord
publication remain outside this prototype's completed scope.
