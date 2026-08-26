"""WebRenderer tests: HTTP page, manifest, state, sheets and interactions."""

import json
import time
import unittest
import urllib.request

from dsh_pet.dsh_integration import NoneStatusSource
from dsh_pet.pet_core import PetCore
from dsh_pet.sprite import AsciiSpritePack
from dsh_pet.web_renderer import WebRenderer

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def get(url: str):
    return urllib.request.urlopen(url, timeout=8)


def post(url: str, body: dict):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=8)


class WebRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pack = AsciiSpritePack()
        core = PetCore(pack, fps=20, status_source=NoneStatusSource())
        cls.renderer = WebRenderer(core, port=0, open_browser=False)
        cls.renderer.start()
        port = cls.renderer._httpd.server_address[1]
        cls.base = f"http://127.0.0.1:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.renderer.stop()

    # ------------------------------------------------------------------ #

    def test_index_page(self):
        with get(self.base + "/") as resp:
            self.assertEqual(resp.status, 200)
            html = resp.read().decode("utf-8")
        self.assertIn("dsh-pet", html)
        self.assertIn("sprite", html)
        self.assertIn("/api/state", html)

    def test_manifest(self):
        data = json.load(get(self.base + "/api/manifest"))
        self.assertIn("clips", data)
        self.assertIn("idle", data["clips"])
        self.assertGreater(data["cell"]["width"], 0)
        self.assertIn("behaviours", data)
        self.assertGreater(data["clips"]["idle"]["frames"], 0)

    def test_state_snapshot(self):
        data = json.load(get(self.base + "/api/state"))
        self.assertIn("behaviour", data)
        self.assertIn("clip", data)
        self.assertIn("bubble", data)
        self.assertTrue(data["visible"])
        self.assertFalse(data["sleeping"])

    def test_sheet_png(self):
        with get(self.base + "/api/sheet/idle.png") as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.read()[:8], PNG_MAGIC)

    def test_sheet_unknown_clip_404(self):
        try:
            get(self.base + "/api/sheet/nope.png")
            self.fail("expected 404")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 404)

    def test_interact_endpoint(self):
        data = json.load(post(self.base + "/api/interact", {"kind": "pet"}))
        self.assertTrue(data["ok"])
        self.assertTrue(data["text"])
        data2 = json.load(post(self.base + "/api/interact", {"kind": "feed"}))
        self.assertTrue(data2["ok"])
        self.assertIn("🍉", data2["text"])

    def test_interact_changes_state(self):
        self.renderer.interact("pet")
        self.renderer.core.tick(self.renderer.core.period)
        snapshot = self.renderer.state_snapshot()
        self.assertEqual(snapshot["behaviour"], "pet")

    def test_sleep_toggle(self):
        data = json.load(post(self.base + "/api/sleep", {}))
        self.assertTrue(data["sleeping"])
        data = json.load(post(self.base + "/api/sleep", {}))
        self.assertFalse(data["sleeping"])

    def test_hide_summon(self):
        json.load(post(self.base + "/api/hide", {}))
        self.assertFalse(json.load(get(self.base + "/api/state"))["visible"])
        json.load(post(self.base + "/api/summon", {}))
        self.assertTrue(json.load(get(self.base + "/api/state"))["visible"])

    def test_quit_shuts_down(self):
        renderer = WebRenderer(PetCore(AsciiSpritePack(), fps=20,
                                       status_source=NoneStatusSource()),
                               port=0, open_browser=False)
        renderer.start()
        port = renderer._httpd.server_address[1]
        post(f"http://127.0.0.1:{port}/api/quit", {})
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if renderer._server_thread is not None and not renderer._server_thread.is_alive():
                break
            time.sleep(0.05)
        self.assertFalse(renderer._server_thread.is_alive())


if __name__ == "__main__":
    unittest.main()
