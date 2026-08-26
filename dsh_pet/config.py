"""Configuration loading for dsh-pet.

The configuration file is a small INI-style dotfile (``.dsh_pet_config``)
looked up in this order:

1. an explicit path passed with ``--config`` / ``-c``;
2. ``./.dsh_pet_config`` in the current working directory;
3. ``~/.dsh_pet_config`` in the user home directory.

Command-line flags always override file values.  Everything has a sane
default, so the pet runs with no configuration at all.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

CONFIG_NAMES = (".dsh_pet_config", "dsh_pet_config.ini")

# Keys that may appear more than once in an INI file (comma separated list).
_LIST_KEYS = ("default_look_directions",)

DEFAULTS: Dict[str, Dict[str, str]] = {
    "general": {
        "pet_type": "lulu",  # lulu | capybara
        "log_level": "info",  # debug | info | warning | error
    },
    "animation": {
        "fps": "10",  # animation frames per second (default 10 FPS)
        "random_action_interval": "12.0",  # seconds between random actions
        "random_action_chance": "0.6",  # probability of a random action at each tick
    },
    "renderer": {
        "mode": "web",  # web | ansi | tk | auto (auto resolves to web)
        "ansi_width": "48",  # pet width in terminal characters
        "bg_color": "",  # background behind transparent pixels, e.g. 1e1e2e (empty = terminal default)
        "tk_scale": "3",  # Tk window pixel scale factor
        "web_port": "8765",  # local port for the web pet page
        "open_browser": "true",  # open the browser automatically in web mode
    },
    "interaction": {
        "feed_key": "f",
        "pet_key": "p",
        "sleep_key": "s",
        "quit_key": "q",
    },
    "dsh": {
        "status_source": "mock",  # mock | file | none
        "status_file": ".dsh_pet_status.json",
        "status_poll_interval": "1.0",
        "bubble_width": "40",
    },
}


def _as_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def _as_int(value: str, default: int) -> int:
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def _as_float(value: str, default: float) -> float:
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return default


@dataclass
class Config:
    """Resolved pet configuration."""

    # general
    pet_type: str = "lulu"
    log_level: str = "info"

    # animation
    fps: int = 10
    random_action_interval: float = 12.0
    random_action_chance: float = 0.6

    # renderer
    renderer_mode: str = "web"  # web | ansi | tk | auto
    ansi_width: int = 48
    bg_color: Optional[str] = None  # hex string without '#', or None
    tk_scale: int = 3
    web_port: int = 8765
    open_browser: bool = True

    # interaction keys
    feed_key: str = "f"
    pet_key: str = "p"
    sleep_key: str = "s"
    quit_key: str = "q"

    # dsh integration
    status_source: str = "mock"  # mock | file | none
    status_file: str = ".dsh_pet_status.json"
    status_poll_interval: float = 1.0
    bubble_width: int = 40

    # CLI-only flags
    no_hint: bool = False  # hide the key hint line (CLI --no-hint)

    # not from file: CLI overrides only
    cli_overrides: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.fps = max(1, self.fps)
        self.ansi_width = max(8, min(self.ansi_width, 200))
        self.bubble_width = max(10, min(self.bubble_width, 80))
        self.web_port = max(0, min(self.web_port, 65535))

    # ------------------------------------------------------------------ #

    def frame_period(self) -> float:
        """Seconds per animation frame."""
        return 1.0 / self.fps

    def bubble_lines(self, width: int) -> int:  # pragma: no cover - helper
        return self.bubble_width


def find_config_file(explicit: Optional[str] = None) -> Optional[str]:
    """Locate a configuration file, or return None when none exists."""
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    for name in CONFIG_NAMES:
        local = os.path.join(os.getcwd(), name)
        if os.path.isfile(local):
            return local
    home = os.path.expanduser("~")
    for name in CONFIG_NAMES:
        user = os.path.join(home, name)
        if os.path.isfile(user):
            return user
    return None


def _read_ini(path: str) -> Dict[str, Dict[str, str]]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # keep key case
    # tolerate missing section headers by placing orphan options into [general]
    parser.read(path, encoding="utf-8")
    data: Dict[str, Dict[str, str]] = {}
    for section in parser.sections():
        data[section] = {k: v for k, v in parser.items(section)}
    return data


def load_config(explicit: Optional[str] = None) -> Config:
    """Load the configuration from disk merged over the defaults."""
    cfg = Config()
    path = find_config_file(explicit)
    raw: Dict[str, Dict[str, str]] = {}
    if path is not None:
        try:
            raw = _read_ini(path)
        except Exception as exc:  # noqa: BLE001 - bad config must not kill the pet
            import warnings

            warnings.warn(f"could not parse config {path!r}: {exc}")
    _apply_raw(cfg, raw)
    _apply_cli(cfg, cfg.cli_overrides)
    return cfg


def _apply_raw(cfg: Config, raw: Dict[str, Dict[str, str]]) -> None:
    g = raw.get("general", {})
    a = raw.get("animation", {})
    r = raw.get("renderer", {})
    i = raw.get("interaction", {})
    d = raw.get("dsh", {})

    if "pet_type" in g:
        cfg.pet_type = g["pet_type"].strip().lower()
    if "log_level" in g:
        cfg.log_level = g["log_level"].strip().lower()
    if "fps" in a:
        cfg.fps = _as_int(a["fps"], cfg.fps)
    if "random_action_interval" in a:
        cfg.random_action_interval = _as_float(a["random_action_interval"], cfg.random_action_interval)
    if "random_action_chance" in a:
        cfg.random_action_chance = max(0.0, min(1.0, _as_float(a["random_action_chance"], cfg.random_action_chance)))
    if "mode" in r:
        cfg.renderer_mode = r["mode"].strip().lower()
    if "ansi_width" in r:
        cfg.ansi_width = _as_int(r["ansi_width"], cfg.ansi_width)
    if "bg_color" in r and r["bg_color"].strip():
        cfg.bg_color = r["bg_color"].strip().lstrip("#")
    if "tk_scale" in r:
        cfg.tk_scale = max(1, _as_int(r["tk_scale"], cfg.tk_scale))
    if "web_port" in r:
        cfg.web_port = _as_int(r["web_port"], cfg.web_port)
    if "open_browser" in r:
        cfg.open_browser = _as_bool(r["open_browser"])
    if "feed_key" in i:
        cfg.feed_key = i["feed_key"].strip()
    if "pet_key" in i:
        cfg.pet_key = i["pet_key"].strip()
    if "sleep_key" in i:
        cfg.sleep_key = i["sleep_key"].strip()
    if "quit_key" in i:
        cfg.quit_key = i["quit_key"].strip()
    if "status_source" in d:
        cfg.status_source = d["status_source"].strip().lower()
    if "status_file" in d:
        cfg.status_file = d["status_file"].strip()
    if "status_poll_interval" in d:
        cfg.status_poll_interval = max(0.1, _as_float(d["status_poll_interval"], cfg.status_poll_interval))
    if "bubble_width" in d:
        cfg.bubble_width = _as_int(d["bubble_width"], cfg.bubble_width)
    cfg.__post_init__()


def _apply_cli(cfg: Config, overrides: Dict[str, str]) -> None:
    """Apply validated CLI overrides (key -> string value).

    Int/float/bool fields are coerced; unknown keys are ignored.
    """
    def get_int(key: str, default: int) -> int:
        value = overrides.get(key)
        return _as_int(value, default) if value is not None else default

    def get_float(key: str, default: float) -> float:
        value = overrides.get(key)
        return _as_float(value, default) if value is not None else default

    def get_str(key: str, default: str) -> str:
        value = overrides.get(key)
        return str(value).strip() if value is not None else default

    if "pet_type" in overrides:
        cfg.pet_type = get_str("pet_type", cfg.pet_type).lower()
    if "log_level" in overrides:
        cfg.log_level = get_str("log_level", cfg.log_level).lower()
    if "fps" in overrides:
        cfg.fps = get_int("fps", cfg.fps)
    if "random_action_interval" in overrides:
        cfg.random_action_interval = get_float("random_action_interval", cfg.random_action_interval)
    if "random_action_chance" in overrides:
        cfg.random_action_chance = max(0.0, min(1.0, get_float("random_action_chance", cfg.random_action_chance)))
    if "renderer_mode" in overrides:
        cfg.renderer_mode = get_str("renderer_mode", cfg.renderer_mode).lower()
    if "ansi_width" in overrides:
        cfg.ansi_width = get_int("ansi_width", cfg.ansi_width)
    if "bg_color" in overrides and overrides.get("bg_color"):
        cfg.bg_color = overrides["bg_color"].strip().lstrip("#")
    if "tk_scale" in overrides:
        cfg.tk_scale = get_int("tk_scale", cfg.tk_scale)
    if "feed_key" in overrides:
        cfg.feed_key = get_str("feed_key", cfg.feed_key)
    if "pet_key" in overrides:
        cfg.pet_key = get_str("pet_key", cfg.pet_key)
    if "sleep_key" in overrides:
        cfg.sleep_key = get_str("sleep_key", cfg.sleep_key)
    if "quit_key" in overrides:
        cfg.quit_key = get_str("quit_key", cfg.quit_key)
    if "status_source" in overrides:
        cfg.status_source = get_str("status_source", cfg.status_source).lower()
    if "status_file" in overrides:
        cfg.status_file = get_str("status_file", cfg.status_file)
    if "status_poll_interval" in overrides:
        cfg.status_poll_interval = max(0.1, get_float("status_poll_interval", cfg.status_poll_interval))
    if "bubble_width" in overrides:
        cfg.bubble_width = get_int("bubble_width", cfg.bubble_width)
    if "no_hint" in overrides:
        cfg.no_hint = _as_bool(overrides["no_hint"])
    cfg.__post_init__()
