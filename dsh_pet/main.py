"""dsh-pet entry point.

Run the pet standalone with ``python -m dsh_pet`` (or the ``dsh-pet``
console script).  The dsh integration spawns this module as a subprocess,
passing ``--status-source file --status-file <path>`` so the pet shows real
dsh task status.

Exit codes: 0 on a clean quit, 1 on startup failure.
"""

from __future__ import annotations

import argparse
import sys
import threading
from typing import Dict, List, Optional

from . import __version__
from .config import Config, load_config
from .dsh_integration import make_status_source
from .pet_core import (EVENT_FEED, EVENT_PET, EVENT_QUIT, EVENT_SLEEP, PetCore)
from .renderer import AnsiRenderer, TkRenderer, make_renderer
from .sprite import load_pack

KEY_EVENTS = {
    "feed": EVENT_FEED,
    "pet": EVENT_PET,
    "sleep": EVENT_SLEEP,
    "quit": EVENT_QUIT,
}


def map_key(ch: str, keys: Dict[str, str]) -> Optional[str]:
    """Map one input character to a behaviour event (or None).

    ``keys`` is ``{"feed": "f", "pet": "p", "sleep": "s", "quit": "q"}``.
    This is a pure function so tests can exercise it with simulated input.
    """
    ch = ch.lower()
    if ch == "\x03":  # Ctrl+C
        return EVENT_QUIT
    for name, key in keys.items():
        if key and ch == key.lower():
            return KEY_EVENTS.get(name)
    return None


# --------------------------------------------------------------------------- #
# terminal input readers
# --------------------------------------------------------------------------- #

class _InputReader(threading.Thread):
    """Reads single keys from the terminal and posts behaviour events."""

    def __init__(self, core: PetCore, keys: Dict[str, str]) -> None:
        super().__init__(name="dsh-pet-input", daemon=True)
        self.core = core
        self.keys = keys
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def _handle(self, ch: str) -> None:
        event = map_key(ch, self.keys)
        if event:
            self.core.post_event(event)

    def run(self) -> None:  # pragma: no cover - platform specific
        raise NotImplementedError


class PosixInputReader(_InputReader):
    """termios raw-mode reader for Linux/macOS."""

    def run(self) -> None:  # pragma: no cover - exercised interactively
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while not self._stop_event.is_set():
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if not ready:
                    continue
                data = os_read(fd, 16)
                for ch in data:
                    self._handle(ch.decode("utf-8", "replace"))
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def os_read(fd: int, size: int) -> bytes:  # pragma: no cover - thin wrapper
    import os

    return os.read(fd, size)


class WindowsInputReader(_InputReader):
    """msvcrt reader for Windows consoles."""

    def run(self) -> None:  # pragma: no cover - exercised interactively
        import msvcrt
        import time

        while not self._stop_event.is_set():
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                self._handle(ch)
            time.sleep(0.03)


def start_input_reader(core: PetCore, keys: Dict[str, str]) -> _InputReader:
    if sys.platform.startswith("win"):
        reader = WindowsInputReader(core, keys)
    else:
        reader = PosixInputReader(core, keys)
    reader.start()
    return reader


# --------------------------------------------------------------------------- #
# windows VT mode
# --------------------------------------------------------------------------- #

def _force_utf8_stdio() -> None:
    """Force UTF-8 on stdout/stderr so ANSI half-block glyphs never trip the
    locale codepage (e.g. GBK on Windows consoles)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - best effort
            pass


def enable_windows_vt() -> None:  # pragma: no cover - Windows only
    """Best-effort enable of VT escape processing on Windows consoles."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:  # noqa: BLE001 - fall back to plain output
        pass


# --------------------------------------------------------------------------- #
# argument parsing
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dsh-pet",
        description="dsh-pet — a cute capybara desktop pet for DeepSeek Harness",
        epilog="keys: f feed · p pet · s sleep/wake · q quit  (see --help and README)",
    )
    parser.add_argument("-c", "--config", metavar="PATH", help="path to a .dsh_pet_config file")
    parser.add_argument("--pet-type", choices=("lulu", "capybara"), help="sprite pack to use")
    parser.add_argument("--renderer", choices=("auto", "ansi", "tk", "web"),
                        help="renderer backend (default: web)")
    parser.add_argument("--gui", action="store_true", help="use the Tkinter window mode")
    parser.add_argument("--fps", type=int, metavar="N", help="animation frames per second")
    parser.add_argument("--width", type=int, metavar="N", help="pet width in terminal characters")
    parser.add_argument("--scale", type=int, metavar="N", help="Tk window pixel scale")
    parser.add_argument("--bg-color", metavar="RRGGBB", help="background colour behind the pet")
    parser.add_argument("--port", type=int, metavar="N", help="local port for the web pet page")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open the browser in web mode (just serve)")
    parser.add_argument("--status-source", choices=("mock", "file", "none"),
                        help="where task status comes from")
    parser.add_argument("--status-file", metavar="PATH", help="JSON status file for --status-source file")
    parser.add_argument("--no-hint", action="store_true", help="hide the key hint line")
    parser.add_argument("--version", action="version", version=f"dsh-pet {__version__}")
    return parser


def apply_args(cfg: Config, args: argparse.Namespace) -> None:
    if args.pet_type:
        cfg.pet_type = args.pet_type
    if args.renderer:
        cfg.renderer_mode = args.renderer
    if args.gui:
        cfg.renderer_mode = "tk"
    if args.fps is not None:
        cfg.fps = args.fps
    if args.width is not None:
        cfg.ansi_width = args.width
    if args.scale is not None:
        cfg.tk_scale = args.scale
    if args.bg_color:
        cfg.bg_color = args.bg_color
    if args.port is not None:
        cfg.web_port = args.port
    if args.no_browser:
        cfg.open_browser = False
    if args.status_source:
        cfg.status_source = args.status_source
    if args.status_file:
        cfg.status_file = args.status_file
    if args.no_hint:
        cfg.no_hint = True
    cfg.__post_init__()


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main(argv: Optional[List[str]] = None) -> int:
    _force_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    apply_args(cfg, args)

    try:
        pack = load_pack(cfg.pet_type)
    except Exception as exc:  # noqa: BLE001 - report and exit
        print(f"dsh-pet: could not load sprite pack: {exc}", file=sys.stderr)
        return 1

    status_source = make_status_source(cfg.status_source, cfg.status_file)
    core = PetCore(
        pack,
        fps=cfg.fps,
        random_action_interval=cfg.random_action_interval,
        random_action_chance=cfg.random_action_chance,
        status_source=status_source,
        status_poll_interval=cfg.status_poll_interval,
        bubble_width=cfg.bubble_width,
    )
    keys = {"feed": cfg.feed_key, "pet": cfg.pet_key,
            "sleep": cfg.sleep_key, "quit": cfg.quit_key}

    mode = cfg.renderer_mode
    if mode == "auto":
        mode = "web"  # the default mode is the web pet; --renderer ansi opts into the terminal
    if mode == "web":
        return _run_web(core, cfg)
    if mode == "tk":
        renderer = TkRenderer(core, scale=cfg.tk_scale, bg_color=cfg.bg_color)
        try:
            renderer.run()
        except Exception as exc:  # noqa: BLE001 - no display server etc.
            print(f"dsh-pet: Tk mode unavailable: {exc}", file=sys.stderr)
            print("dsh-pet: falling back to ANSI terminal mode", file=sys.stderr)
            return _run_ansi(core, cfg, keys)
        finally:
            core.close()
        return 0

    return _run_ansi(core, cfg, keys)


def _run_web(core: PetCore, cfg: Config) -> int:
    from .web_renderer import WebRenderer

    renderer = WebRenderer(core, port=cfg.web_port, open_browser=cfg.open_browser)
    try:
        renderer.run()
    except KeyboardInterrupt:
        pass
    finally:
        renderer.stop()
        core.close()
    return 0


def _run_ansi(core: PetCore, cfg: Config, keys: Dict[str, str]) -> int:
    enable_windows_vt()
    reader: Optional[_InputReader] = None
    try:
        reader = start_input_reader(core, keys)
    except Exception:  # noqa: BLE001 - input is optional; pet still renders
        reader = None
    renderer = AnsiRenderer(core, width=cfg.ansi_width, bg_color=cfg.bg_color,
                            hint=not cfg.no_hint, keys=keys)
    try:
        renderer.run()
    except KeyboardInterrupt:
        core.quit = True
    finally:
        if reader is not None:
            reader.stop()
            reader.join(timeout=0.5)
        core.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
