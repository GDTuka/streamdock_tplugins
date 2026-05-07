# programming-keyboard-utils

StreamDock plugins for the **Ajazz AKP05E_3A3D** keypad (and other
StreamDock-compatible devices), aimed at keeping a developer's hands on the
keypad instead of the mouse.

Each plugin is self-contained — its own venv, its own PyInstaller build, its
own StreamDock manifest. See the per-project README for build and install
steps.

## Projects

### [vscode-project-open](./vscode-project-open/)

One-tap launch of VS Code on a per-key configured project path. Press a key,
VS Code opens (or focuses, if already open) on that folder. Bind one key per
project to jump between them.

### [vscode-cmd-commands](./vscode-cmd-commands/)

Per-key user-defined shell command chains, executed in the workspace of the
VS Code window currently in focus. Detects the focused VS Code window, then
runs the configured commands sequentially in that directory (fail-fast). Use
it to bind a key to `npm run build && npm test`, a TAUSIK bootstrap, a
`git pull`, or any other chain you'd otherwise type by hand.
