# dsh-pet-lulu 🐹 Capybara Lulu desktop pet

> **English** | [简体中文](README.md)

A cute capybara desktop pet plugin for DeepSeek Harness (dsh) with **three
render modes**:

* **Web pet (default)** — a floating pet in a browser page: draggable,
  click-to-pet, feed, sleep, with a live status bubble. `python -m dsh_pet`
  opens the page directly;
* **Terminal pet (ANSI)** — truecolor half-block animation in the terminal
  with keyboard interaction (`--renderer ansi`);
* **Window pet (Tk)** — a standalone Tkinter window with mouse interaction
  (`--gui`).

> Artwork comes from [czy666chen/lulu](https://github.com/czy666chen/lulu)
> (MIT) and [srwang0506/HatchPet-CapybaraLulu](https://github.com/srwang0506/HatchPet-CapybaraLulu)
> (Apache-2.0). See [`dsh_pet/assets/SOURCES.md`](dsh_pet/assets/SOURCES.md)
> for sources and licenses.

![Preview](docs/preview.gif)

---

## Table of contents

1. [Features](#features)
2. [Installation](#installation)
3. [Choosing a mode](#choosing-a-mode)
4. [Web mode (default)](#web-mode-default)
5. [Terminal mode (ANSI)](#terminal-mode-ansi)
6. [Window mode (Tk)](#window-mode-tk)
7. [dsh integration](#dsh-integration)
8. [Configuration](#configuration)
9. [Keyboard / mouse interactions](#keyboard--mouse-interactions)
10. [Tests](#tests)
11. [Project structure](#project-structure)
12. [Assets & licenses](#assets--licenses)
13. [FAQ / troubleshooting](#faq--troubleshooting)
14. [Acceptance checklist](#acceptance-checklist)

---

## Features

* **Animation system**: idle breathing/blinking loop, random actions
  (walk, jump, yawn, glance around); configurable frame rate (default
  10 FPS) with frame-loop throttling (target <5% of a single core).
* **Interactions**:
  * web mode: click to pet, drag to reposition (position remembered),
    hover panel (feed / sleep / hide), summon button, keys `f/p/s/h/q`;
  * terminal mode: `f` feed, `p` pet, `s` sleep/wake, `q` quit;
  * Tk window mode: mouse click triggers a random reaction;
  * one-shot reactions play once and return to idle.
* **Status bubble**: realtime dsh task status above the pet (task name,
  progress bar, GPU temperature). A built-in mock source is the default;
  real dsh data hooks are reserved.
* **Three render modes / two sprite packs**: `web` (default) / `ansi` / `tk`;
  switch pets with `pet_type = lulu | capybara`.

## Installation

Requirements: Python 3.8+. [Pillow](https://pypi.org/project/Pillow/) is an
optional dependency for parsing the spritesheets (without it the terminal
pet falls back to built-in ASCII pixel art; web mode needs Pillow to build
the sprite strips).

```sh
# Recommended: install from source with Pillow
pip install -e ".[sprites]"

# Or core only (no Pillow)
pip install -e .
```

You can also run it directly from the repository root:

```sh
python -m dsh_pet            # or bin/dsh-pet (Windows: bin\dsh-pet.cmd)
```

Install the dsh plugin (optional, see [dsh integration](#dsh-integration)):

```sh
dsh plugin --profile pet add <path>/plugins
```

## Choosing a mode

| Mode | Command | Notes |
| --- | --- | --- |
| **web (default)** | `python -m dsh_pet` | Opens the browser pet page (`http://127.0.0.1:8765`) |
| Terminal | `python -m dsh_pet --renderer ansi` | Fullscreen terminal TUI |
| Window | `python -m dsh_pet --gui` | Standalone Tkinter window |

`--renderer` accepts `auto` (same as web) / `ansi` / `tk` / `web`.
Persist the choice in the config file with `[renderer] mode = web | ansi | tk | auto`.

## Web mode (default)

### Launch

```sh
python -m dsh_pet                        # opens the browser (default port 8765)
python -m dsh_pet --no-browser           # serve only, no browser (remote/tests)
python -m dsh_pet --port 9000            # change the port
python -m dsh_pet --pet-type capybara    # switch to the high-res capybara pack
python -m dsh_pet --fps 15               # frame rate
python -m dsh_pet --status-source file --status-file /path/status.json
```

### Page interactions

* **Click the pet** → pet it (bubble feedback, one-shot reaction)
* **Drag the pet** → reposition (remembered in localStorage)
* **Hover the pet** → panel with `Feed` / `Sleep` / `Hide`
* **After hiding** → a `Summon` button appears bottom-right
* **Keys**: `f` feed · `p` pet · `s` sleep/wake · `h` hide · `q` close the page
* **Status bubble**: live task name, progress bar and GPU temperature
  (mock data by default)

### HTTP API (for scripts / other apps)

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/` | GET | The pet page |
| `/api/manifest` | GET | Pet manifest (atlas geometry, animation tracks) |
| `/api/state` | GET | Live state (behaviour/clip/bubble/visibility/sleeping) |
| `/api/sheet/<clip>.png` | GET | Sprite strip image for one animation clip |
| `/api/interact` | POST | `{"kind":"pet"|"feed"}` pet / feed |
| `/api/sleep` | POST | Toggle sleep |
| `/api/random` | POST | Trigger one random action |
| `/api/hide` / `/api/summon` | POST | Hide / summon |
| `/api/quit` | POST | Shut the server down and exit |

## Terminal mode (ANSI)

```sh
python -m dsh_pet --renderer ansi                 # terminal TUI
python -m dsh_pet --renderer ansi --width 60      # pet width in characters
python -m dsh_pet --renderer ansi --fps 15        # frame rate
python -m dsh_pet --renderer ansi --no-hint       # hide the key hint line
python -m dsh_pet --renderer ansi --bg-color 1e1e2e
```

* Keys: `f` feed · `p` pet · `s` sleep/wake · `q` / `Ctrl+C` quit
* On exit the cursor and screen are restored (alternate screen buffer);
  terminal resizes are handled.
* Windows: VT mode is enabled automatically (Windows 10+ / Windows Terminal
  need no extra setup).

## Window mode (Tk)

```sh
python -m dsh_pet --gui
python -m dsh_pet --gui --scale 4        # pixel scale factor
python -m dsh_pet --gui --bg-color 1e1e2e
```

* Mouse click on the pet → random reaction; keys `f/p/s/q` work as in
  terminal mode.
* Falls back to ANSI terminal mode when no display server is available.

## dsh integration

`dsh` is a Node.js (Cordis) implementation. This plugin spawns the Python
pet as a **subprocess** and passes task status through a **JSON file**, so
it never blocks the dsh main process.

### Install

```sh
# 1. create the pet profile and install the plugin package (replace <path>)
dsh plugin --profile pet add <path>/pluginss

# 2. put the content of plugins/pet.profile.yml into
#    $DSH_HOME/profiles/pet/cordis.patch.yml (append the insert row if it exists)
```

Example `plugins/pet.profile.yml`:

```yaml
- insert:
    - id: dsh-pet
      name: '@dsh-pet/plugin'
      config:
        pythonBin: python            # python interpreter
        packageDir: 'D:\...\dsh-pet-lulu'   # repo path when not pip-installed (or set DSH_PET_HOME)
```

### Run

```sh
dsh --profile pet pet                              # default: web pet (opens the browser)
dsh --profile pet pet --mode terminal              # terminal TUI
dsh --profile pet pet --mode tk                    # Tk window
dsh --profile pet pet --pet-type capybara \
    --status-source file --status-file .dsh_pet_status.json
dsh --profile pet pet --help                       # all options
```

The `pet` subcommand accepts the same options as the Python CLI: `--mode`,
`--pet-type`, `--renderer`, `--gui`, `--fps`, `--width`, `--bg-color`,
`--port`, `--no-browser`, `--status-source`, `--status-file`, `--config`,
`--no-hint`.

### Task status pipeline

* With `--status-source file` the plugin keeps writing demo task progress to
  the status file and the pet bubble shows it live — the "dsh task progress"
  genuinely comes from the dsh side;
* Other dsh plugins can push real status through the provided
  `petStatus.update({task_name, phase, progress, gpu_temp, message})` service;
* Status file shape:

```json
{"task_name": "...", "phase": "running", "progress": 42.0,
 "gpu_temp": 61.0, "message": "..."}
```

### Literal `dsh pet`

The launcher only hardcodes the `web` alias, so the literal `dsh pet` needs
a shell alias:

```powershell
# PowerShell
function dsh-pet { dsh --profile pet pet @args }
```

```sh
# bash / zsh
alias dsh-pet='dsh --profile pet pet'
```

## Configuration

Copy [`.dsh_pet_config.example`](.dsh_pet_config.example) to
`.dsh_pet_config` (in the current directory or `~`), or pass `-c <path>`.
Every key is optional:

| Section | Key | Default | Purpose |
| --- | --- | --- | --- |
| `[general]` | `pet_type` | `lulu` | Sprite pack: `lulu` / `capybara` |
| | `log_level` | `info` | `debug` / `info` / `warning` / `error` |
| `[animation]` | `fps` | `10` | Frames per second |
| | `random_action_interval` | `12.0` | Seconds between random actions |
| | `random_action_chance` | `0.6` | Random-action probability (0–1) |
| `[renderer]` | `mode` | `web` | `web` (default) / `ansi` / `tk` / `auto` |
| | `ansi_width` | `48` | Terminal pet width (characters) |
| | `bg_color` | empty | Background behind transparent pixels, e.g. `1e1e2e`; empty = terminal default |
| | `tk_scale` | `3` | Tk window pixel scale factor |
| | `web_port` | `8765` | Web-mode port |
| | `open_browser` | `true` | Auto-open the browser in web mode |
| `[interaction]` | `feed_key` | `f` | Feed key |
| | `pet_key` | `p` | Pet key |
| | `sleep_key` | `s` | Sleep/wake key |
| | `quit_key` | `q` | Quit key |
| `[dsh]` | `status_source` | `mock` | `mock` / `file` / `none` |
| | `status_file` | `.dsh_pet_status.json` | Status JSON file path |
| | `status_poll_interval` | `1.0` | Status poll interval (seconds) |
| | `bubble_width` | `40` | Max bubble width (characters) |

Command-line arguments always override the config file.

## Keyboard / mouse interactions

| Key | Web mode | Terminal mode | Tk window |
| --- | --- | --- | --- |
| `f` | Feed | Feed | Feed |
| `p` | Pet | Pet | Pet |
| `s` | Sleep/wake | Sleep/wake | Sleep/wake |
| `h` | Hide/summon | — | — |
| `q` / `Ctrl+C` | Close the page | Quit and restore terminal | Close the window |
| Mouse | Click to pet, drag to move | — | Click for a random reaction |

All keys can be remapped in the `[interaction]` section.

## Tests

```sh
python -m unittest discover -s tests -v     # all unit tests (incl. web API tests)
node plugins/test.js                         # cordis plugin tests
python scripts/render_preview.py            # generate docs/preview.gif
python -m dsh_pet --renderer ansi --no-hint # try terminal mode manually
python -m dsh_pet --no-browser              # try web mode manually
```

## Project structure

```plain
dsh_pet/
├── __init__.py            # package declaration
├── main.py                # entry: arg parsing, mode selection, input (POSIX/Windows)
├── pet_core.py            # state machine + animation engine + event queue
├── renderer.py            # AnsiRenderer (terminal half-block) / TkRenderer (window)
├── web_renderer.py        # WebRenderer (default): HTTP server + browser pet page
├── sprite.py              # asset loading: pet.json + spritesheet.webp → frames
├── config.py              # .dsh_pet_config loading
├── dsh_integration.py     # MockStatusSource / FileStatusSource + bubble formatting
├── assets/                # artwork & licenses (see SOURCES.md)
│   ├── lulu/              # czy666chen/lulu (MIT)
│   ├── capybara/          # HatchPet-CapybaraLulu (Apache-2.0)
│   └── SOURCES.md
├── bin/dsh-pet            # wrapper scripts (POSIX sh + Windows .cmd)
├── plugins/               # cordis plugin (JS): registers the dsh pet subcommand (default web)
├── tests/                 # unittest: animation, state machine, keys, config, renderers, web
├── scripts/               # preview / demo scripts
├── .dsh_pet_config.example
├── README.md / README.en.md
└── pyproject.toml
```

## Assets & licenses

* `lulu`: czy666chen/lulu, **MIT License**
  (`dsh_pet/assets/lulu/licenses/LICENSE.lulu`).
* `capybara`: srwang0506/HatchPet-CapybaraLulu, **Apache-2.0**
  (`dsh_pet/assets/capybara/licenses/LICENSE` + `NOTICE`).
* Full details, the row layout and download instructions are in
  [`dsh_pet/assets/SOURCES.md`](dsh_pet/assets/SOURCES.md).
* This project's own code is MIT-licensed (see the root `LICENSE`).

## FAQ / troubleshooting

* **The pet is not on the page?** Press F5 to refresh first; if you hid it,
  a "Summon" button appears bottom-right — click it.
* **Port already in use?** Pick another one: `python -m dsh_pet --port 9000`.
* **No Pillow?** Run `pip install -e ".[sprites]"`; the terminal pet falls
  back to ASCII art, web mode reports an error and asks for Pillow.
* **`dsh pet` complains about a missing `--profile`?** The launcher only
  hardcodes `web`; use `dsh --profile pet pet` or add a shell alias (above).
* **The pet is asleep and won't move?** Press `s` to wake it.
* **Want to reset the web pet position?** Clear the `dsh-pet-lulu-pos` key
  in the browser's localStorage.

## Acceptance checklist

- [x] `python -m dsh_pet` (default web) opens the pet page with a stable idle animation
- [x] `--renderer ansi` terminal mode kept; `f` / `p` / `s` trigger reactions
- [x] Runs without crashes; CPU <5% of a single core (frame-loop throttling)
- [x] dsh integration: plugin spawns the pet + status file carries mock progress
- [x] Web mode: click/feed/sleep/hide/summon/drag + status bubble endpoints all work
- [x] Clear code with comments; complete bilingual README
