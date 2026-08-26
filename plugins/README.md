# dsh pet plugin (`@dsh-pet/plugin`)

A small Cordis plugin for DeepSeek Harness (dsh) that registers the `pet`
subcommand.  It spawns the Python pet (`dsh-pet-lulu`, see the repository
root) as a **subprocess with inherited stdio**, so the pet takes over the
terminal while the dsh main process keeps running — the pet never blocks it.

## What it does

* Registers `pet` as a commander subcommand inside any dsh profile that
  mounts this plugin (via `cmdlineArgs` / `appExit`).
* Ships the `dsh.bundle` manifest (`cordis.patch.yml`) so the package is
  installable as a proper dsh bundle layer via `dsh plugin add`.
* Spawns `python -m dsh_pet` with the same options the Python CLI accepts
  (`--mode`, `--pet-type`, `--renderer`, `--gui`, `--fps`, `--width`,
  `--bg-color`, `--port`, `--no-browser`, `--status-source`,
  `--status-file`, `--config`, `--no-hint`).
* **Mode selection** — `--mode web | terminal | tk`, default **web**
  (browser pet page). `terminal` runs the ANSI TUI, `tk` the Tk window.
* Streams task status to the pet through a JSON file when the pet runs with
  `--status-source file`: the plugin writes the file and the Python side
  polls it, so "dsh task progress" really comes from dsh.
* Provides a `petStatus` service (`update({task_name, phase, progress,
  gpu_temp, message})`) that other dsh plugins can use to push real task
  status into the status file.

## Install

The dsh launcher only knows `web` as a bare alias, so the pet lives on its
own profile:

```sh
# 1. create the profile and install this plugin package into it
dsh plugin --profile pet add <path-to-dsh-pet-lulu/plugins>

# 2. mount the plugin: put the row from pet.profile.yml into
#    $DSH_HOME/profiles/pet/cordis.yml (create it if missing)

# 3. point the plugin at the Python checkout if it is not pip-installed
setx DSH_PET_HOME "D:\path\to\dsh-pet-lulu"      # Windows
export DSH_PET_HOME=/path/to/dsh-pet-lulu         # Linux / macOS
```

If `dsh_pet` is installed with pip, nothing else is needed.

## Run

```sh
dsh --profile pet pet                              # default: web pet (opens the browser page)
dsh --profile pet pet --mode terminal              # ANSI terminal mode
dsh --profile pet pet --mode tk                    # Tk window mode
dsh --profile pet pet --pet-type capybara \
    --status-source file --status-file .dsh_pet_status.json   # status streamed by the plugin
dsh --profile pet pet --help
```

For the literal `dsh pet` form the launcher must learn the alias first
(the shipped launcher only hardcodes `web`):

```sh
# PowerShell
function dsh { & dsh.cmd @args }        # ensure dsh is callable in functions
Set-Alias -Name pet -Value "dsh --profile pet pet" -Option AllScope  # not recommended
# simplest: a small wrapper script
@'
@echo off
dsh --profile pet pet %*
'@ | Set-Content "$env:USERPROFILE\bin\dsh-pet.cmd"
```

```sh
# bash / zsh
alias dsh-pet='dsh --profile pet pet'
# or a wrapper script on PATH
```

## Configuration

The row config keys: `pythonBin` (default `python`), `packageDir`
(default `$DSH_PET_HOME`), `statusFile` (used by `petStatus.update`).
