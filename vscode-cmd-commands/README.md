# VSCode Cmd Commands — StreamDock plugin

Per-key user-defined shell command chains, executed in the workspace of the
VS Code window currently in focus. Built for **Ajazz AKP05E_3A3D** /
StreamDock-compatible keypads.

When you press the assigned key, the plugin:

1. Detects the workspace path of the focused VS Code window (Win32 foreground
   API → fallback to VS Code's recently-opened list).
2. Runs the configured `commands` list sequentially in that directory, one
   command per `subprocess.run` with `shell=True` (so pipes, redirects, and
   shell builtins work).
3. Stops on the first non-zero return code (fail-fast). The failing command's
   1-based index is shown on the key as `ERR N`.

Each key has its own `title` and `commands` list — bind one key to
`npm run build && npm test`, another to your TAUSIK bootstrap, another to
`git pull && code .`, whatever you need.

## Requirements

- Windows 10+ (the foreground detector uses Win32 only)
- StreamDock app installed and connected to your Ajazz device
- Anything you reference in your commands must be on `PATH` for the user
  that runs StreamDock

## Build

```powershell
cd utils\vscode-cmd-commands
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -m PyInstaller main.spec --noconfirm
```

The build output is `dist\VSCodeCmd.exe` (single-file, ~10 MB).

## Install into StreamDock

1. Copy `com.vscode.cmd.sdPlugin\` into the StreamDock plugins folder:
   ```
   %APPDATA%\HotSpot\StreamDock\Plugins\com.vscode.cmd.sdPlugin\
   ```
2. Copy `dist\VSCodeCmd.exe` next to the manifest, replacing any previous
   build:
   ```
   %APPDATA%\HotSpot\StreamDock\Plugins\com.vscode.cmd.sdPlugin\VSCodeCmd.exe
   ```
3. Restart StreamDock so it picks up the new plugin.
4. Drag the **Run Commands** action onto a key.

## Configuration

Open the action's property inspector and set:

- **Title** — text shown on the key when idle (defaults to `Run` if empty).
- **Commands** — ordered list of shell command strings. Use **+ add command**
  to append a row, **×** to remove one. Empty rows are treated as failures
  (cannot run an empty shell line).

The values are stored per-key, so each key on the device runs its own chain.

## Button states

| State | Meaning | Title |
|-------|---------|-------|
| 0 — idle | Ready / last run succeeded | `<your title>` (or `Run`) |
| 1 — busy | Chain in flight | `...` |
| 2 — error | Last run failed | `ERR N` / `NO CMD` / `NO VSC` / `CRASH` |

`ERR N` = command at 1-based position `N` exited with a non-zero code (the
remaining commands were skipped). A failed run also calls `showAlert`.
Detailed errors land in:

```
%APPDATA%\HotSpot\StreamDock\Plugins\com.vscode.cmd.sdPlugin\logs\plugin.log
```

## VS Code workspace detection

Two strategies, tried in order:

1. **Foreground (priority).** `GetForegroundWindow` → process name must equal
   `Code.exe` → window title is parsed (ends with ` - Visual Studio Code`)
   → folder name is cross-referenced against the recently-opened list to
   resolve to an absolute path.
2. **Fallback.** Most-recent entry from VS Code's recents:
   - `%APPDATA%\Code\User\globalStorage\state.vscdb`
     (key `history.recentlyOpenedPathsList`, modern)
   - `%APPDATA%\Code\User\globalStorage\storage.json` (legacy)
   - `%APPDATA%\Code\storage.json` (older legacy)

If neither yields a workspace, the button transitions to error with
`NO VSC`.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Title `NO CMD` after press | Commands list is empty. Add at least one row in the property inspector. |
| Title `NO VSC` after press | No VS Code window is focused **and** the recents list is unreadable. Open VS Code on the project once, then press again. |
| Title `ERR N` after press | Command `N` (1-based) returned a non-zero exit code. Check `plugin.log` for the captured stderr. |
| Title `CRASH` after press | Unexpected exception in the action handler. Open `plugin.log` for the traceback. |
| Plugin never appears in StreamDock | Manifest copied to wrong folder, or `VSCodeCmd.exe` is missing next to `manifest.json`. |

## Layout

```
utils/vscode-cmd-commands/
├── com.vscode.cmd.sdPlugin/      # the plugin folder StreamDock loads
│   ├── manifest.json             # action UUID com.vscode.cmd.run
│   ├── propertyInspector/run/    # html + js for the title + commands rows
│   └── static/                   # icons + sdpi.css + common.js
├── src/
│   ├── core/                     # Action / Plugin / Logger / Timer / Factory
│   ├── actions/run.py            # the on_key_up handler (threaded)
│   └── utils/
│       ├── vscode_detector.py    # foreground + recents resolution
│       └── command_runner.py     # generic fail-fast shell-command chain
├── tests/                        # pytest, no network, all subprocess mocked
├── main.py                       # WS connect entrypoint
├── main.spec                     # PyInstaller spec (hiddenimports configured)
└── requirements.txt
```

## Tests

```powershell
venv\Scripts\python -m pytest tests/ -v
```

All subprocess and Win32 calls are mocked — no network and no StreamDock
required.

## Security note

Commands are passed to the shell with `shell=True`, so anything you put in
the property inspector runs with your user privileges. The settings live
inside the StreamDock app's per-key state on the local machine, so this is
a local-trust tool — don't expose the StreamDock settings file to others.
