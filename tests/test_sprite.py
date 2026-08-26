"""Sprite loading and block conversion tests."""

import unittest

from dsh_pet import sprite
from dsh_pet.sprite import AsciiSpritePack, SpriteError, load_pack

HAVE_PIL = sprite.HAVE_PIL


@unittest.skipUnless(HAVE_PIL, "Pillow not available")
class SpritePackTests(unittest.TestCase):
    def test_lulu_pack_loads(self):
        pack = load_pack("lulu")
        self.assertIsInstance(pack, sprite.SpritePack)
        self.assertTrue(pack.display_name)
        for behaviour in ("idle", "eat", "pet", "jump", "walk", "yawn", "sleep", "look"):
            clip = pack.clip_for(behaviour)
            self.assertTrue(clip, f"missing clip for {behaviour}")
            self.assertGreater(len(clip.frames), 0)

    def test_lulu_idle_has_seven_frames(self):
        pack = sprite.SpritePack("lulu")
        idle = pack.clip_for("idle")
        self.assertEqual(len(idle.frames), 7)

    def test_capybara_pack_loads(self):
        pack = load_pack("capybara")
        self.assertIsInstance(pack, sprite.SpritePack)
        idle = pack.clip_for("idle")
        self.assertEqual(len(idle.frames), 20)
        look = pack.clip_for("look")
        self.assertEqual(len(look.frames), 16)

    def test_frame_size_is_cell(self):
        pack = sprite.SpritePack("lulu")
        frame = pack.clip_for("idle").frames[0]
        self.assertEqual(frame.size, (sprite.CELL_W, sprite.CELL_H))

    def test_blocks_generation(self):
        pack = sprite.SpritePack("lulu")
        frame = pack.clip_for("idle").frames[0]
        blocks = pack.frame_blocks(frame, width=48, bg=(30, 30, 46))
        # 192x208 @ 48 wide with 2:1 half blocks -> round(208/192*48/2) rows
        self.assertEqual(len(blocks), 26)
        row = blocks[0]
        self.assertEqual(len(row), 48)
        (top, ta), (bot, ba) = row[0]
        self.assertEqual(len(top), 3)
        self.assertTrue(0 <= ta <= 255)

    def test_unknown_pet_type(self):
        with self.assertRaises(SpriteError):
            sprite.SpritePack("dragon")


class AsciiFallbackTests(unittest.TestCase):
    def test_ascii_pack(self):
        pack = AsciiSpritePack()
        for behaviour in ("idle", "eat", "pet", "sleep", "yawn", "jump"):
            clip = pack.clip_for(behaviour)
            self.assertTrue(clip)
        self.assertEqual(pack.display_name, "ascii-lulu (fallback)")

    def test_grid_blocks(self):
        pack = AsciiSpritePack()
        frame = pack.clip_for("idle").frames[0]
        blocks = sprite.blocks_from_grid(frame, width=16, bg=(0, 0, 0))
        self.assertGreater(len(blocks), 0)
        self.assertEqual(len(blocks[0]), 16)


if __name__ == "__main__":
    unittest.main()
