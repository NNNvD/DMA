# DMA Local Setup Guide For Complete Beginners

This guide explains how to put the DMA on a personal computer and open the same kind of DM Panel used by the GM.

It assumes:

- you have Google Chrome installed
- you are comfortable following steps carefully, even if you have never used GitHub or Python before
- the GM will give you a separate folder named `local-private-overlay`

The `local-private-overlay` folder contains private campaign material. It is not stored on public GitHub for copyright reasons.

## What You Are Installing

You will install:

- a free GitHub account
- GitHub Desktop, which downloads the project from GitHub
- Python, which runs the DMA backend
- the DMA project files
- the private campaign overlay from the GM

When finished, you will open the DMA in Chrome at:

`http://127.0.0.1:8006/dm-panel`

## Step 1: Create A GitHub Account

1. Open Chrome.
2. Go to `https://github.com/`.
3. Click `Sign up`.
4. Follow GitHub's instructions to create an account.
5. Verify your email address if GitHub asks you to.

Keep your GitHub username and password somewhere safe.

Official GitHub account help:

`https://docs.github.com/en/get-started/start-your-journey/creating-an-account-on-github`

## Step 2: Install GitHub Desktop

GitHub Desktop is the easiest way to download the project without learning Git commands first.

1. Go to `https://desktop.github.com/`.
2. Download GitHub Desktop for your computer.
3. Install it.
4. Open GitHub Desktop.
5. Sign in with the GitHub account you created.

Official GitHub Desktop help:

`https://docs.github.com/en/desktop`

## Step 3: Download The DMA Repository

1. In Chrome, go to the DMA GitHub repository.
2. Click the green `Code` button.
3. Choose `Open with GitHub Desktop`.
4. GitHub Desktop will ask where to store the project.
5. Choose a location you can find again, such as:

Windows:

`C:\Users\YOUR-NAME\Documents\DMA`

macOS:

`/Users/YOUR-NAME/Documents/DMA`

6. Click `Clone`.

After cloning, you should have a folder on your computer containing files such as:

- `README.md`
- `Makefile`
- `backend`
- `docs`
- `scripts`

This folder is called the repository root.

## Step 4: Install Python

DMA runs on Python.

1. Go to `https://www.python.org/downloads/`.
2. Download the current Python 3 installer for your computer.
3. Run the installer.

Important on Windows:

- tick the checkbox called `Add python.exe to PATH` before clicking install
- if you miss this checkbox, Python may install but commands may not work

Important on macOS:

- install the standard Python 3 package from `python.org`
- after installing, you may need to close and reopen Terminal

Check that Python works.

Windows:

1. Open the Start menu.
2. Type `PowerShell`.
3. Open Windows PowerShell.
4. Type:

```powershell
python --version
```

macOS:

1. Open `Terminal`.
2. Type:

```bash
python3 --version
```

You should see a Python 3 version number.

Official Python download page:

`https://www.python.org/downloads/`

## Step 5: Open A Terminal In The DMA Folder

You now need to run commands from the repository root.

### Windows

1. Open the DMA folder in File Explorer.
2. Click the address bar at the top.
3. Type `powershell`.
4. Press Enter.

PowerShell should open inside the DMA folder.

### macOS

1. Open Terminal.
2. Type `cd ` with a space after it.
3. Drag the DMA folder into the Terminal window.
4. Press Enter.

The command will look something like:

```bash
cd /Users/YOUR-NAME/Documents/DMA
```

## Step 6: Create The Local Settings File

In the terminal, run:

Windows:

```powershell
copy .env.example .env
```

macOS:

```bash
cp .env.example .env
```

Open the new `.env` file in a text editor.

For the Abomination Vaults setup, make sure these lines are present:

```env
DATABASE_URL=sqlite+aiosqlite:///./dma-abomination-vaults.db
OBSIDIAN_VAULT_PATH=./obsidian-abomination-vaults-vault
REFERENCE_PDF_ROOT=./assets/imports/misc/private-local/reference/raw
DUNGEON_MAP_ROOT=./assets/imports/misc/private-local/media
DUNGEON_ROOM_KEY_ROOT=./assets/imports/misc/private-local/room-keys
```

If `DATABASE_URL` says `./dma.db`, change it to `./dma-abomination-vaults.db`.

You do not need an OpenAI API key for the basic local panel to open. Leave:

```env
EMBEDDING_PROVIDER=disabled
OPENAI_API_KEY=
```

Optional: keep the text-to-speech engine on browser mode unless the GM has given
you separate Piper instructions.

```env
TTS_PROVIDER=browser
PIPER_BINARY_PATH=piper
PIPER_VOICE_PATH=
```

## Step 7: Install DMA Python Packages

From the repository root, run:

Windows:

```powershell
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.txt
```

macOS:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r backend/requirements-dev.txt
```

This may take a few minutes.

If you get a permissions error, tell the GM. Do not randomly delete files.

## Step 8: Add The Private Campaign Overlay

The public GitHub repo does not include copyrighted or private campaign files.

The GM should give you a folder named:

`local-private-overlay`

Place that folder directly inside the DMA repository root.

Your DMA folder should then contain:

- `backend`
- `docs`
- `scripts`
- `local-private-overlay`
- `README.md`

Inside `local-private-overlay`, there should be:

`local-private-overlay/project-root/`

That folder mirrors the DMA project structure. It contains private local material such as:

- `dma-abomination-vaults.db`
- `obsidian-abomination-vaults-vault`
- private reference PDFs
- map images
- room keys
- campaign-specific local notes and metadata

Now install the overlay.

Windows:

```powershell
Copy-Item -Recurse -Force .\local-private-overlay\project-root\* .
```

macOS:

```bash
scripts/install_private_overlay.sh
```

Alternative macOS command:

```bash
cp -R local-private-overlay/project-root/. .
```

After this step, your DMA folder should contain:

- `dma-abomination-vaults.db`
- `obsidian-abomination-vaults-vault`
- `assets/imports/misc/private-local`

These are local-only files. Do not upload them to GitHub.

## Step 9: Start The DMA Backend

From the repository root, run:

Windows:

```powershell
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8006
```

macOS:

```bash
python3 -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8006
```

Leave this terminal window open.

You should see text that includes:

```text
Uvicorn running on http://127.0.0.1:8006
```

If Windows Firewall asks for permission, allow access for private networks.

## Step 10: Open The DMA Panel In Chrome

Open Chrome and go to:

`http://127.0.0.1:8006/dm-panel`

You should see the DMA DM Panel with modules such as:

- Map Room
- Campaign Overview
- Session Overview
- PC Sheet Viewer
- NPC Dossier Viewer
- DMA Chat Workbench
- Dice Roller
- Reference PDFs

Click `Launch Current Session` near the top.

For the current Abomination Vaults setup, this should load:

- the active session around Level 3 area C7
- GM and PC campaign summaries
- the map room
- PC and NPC overview tools

## Step 11: Check That The Private Material Loaded

In the DMA panel:

1. Open `Campaign Overview`.
2. Click the `GM Summary` and `PC Summary` tabs.
3. Open `Session Overview`.
4. Look for `Session 04 - Level 3 C7 Start`.
5. Open `Map Room`.
6. Check that dungeon maps appear in the dropdown.
7. Open `PC Sheet Viewer`.
8. Check that PCs appear.
9. Open `NPC Dossier Viewer`.
10. Check that NPCs appear.

If maps, PDFs, or vault notes are missing, the private overlay was probably not copied into the correct place.

## Step 12: How To Stop DMA

Go back to the terminal window where the backend is running.

Press:

```text
Ctrl + C
```

The DMA backend will stop.

To start it again later, repeat Step 9 and Step 10.

## Troubleshooting

### Chrome Says The Site Cannot Be Reached

The backend is probably not running.

Go back to Step 9 and start the backend again.

### The Page Opens But Looks Empty

The private overlay may not be installed.

Check that these exist in the DMA folder:

- `dma-abomination-vaults.db`
- `obsidian-abomination-vaults-vault`
- `assets/imports/misc/private-local`

Also check that `.env` contains:

```env
DATABASE_URL=sqlite+aiosqlite:///./dma-abomination-vaults.db
```

### Python Command Not Found On Windows

Python may not have been added to PATH.

Try:

```powershell
py --version
```

If that works, use `py` instead of `python`:

```powershell
py -m pip install -r backend/requirements-dev.txt
py -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8006
```

If that does not work, reinstall Python and make sure `Add python.exe to PATH` is checked.

### Permission Or Security Warning On macOS

macOS may ask whether Terminal can access files in Documents, Desktop, or Downloads.

Allow access if the DMA folder is stored there.

### Port 8006 Is Already In Use

Something else is already using the DMA port.

Use another port, for example `8007`.

Windows:

```powershell
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8007
```

macOS:

```bash
python3 -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8007
```

Then open:

`http://127.0.0.1:8007/dm-panel`

## Updating Later

When the GM says there is an update:

1. Open GitHub Desktop.
2. Open the DMA repository.
3. Click `Fetch origin`.
4. Click `Pull origin` if GitHub Desktop offers it.
5. If the GM also gives you a new `local-private-overlay`, replace your old one and repeat Step 8.
6. Start DMA again.

## Important Copyright Reminder

The private overlay is for local use by people who are allowed to use the campaign material.

Do not:

- upload `local-private-overlay` to GitHub
- upload the adventure PDFs
- upload official map images
- upload extracted art from PDFs
- share the private overlay publicly

The public GitHub repo contains the DMA tool. The private overlay contains campaign material that must stay local.
