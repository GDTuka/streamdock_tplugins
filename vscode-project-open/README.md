# VSCode Open Project — StreamDock plugin

One-tap launch of VS Code on a per-key configured project path. Built for
**Ajazz AKP05E_3A3D** / StreamDock-compatible keypads.

When you press the assigned key, the plugin spawns `code <path>` non-blocking.
VS Code's CLI is idempotent: if a window already has that folder open, it
just focuses that window instead of creating a duplicate.

Each key has its own `path` setting and its own title (set in StreamDock's
standard key panel) — bind one key per project to jump between them.

## Requirements

- Windows 10+
- StreamDock app installed and connected to your Ajazz device
- VS Code installed with the `code` CLI on PATH (the installer's
  "Add to PATH" option). The plugin also probes `code.cmd` and `code.exe`
  as fallbacks.

## Build

```powershell
cd utils\vscode-project-open
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -m PyInstaller main.spec --noconfirm
```

The build output is `dist\VSCodeOpen.exe` (single-file).

## Install into StreamDock

1. Copy `com.vscode.open.sdPlugin\` into the StreamDock plugins folder:
   ```
   %APPDATA%\HotSpot\StreamDock\Plugins\com.vscode.open.sdPlugin\
   ```
2. Copy `dist\VSCodeOpen.exe` next to the manifest:
   ```
   %APPDATA%\HotSpot\StreamDock\Plugins\com.vscode.open.sdPlugin\VSCodeOpen.exe
   ```
3. Restart StreamDock so it picks up the new plugin.
4. Drag the **Open Project** action onto a key.

## Configuration

Open the action's property inspector and set:

- **Project path** — absolute folder path (e.g. `C:\Work\my-app`).

Set the key's title in StreamDock's standard key panel (it's enabled —
`UserTitleEnabled: true`). Use it to label different projects on different
keys.

## Button states

| State | Meaning | Title |
|-------|---------|-------|
| 0 — idle | Ready / VS Code launched | `<your title>` (or `Open`) |
| 1 — error | Last press failed | `NO PATH` / `NO DIR` / `NO CODE` / `ERR` / `CRASH` |

There is no busy state — `subprocess.Popen` returns immediately and VS
Code starts asynchronously in its own process.

A failed run also calls `showAlert`. Detailed errors land in:

```
%APPDATA%\HotSpot\StreamDock\Plugins\com.vscode.open.sdPlugin\logs\plugin.log
```

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Title `NO PATH` after press | Property inspector "Project path" is empty. |
| Title `NO DIR` after press | The configured path doesn't exist or is not a directory. |
| Title `NO CODE` after press | Neither `code`, `code.cmd`, nor `code.exe` is on PATH. Re-run the VS Code installer with "Add to PATH". |
| Title `ERR` after press | `code` was found but spawning failed (rare — permissions, anti-virus). Check `plugin.log`. |
| Plugin never appears in StreamDock | Manifest copied to wrong folder, or `VSCodeOpen.exe` is missing next to `manifest.json`. |

## Layout

```
utils/vscode-project-open/
├── com.vscode.open.sdPlugin/     # the plugin folder StreamDock loads
│   ├── manifest.json             # action UUID com.vscode.open.run
│   ├── propertyInspector/run/    # html + js for the path input
│   └── static/                   # icons + sdpi.css + common.js
├── src/
│   ├── core/                     # Action / Plugin / Logger / Timer / Factory
│   ├── actions/run.py            # the on_key_up handler (threaded)
│   └── utils/
│       └── vscode_opener.py      # subprocess.Popen wrapper, never raises
├── tests/                        # pytest, all subprocess calls mocked
├── main.py                       # WS connect entrypoint
├── main.spec                     # PyInstaller spec
└── requirements.txt
```

## Tests

```powershell
venv\Scripts\python -m pytest tests/ -v
```
