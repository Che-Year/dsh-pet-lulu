"""Renderer tests: bubble drawing, ANSI escapes and full redraw."""

import io
import unittest

from dsh_pet.renderer import AnsiRenderer, _cell_escape, _draw_bubble
from dsh_pet.sprite import AsciiSpritePack, blocks_from_grid
from dsh_pet.pet_core import PetCore
from dsh_pet.dsh_integration import NoneStatusSource


class BubbleTests(unittest.TestCase):
    def test_draw_bubble(self):
        lines = _draw_bubble(["hello", "world"], width=20)
        self.assertEqual(lines[0][0], "╭")
        self.assertEqual(lines[-1][0], "╰")
        self.assertIn("│hello│", lines)

    def test_empty(self):
        self.assertEqual(_draw_bubble([], 20), [])


class CellEscapeTests(unittest.TestCase):
    def test_opaque_pair(self):
        block = (((255, 0, 0), 255), ((0, 0, 255), 255))
        esc = _cell_escape(block, True)
        self.assertIn("38;2;255;0;0", esc)
        self.assertIn("48;2;0;0;255", esc)
        self.assertIn("▀", esc)

    def test_transparent_top(self):
        block = (((0, 0, 0), 0), ((0, 255, 0), 255))
        esc = _cell_escape(block, True)
        self.assertIn("▄", esc)
        self.assertIn("49m", esc)

    def test_transparent_bottom(self):
        block = (((255, 255, 0), 255), ((0, 0, 0), 0))
        esc = _cell_escape(block, True)
        self.assertIn("▀", esc)

    def test_fully_transparent(self):
        block = (((0, 0, 0), 0), ((0, 0, 0), 0))
        esc = _cell_escape(block, False)
        self.assertIn("40m", esc)


class AnsiRendererTests(unittest.TestCase):
    def test_redraw_outputs_escape_sequences(self):
        pack = AsciiSpritePack()
        core = PetCore(pack, fps=60, status_source=NoneStatusSource())
        out = io.StringIO()
        renderer = AnsiRenderer(core, width=16, bg_color="1e1e2e", out=out, hint=False)
        core.tick(core.period)
        renderer._draw()
        text = out.getvalue()
        self.assertIn("\x1b[", text)
        self.assertIn("▀", text)

    def test_bubble_included(self):
        pack = AsciiSpritePack()
        core = PetCore(pack, fps=60, status_source=NoneStatusSource())
        out = io.StringIO()
        renderer = AnsiRenderer(core, width=16, bg_color="1e1e2e", out=out, hint=False)
        core.post_event("feed")
        core.tick(core.period)
        renderer._draw()
        self.assertIn("🍉", out.getvalue())

    def test_run_loop_stops_on_quit(self):
        pack = AsciiSpritePack()
        core = PetCore(pack, fps=200, status_source=NoneStatusSource())
        out = io.StringIO()
        renderer = AnsiRenderer(core, width=16, bg_color=None, out=out, hint=False)
        core.post_event("quit")
        renderer.run()
        self.assertTrue(core.quit)
        self.assertIn("\x1b[?1049h", out.getvalue())  # alt screen entered
        self.assertIn("\x1b[?1049l", out.getvalue())  # ... and left


if __name__ == "__main__":
    unittest.main()
