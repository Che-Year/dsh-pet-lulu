#!/usr/bin/env python3
"""Render a static PNG and an animated GIF preview of the pet from the real
sprite assets.  Output: docs/preview.png and docs/preview.gif.

Usage: python scripts/render_preview.py [--pet-type capybara] [--scale 2]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dsh_pet.sprite import load_pack  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pet-type", default="lulu", choices=("lulu", "capybara"))
    parser.add_argument("--scale", type=int, default=2)
    args = parser.parse_args()

    from PIL import Image

    pack = load_pack(args.pet_type)
    docs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")
    os.makedirs(docs, exist_ok=True)

    # static preview: first idle frame scaled up
    idle = pack.clip_for("idle").frames[0]
    if hasattr(idle, "resize"):
        canvas = idle.convert("RGBA").resize(
            (idle.width * args.scale, idle.height * args.scale))
        canvas.save(os.path.join(docs, "preview.png"))
    else:
        print("ASCII fallback pack; skipping image preview")
        return 0

    # animated preview: first N idle frames (or eat reaction for fun)
    frames = pack.clip_for("idle").frames[:6]
    if len(frames) < 2:
        frames = pack.clip_for("eat").frames + pack.clip_for("idle").frames[:2]
    frames = [f.convert("RGBA").resize((f.width * args.scale, f.height * args.scale))
              for f in frames if hasattr(f, "resize")]
    if len(frames) < 2:
        print("not enough frames for a GIF")
        return 0
    frames[0].save(os.path.join(docs, "preview.gif"), save_all=True,
                   append_images=frames[1:], duration=150, loop=0,
                   disposal=2, transparency=0)
    print(f"wrote docs/preview.png and docs/preview.gif ({len(frames)} frames, {args.pet_type})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
