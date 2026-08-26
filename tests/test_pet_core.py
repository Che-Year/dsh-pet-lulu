"""PetCore state machine and animation engine tests (simulated input)."""

import unittest

from dsh_pet.dsh_integration import NoneStatusSource
from dsh_pet.pet_core import (EVENT_FEED, EVENT_PET, EVENT_QUIT, EVENT_SLEEP,
                              PetCore)
from dsh_pet.sprite import AsciiSpritePack


class _CountingSource(NoneStatusSource):
    """Status source that counts polls, so tests can assert polling happens."""

    def __init__(self):
        self.polls = 0

    def poll(self):
        self.polls += 1
        return None


def make_core(**kw):
    pack = AsciiSpritePack()
    kw.setdefault("fps", 10)
    kw.setdefault("status_source", _CountingSource())
    kw.setdefault("status_poll_interval", 0.01)
    return PetCore(pack, **kw)


class PetCoreTests(unittest.TestCase):
    def test_initial_idle(self):
        core = make_core()
        behaviour, index = core.current_frame()
        self.assertEqual(behaviour, "idle")
        self.assertEqual(index, 0)

    def test_idle_loops_forward(self):
        core = make_core()
        idle_frames = len(core.pack.clip_for("idle").frames)
        for _ in range(idle_frames * 2 + 5):
            core.tick(core.period)
        behaviour, index = core.current_frame()
        self.assertEqual(behaviour, "idle")
        self.assertTrue(0 <= index < idle_frames)

    def test_feed_plays_oneshot_then_returns_to_idle(self):
        core = make_core()
        core.post_event(EVENT_FEED)
        core.tick(core.period)
        behaviour, _ = core.current_frame()
        self.assertEqual(behaviour, "eat")
        self.assertIn("🍉", "\n".join(core.bubble_lines()))
        # let the one-shot finish
        for _ in range(len(core.pack.clip_for("eat").frames) + 2):
            core.tick(core.period)
        behaviour, _ = core.current_frame()
        self.assertEqual(behaviour, "idle")
        self.assertNotIn("🍉", "\n".join(core.bubble_lines()))

    def test_pet_plays_wave(self):
        core = make_core()
        core.post_event(EVENT_PET)
        core.tick(core.period)
        behaviour, _ = core.current_frame()
        self.assertEqual(behaviour, "pet")
        for _ in range(len(core.pack.clip_for("pet").frames) + 2):
            core.tick(core.period)
        self.assertEqual(core.current_frame()[0], "idle")

    def test_sleep_toggle(self):
        core = make_core()
        core.post_event(EVENT_SLEEP)
        core.tick(core.period)
        self.assertTrue(core.is_sleeping())
        behaviour, _ = core.current_frame()
        self.assertEqual(behaviour, "sleep")
        self.assertIn("Zzz", "\n".join(core.bubble_lines()))
        # frames are held while sleeping
        b1, i1 = core.current_frame()
        for _ in range(10):
            core.tick(core.period)
        b2, i2 = core.current_frame()
        self.assertEqual((b1, i1), (b2, i2))
        # toggle back
        core.post_event(EVENT_SLEEP)
        core.tick(core.period)
        self.assertFalse(core.is_sleeping())
        self.assertEqual(core.current_frame()[0], "idle")

    def test_feed_wakes_sleeping_pet(self):
        core = make_core()
        core.post_event(EVENT_SLEEP)
        core.tick(core.period)
        self.assertTrue(core.is_sleeping())
        core.post_event(EVENT_FEED)
        core.tick(core.period)
        self.assertFalse(core.is_sleeping())
        self.assertEqual(core.current_frame()[0], "eat")

    def test_quit_flag(self):
        core = make_core()
        core.post_event(EVENT_QUIT)
        core.tick(core.period)
        self.assertTrue(core.quit)

    def test_events_drain_in_order(self):
        core = make_core()
        core.post_event(EVENT_PET)
        core.post_event(EVENT_SLEEP)
        core.tick(core.period)  # drains both
        self.assertTrue(core.is_sleeping())  # sleep won after pet started
        # pet one-shot is interrupted by sleep
        self.assertEqual(core.current_frame()[0], "sleep")

    def test_status_polling_happens(self):
        source = _CountingSource()
        core = make_core(status_source=source, status_poll_interval=0.001)
        for _ in range(30):
            core.tick(core.period)
        self.assertGreater(source.polls, 0)

    def test_random_action_event_forced(self):
        core = make_core(random_action_chance=1.0)
        seen = set()
        for _ in range(20):
            core.post_event("random")
            core.tick(core.period)
            seen.add(core.current_frame()[0])
        # at least one random reaction must have played (blink may finish
        # within a single tick and fall back to idle, which is fine)
        self.assertTrue(seen & {"walk", "walk-left", "jump", "yawn", "look", "blink"},
                        f"no random reaction observed, got {seen}")
        # ... and the pet returns to idle afterwards
        for _ in range(60):
            core.tick(core.period)
        self.assertEqual(core.current_frame()[0], "idle")

    def test_random_action_not_during_sleep(self):
        core = make_core(random_action_chance=1.0)
        core.post_event(EVENT_SLEEP)
        core.tick(core.period)
        core.post_event("random")
        core.tick(core.period)
        self.assertEqual(core.current_frame()[0], "sleep")

    def test_unknown_event_ignored(self):
        core = make_core()
        core.post_event("explode")
        core.tick(core.period)
        self.assertEqual(core.current_frame()[0], "idle")


if __name__ == "__main__":
    unittest.main()
