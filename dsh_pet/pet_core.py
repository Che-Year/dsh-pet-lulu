"""Pet core: the behaviour state machine and animation engine.

The core owns *what* the pet is doing and *which frame* of *which clip* is
current.  It is deliberately renderer-agnostic: a renderer asks
:meth:`PetCore.current_frame` for ``(behaviour, frame_index)`` and pulls the
pixel data from the sprite pack itself.

Events are posted from an input thread (or tests) and consumed on the
animation thread, so key presses never block rendering.

Behaviours:

* ``idle``        - looping idle animation (breathing / blinking)
* ``blink``       - one-shot blink then back to idle
* ``eat``         - one-shot "eating" reaction (key ``f``)
* ``pet``         - one-shot "happy wave" reaction (key ``p``)
* ``jump``        - one-shot jump (random)
* ``walk``        - one-shot walk right (random)
* ``walk-left``   - one-shot walk left (random)
* ``yawn``        - one-shot yawn (random)
* ``look``        - one-shot glance in a random direction (random)
* ``sleep``       - hold the sleeping pose until toggled awake (key ``s``)
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .dsh_integration import StatusInfo, StatusSource, format_status, make_status_source

# Behaviour events posted by input handlers.
EVENT_FEED = "feed"
EVENT_PET = "pet"
EVENT_SLEEP = "sleep"
EVENT_QUIT = "quit"
EVENT_RANDOM = "random"

# One-shot reaction texts shown in the bubble while playing.
REACTION_TEXT: Dict[str, str] = {
    "eat": "🍉 好吃！",
    "pet": "嘿嘿～",
    "jump": "跳！",
    "walk": "遛弯去咯～",
    "walk-left": "遛弯去咯～",
    "yawn": "哈欠～",
    "look": "看看…",
    "blink": "",
    "sleep": "Zzz…",
}

# Random actions and their relative weights while idling.
RANDOM_ACTIONS: List[tuple] = [
    ("walk", 3),
    ("walk-left", 3),
    ("jump", 2),
    ("yawn", 2),
    ("look", 2),
    ("blink", 1),
]


@dataclass
class _State:
    behaviour: str = "idle"
    frame: int = 0
    loops: int = 0
    # one-shot behaviours end after max_loops (>=1); looping ones go forever
    max_loops: int = 0
    hold: bool = False
    hold_frame: int = 0
    text: str = ""


class PetCore:
    """State machine + frame pacing for one pet."""

    def __init__(self, pack, fps: int = 10,
                 random_action_interval: float = 12.0,
                 random_action_chance: float = 0.6,
                 status_source: StatusSource = None,
                 status_poll_interval: float = 1.0,
                 bubble_width: int = 40,
                 rng: Optional[random.Random] = None) -> None:
        self.pack = pack
        self.fps = max(1, int(fps))
        self.period = 1.0 / self.fps
        self.random_action_interval = max(0.5, random_action_interval)
        self.random_action_chance = max(0.0, min(1.0, random_action_chance))
        self.bubble_width = max(10, bubble_width)
        self.rng = rng or random.Random()
        self.status_source = status_source or make_status_source("mock")
        self.status_poll_interval = max(0.1, status_poll_interval)
        self._events: List[str] = []
        self._state = _State()
        self._sleeping = False
        self.quit = False
        self._frame_accum = 0.0
        self._last_status_poll = 0.0
        self._last_random_time = time.monotonic()
        self._status: Optional[StatusInfo] = None
        # behaviour bubble text is kept for the duration of a one-shot
        self._reaction_text = ""

    # ------------------------------------------------------------------ #
    # events
    # ------------------------------------------------------------------ #

    def post_event(self, name: str) -> None:
        """Queue one behaviour event (thread-safe enough for a TTY reader)."""
        if name in (EVENT_FEED, EVENT_PET, EVENT_SLEEP, EVENT_QUIT, EVENT_RANDOM):
            self._events.append(name)

    def drain_events(self) -> None:
        events, self._events = self._events, []
        for name in events:
            self._handle_event(name)

    def _handle_event(self, name: str) -> None:
        if name == EVENT_QUIT:
            self.quit = True
            return
        if name == EVENT_SLEEP:
            self._toggle_sleep()
            return
        if name == EVENT_FEED:
            self._wake_if_sleeping()
            self._start_one_shot("eat")
            return
        if name == EVENT_PET:
            self._wake_if_sleeping()
            self._start_one_shot("pet")
            return
        if name == EVENT_RANDOM:
            self._maybe_random_action(force=True)

    # ------------------------------------------------------------------ #
    # state transitions
    # ------------------------------------------------------------------ #

    def _start_one_shot(self, behaviour: str) -> None:
        clip = self.pack.clip_for(behaviour)
        if not clip:
            return
        self._state = _State(behaviour=behaviour, frame=0, loops=0, max_loops=1,
                             hold=False, text=REACTION_TEXT.get(behaviour, ""))
        self._reaction_text = self._state.text

    def _toggle_sleep(self) -> None:
        self._sleeping = not self._sleeping
        if self._sleeping:
            clip = self.pack.clip_for("sleep")
            self._state = _State(behaviour="sleep", frame=0, loops=0, max_loops=0,
                                 hold=True, hold_frame=0, text="Zzz…")
        else:
            self._go_idle()

    def _wake_if_sleeping(self) -> None:
        if self._sleeping:
            self._sleeping = False
            self._go_idle()

    def _go_idle(self) -> None:
        self._state = _State(behaviour="idle", frame=0, loops=0, max_loops=0, hold=False)
        self._reaction_text = ""

    def _maybe_random_action(self, force: bool = False) -> None:
        if self._sleeping or self.quit:
            return
        if self._state.behaviour != "idle":
            return
        now = time.monotonic()
        if not force and now - self._last_random_time < self.random_action_interval:
            return
        self._last_random_time = now
        if self.rng.random() > self.random_action_chance:
            return
        weights = [w for _, w in RANDOM_ACTIONS]
        choice = self.rng.choices([b for b, _ in RANDOM_ACTIONS], weights=weights, k=1)[0]
        self._start_one_shot(choice)

    # ------------------------------------------------------------------ #
    # ticking / frames
    # ------------------------------------------------------------------ #

    def tick(self, dt: float) -> None:
        """Advance the animation clock by ``dt`` seconds and poll status."""
        self.drain_events()
        self._maybe_random_action(force=False)
        self._poll_status()
        if self.quit:
            return
        self._frame_accum += dt
        if self._frame_accum < self.period:
            return
        self._frame_accum -= self.period
        self._advance_frame()

    def _advance_frame(self) -> None:
        state = self._state
        clip = self.pack.clip_for(state.behaviour)
        n = len(clip)
        if n <= 1 and state.hold:
            state.frame = state.hold_frame
            return
        state.frame += 1
        if state.frame < n:
            return
        # end of clip
        if state.hold:
            state.frame = n - 1 if n else 0
            return
        if state.max_loops > 0:
            state.loops += 1
            if state.loops >= state.max_loops:
                self._finish_oneshot()
                return
        state.frame = 0

    def _finish_oneshot(self) -> None:
        self._reaction_text = ""
        if self._sleeping:
            self._state = _State(behaviour="sleep", frame=0, loops=0, max_loops=0,
                                 hold=True, hold_frame=0, text="Zzz…")
        else:
            self._go_idle()

    def _poll_status(self) -> None:
        now = time.monotonic()
        if now - self._last_status_poll < self.status_poll_interval:
            return
        self._last_status_poll = now
        try:
            info = self.status_source.poll()
        except Exception:  # noqa: BLE001 - a broken source must not crash the pet
            info = None
        if info is not None:
            self._status = info

    # ------------------------------------------------------------------ #
    # queries for renderers
    # ------------------------------------------------------------------ #

    def current_frame(self) -> tuple:
        """Return ``(behaviour, frame_index)`` for the current frame."""
        state = self._state
        clip = self.pack.clip_for(state.behaviour)
        n = len(clip)
        index = 0
        if n:
            index = min(state.frame, n - 1)
        return (state.behaviour, index)

    def bubble_lines(self) -> List[str]:
        """Lines to draw above the pet (behaviour reaction + dsh status)."""
        lines: List[str] = []
        text = self._reaction_text or self._state.text
        if text:
            lines.append(text)
        if not self._sleeping:
            lines.extend(format_status(self._status, self.bubble_width))
        return lines

    def is_sleeping(self) -> bool:
        return self._sleeping

    def status(self) -> Optional[StatusInfo]:
        return self._status

    def close(self) -> None:
        self.quit = True
        try:
            self.status_source.close()
        except Exception:  # noqa: BLE001
            pass
