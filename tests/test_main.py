"""Entry point tests: argument parsing and key mapping (simulated input)."""

import io
import unittest

from dsh_pet.main import apply_args, build_parser, map_key
from dsh_pet.config import Config

KEYS = {"feed": "f", "pet": "p", "sleep": "s", "quit": "q"}


class MapKeyTests(unittest.TestCase):
    def test_feed(self):
        self.assertEqual(map_key("f", KEYS), "feed")
        self.assertEqual(map_key("F", KEYS), "feed")

    def test_pet(self):
        self.assertEqual(map_key("p", KEYS), "pet")

    def test_sleep(self):
        self.assertEqual(map_key("s", KEYS), "sleep")

    def test_quit_and_ctrl_c(self):
        self.assertEqual(map_key("q", KEYS), "quit")
        self.assertEqual(map_key("\x03", KEYS), "quit")

    def test_unknown(self):
        self.assertIsNone(map_key("x", KEYS))
        self.assertIsNone(map_key("", KEYS))

    def test_custom_keys(self):
        custom = {"feed": "a", "pet": "b", "sleep": "c", "quit": "q"}
        self.assertEqual(map_key("a", custom), "feed")
        self.assertEqual(map_key("b", custom), "pet")


class ArgparseTests(unittest.TestCase):
    def test_parser_builds(self):
        parser = build_parser()
        args = parser.parse_args(["--pet-type", "capybara", "--fps", "15",
                                  "--gui", "--status-source", "file",
                                  "--status-file", "s.json", "--no-hint"])
        self.assertEqual(args.pet_type, "capybara")
        self.assertEqual(args.fps, 15)
        self.assertTrue(args.gui)
        self.assertTrue(args.no_hint)

    def test_parser_web_options(self):
        parser = build_parser()
        args = parser.parse_args(["--renderer", "web", "--port", "9000",
                                  "--no-browser"])
        self.assertEqual(args.renderer, "web")
        self.assertEqual(args.port, 9000)
        self.assertTrue(args.no_browser)

    def test_apply_args(self):
        cfg = Config()
        parser = build_parser()
        args = parser.parse_args(["--fps", "20", "--width", "60",
                                  "--bg-color", "1e1e2e", "--status-source", "none",
                                  "--port", "9999", "--no-browser"])
        apply_args(cfg, args)
        self.assertEqual(cfg.fps, 20)
        self.assertEqual(cfg.ansi_width, 60)
        self.assertEqual(cfg.bg_color, "1e1e2e")
        self.assertEqual(cfg.status_source, "none")
        self.assertEqual(cfg.web_port, 9999)
        self.assertFalse(cfg.open_browser)

    def test_default_mode_is_web(self):
        cfg = Config()
        self.assertEqual(cfg.renderer_mode, "web")

    def test_gui_sets_tk_mode(self):
        cfg = Config()
        args = build_parser().parse_args(["--gui"])
        apply_args(cfg, args)
        self.assertEqual(cfg.renderer_mode, "tk")


if __name__ == "__main__":
    unittest.main()
