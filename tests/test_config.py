"""Config loading tests."""

import os
import unittest

from dsh_pet.config import Config, _apply_cli, find_config_file, load_config

from _tmp import tmp_dir


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        cfg = load_config()
        self.assertEqual(cfg.pet_type, "lulu")
        self.assertEqual(cfg.fps, 10)
        self.assertEqual(cfg.renderer_mode, "web")  # default mode is the web pet
        self.assertEqual(cfg.status_source, "mock")
        self.assertEqual(cfg.web_port, 8765)
        self.assertTrue(cfg.open_browser)
        self.assertAlmostEqual(cfg.frame_period(), 0.1)

    def test_find_config_file_explicit_missing(self):
        self.assertIsNone(find_config_file("/nonexistent/nope.ini"))

    def test_ini_roundtrip(self):
        with tmp_dir() as tmp:
            path = os.path.join(tmp, ".dsh_pet_config")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("[general]\npet_type = capybara\n\n"
                         "[animation]\nfps = 12\n\n"
                         "[renderer]\nmode = tk\ntk_scale = 2\n\n"
                         "[dsh]\nstatus_source = file\n"
                         "status_file = /tmp/x.json\nbubble_width = 30\n")
            cfg = load_config(path)
            self.assertEqual(cfg.pet_type, "capybara")
            self.assertEqual(cfg.fps, 12)
            self.assertEqual(cfg.renderer_mode, "tk")
            self.assertEqual(cfg.tk_scale, 2)
            self.assertEqual(cfg.status_source, "file")
            self.assertEqual(cfg.status_file, "/tmp/x.json")
            self.assertEqual(cfg.bubble_width, 30)

    def test_bad_ini_falls_back_to_defaults(self):
        with tmp_dir() as tmp:
            path = os.path.join(tmp, "bad.ini")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("this is not a valid ini [[[section\n")
            cfg = load_config(path)  # must not raise
            self.assertEqual(cfg.pet_type, "lulu")

    def test_cli_override_wins(self):
        cfg = Config()
        _apply_cli(cfg, {"fps": "30", "pet_type": "capybara"})
        self.assertEqual(cfg.fps, 30)
        self.assertEqual(cfg.pet_type, "capybara")

    def test_sanitisation(self):
        cfg = Config()
        _apply_cli(cfg, {"fps": "0", "ansi_width": "3", "bubble_width": "1000"})
        self.assertEqual(cfg.fps, 1)
        self.assertEqual(cfg.ansi_width, 8)
        self.assertEqual(cfg.bubble_width, 80)


if __name__ == "__main__":
    unittest.main()
