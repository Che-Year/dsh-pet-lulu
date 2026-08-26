"""Renderers for dsh-pet.

Two renderers implement the same small interface:

* :class:`AnsiRenderer` - draws the pet with truecolor half-block glyphs
  (``▀`` / ``▄``) directly in the terminal using the alternate screen
  buffer.  Works on Linux/macOS terminals and on Windows terminals with VT
  mode enabled (Windows 10+ and Windows Terminal do this automatically).
* :class:`TkRenderer` - a small Tkinter window with mouse interaction
  (``--gui`` / ``renderer.mode = tk``).

Both run their own animation loop and pull frames from a
:class:`dsh_pet.pet_core.PetCore`.
"""

from __future__ import annotations

import os
import sys
import time
from typing import List, Optional, Tuple

from . import sprite as sprite_mod
from .pet_core import PetCore, EVENT_FEED, EVENT_PET, EVENT_SLEEP, EVENT_QUIT

# --------------------------------------------------------------------------- #
# ANSI helpers
# --------------------------------------------------------------------------- #

_RESET = "\x1b[0m"
_ALT_SCREEN_ON = "\x1b[?1049h"
_ALT_SCREEN_OFF = "\x1b[?1049l"
_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"
_HOME = "\x1b[H"


def _fg(rgb: Tuple[int, int, int]) -> str:
    return f"\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


def _bg(rgb: Tuple[int, int, int]) -> str:
    return f"\x1b[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


def _cell_escape(block, default_bg: bool) -> str:
    """Escape sequence for one half-block cell.

    ``block`` is ``((top_rgb, top_alpha), (bottom_rgb, bottom_alpha))``.
    Transparent halves fall back to the terminal's default colours when
    ``default_bg`` is true, otherwise to black.
    """
    (top, ta), (bot, ba) = block
    top_opaque = ta >= 8
    bot_opaque = ba >= 8
    fallback = "\x1b[49m" if default_bg else "\x1b[40m"
    if top_opaque and bot_opaque:
        return _fg(top) + _bg(bot) + "▀"
    if top_opaque:
        return _fg(top) + fallback + "▀"
    if bot_opaque:
        return _fg(bot) + fallback + "▄"
    return fallback + " "


# --------------------------------------------------------------------------- #
# bubble rendering
# --------------------------------------------------------------------------- #

def _draw_bubble(lines: List[str], width: int) -> List[str]:
    """Render bubble lines with a rounded box around them."""
    if not lines:
        return []
    inner = max(1, min(width - 2, max(len(line) for line in lines)))
    top = "╭" + "─" * inner + "╮"
    bottom = "╰" + "─" * inner + "╯"
    body = []
    for line in lines:
        padded = line[:inner].ljust(inner)
        body.append("│" + padded + "│")
    return [top] + body + [bottom]


class AnsiRenderer:
    """Truecolor half-block renderer for the terminal."""

    def __init__(self, core: PetCore, width: int = 48,
                 bg_color: Optional[str] = None,
                 out=None, hint: bool = True, keys: Optional[dict] = None) -> None:
        self.core = core
        self.width = width
        self.bg = sprite_mod.parse_color(bg_color)
        self.out = out or sys.stdout
        self.hint = hint
        self.keys = keys or {"feed": "f", "pet": "p", "sleep": "s", "quit": "q"}
        self._last_width = 0
        self._last_height = 0
        self._block_cache: dict = {}

    # ------------------------------------------------------------------ #

    def _blocks(self, frame, width: int):
        key = (id(frame), width)
        if key not in self._block_cache:
            self._block_cache[key] = sprite_mod.frame_blocks(self.core.pack, frame, width, self.bg)
        return self._block_cache[key]

    def _terminal_size(self) -> Tuple[int, int]:
        try:
            import shutil

            size = shutil.get_terminal_size((80, 24))
            return (size.columns, size.lines)
        except Exception:  # noqa: BLE001
            return (80, 24)

    def run(self) -> None:
        """Run the animation loop until the pet quits."""
        try:
            self._write(_ALT_SCREEN_ON + _HIDE_CURSOR + _HOME)
            self._flush()
            while not self.core.quit:
                started = time.monotonic()
                self.core.tick(self.core.period)
                self._draw()
                elapsed = time.monotonic() - started
                delay = self.core.period - elapsed
                if delay > 0:
                    time.sleep(delay)
        finally:
            self._write(_SHOW_CURSOR + _ALT_SCREEN_OFF + _RESET)
            self._flush()

    def _draw(self) -> None:
        cols, rows = self._terminal_size()
        width = min(self.width, max(8, cols - 2))
        lines = self.core.bubble_lines()
        bubble = _draw_bubble(lines, min(self.core.bubble_width, width))
        hint = self.hint
        frame = self._current_image()
        if frame is None:
            return
        # Shrink the pet until it (plus bubble and hint) fits the terminal
        # height; a smaller pet is preferable to a clipped bubble.
        while width >= 8:
            blocks = self._blocks(frame, width)
            total = len(bubble) + len(blocks) + (2 if hint else 1)
            if not rows or total <= rows:
                break
            if hint:
                hint = False  # drop the key hint first
            else:
                width -= 4
        if width < 8:
            width = 8
            blocks = self._blocks(frame, width)
        # last resort: trim bubble lines from the top, keep the pet visible
        total = len(bubble) + len(blocks) + (1 if hint else 0)
        overflow = total - rows if rows else 0
        if overflow > 0:
            bubble = bubble[overflow:]
        parts = [_HOME]
        for line in bubble:
            parts.append(_fg((210, 210, 210)) + line + _RESET + "\n")
        for row_blocks in blocks:
            parts.append("".join(_cell_escape(b, self.bg is None) for b in row_blocks) + _RESET + "\n")
        if hint:
            parts.append(_fg((120, 120, 130)) + self._hint_text() + _RESET)
        self._write("".join(parts))
        self._flush()
        self._last_width, self._last_height = cols, rows

    def _current_image(self):
        behaviour, index = self.core.current_frame()
        clip = self.core.pack.clip_for(behaviour)
        if clip and index < len(clip.frames):
            return clip.frames[index]
        return None

    def _hint_text(self) -> str:
        feed = self.keys.get("feed", "f")
        pet = self.keys.get("pet", "p")
        sleep = self.keys.get("sleep", "s")
        quit_ = self.keys.get("quit", "q")
        return (f"  {feed} 喂食 · {pet} 抚摸 · {sleep} 睡觉/唤醒 · {quit_} 退出"
                f"   · 状态: {self.core.status_source.name}")

    def _write(self, text: str) -> None:
        try:
            self.out.write(text)
        except (BrokenPipeError, OSError, UnicodeError):
            self.core.quit = True

    def _flush(self) -> None:
        try:
            self.out.flush()
        except (BrokenPipeError, OSError):
            self.core.quit = True


# --------------------------------------------------------------------------- #
# Tk renderer
# --------------------------------------------------------------------------- #

class TkRenderer:
    """Tkinter window renderer with mouse interaction."""

    def __init__(self, core: PetCore, scale: int = 3,
                 bg_color: Optional[str] = None) -> None:
        self.core = core
        self.scale = max(1, scale)
        self.bg = sprite_mod.parse_color(bg_color) or (30, 30, 46)
        self._root = None
        self._canvas = None
        self._photo = None
        self._frame_cache: dict = {}
        self._tk_bg = "#%02x%02x%02x" % self.bg

    def _ensure_tk(self):
        import tkinter as tk

        self._root = tk.Tk()
        self._root.title("dsh-pet · " + self.core.pack.display_name)
        self._root.resizable(False, False)
        self._canvas = tk.Canvas(self._root, bg=self._tk_bg, highlightthickness=0)
        self._canvas.pack()
        self._bind_input()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _bind_input(self) -> None:
        import tkinter as tk

        root = self._root
        canvas = self._canvas
        keys = {"f": EVENT_FEED, "p": EVENT_PET, "s": EVENT_SLEEP}
        for char, event in keys.items():
            root.bind(f"<Key-{char}>", lambda _e, ev=event: self.core.post_event(ev))
        root.bind("<Key-q>", lambda _e: self.core.post_event(EVENT_QUIT))
        root.bind("<Escape>", lambda _e: self.core.post_event(EVENT_QUIT))
        # clicking the pet area triggers a random reaction
        canvas.bind("<Button-1>", self._on_click)

    def _on_click(self, _event) -> None:
        self.core.post_event("random")

    def _on_close(self) -> None:
        self.core.post_event(EVENT_QUIT)

    # ------------------------------------------------------------------ #

    def _photo_for(self, frame):
        from PIL import ImageTk

        key = id(frame)
        if key not in self._frame_cache:
            img = frame.convert("RGBA").resize(
                (frame.width * self.scale, frame.height * self.scale))
            self._frame_cache[key] = ImageTk.PhotoImage(img)
        return self._frame_cache[key]

    def run(self) -> None:
        """Run the Tk mainloop; the animation loop is driven by ``after``."""
        self._ensure_tk()
        self._loop()
        self._root.mainloop()

    def _loop(self) -> None:
        if self.core.quit:
            return
        started = time.monotonic()
        self.core.tick(self.core.period)
        self._draw()
        elapsed = time.monotonic() - started
        delay_ms = max(5, int((self.core.period - elapsed) * 1000))
        self._root.after(delay_ms, self._loop)

    def _draw(self) -> None:
        behaviour, index = self.core.current_frame()
        clip = self.core.pack.clip_for(behaviour)
        if not clip or index >= len(clip.frames):
            return
        self._photo = self._photo_for(clip.frames[index])
        canvas = self._canvas
        canvas.delete("all")
        lines = self.core.bubble_lines()
        bubble_lines = _draw_bubble(lines, self.core.bubble_width)
        w = self._photo.width()
        h = self._photo.height()
        text_h = len(bubble_lines) * 18 + 10
        canvas.config(width=w + 20, height=h + text_h)
        canvas.create_text(w // 2 + 10, 6, anchor="n", fill="#d0d0d0",
                           font=("TkDefaultFont", 11),
                           text="\n".join(bubble_lines) if bubble_lines else "")
        canvas.create_image(w // 2 + 10, text_h + h // 2, image=self._photo)


def make_renderer(kind: str, core: PetCore, config) -> object:
    """Instantiate the renderer selected by ``kind`` (auto|ansi|tk)."""
    kind = (kind or "auto").strip().lower()
    if kind == "tk":
        return TkRenderer(core, scale=config.tk_scale, bg_color=config.bg_color)
    return AnsiRenderer(core, width=config.ansi_width, bg_color=config.bg_color)
