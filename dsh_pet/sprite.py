"""Sprite loading, clipping and downsampling for dsh-pet.

The bundled sprite packs follow the "Codex V2 pet contract": a WebP atlas of
1536x2288 pixels laid out as an 8x11 grid of 192x208 cells.

* rows 0-8   : nine standard animation states
  (idle, running-right, running-left, waving, jumping, failed, waiting,
   running, review)
* rows 9-10  : sixteen clockwise look directions

``lulu`` ships a static atlas (one full-canvas frame), ``capybara`` ships an
animated atlas (20 image-time phases) plus 180 explicit per-state PNG frames
under ``frames/<state>/NN.png`` which take precedence when present.

Every clip is a list of RGBA frames plus a loop flag.  The ANSI renderer
downsamples each frame to half-block (top/bottom colour) rows.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

try:  # Pillow is an optional dependency; the ASCII fallback needs it not.
    from PIL import Image

    HAVE_PIL = True
except Exception:  # noqa: BLE001 - missing dependency
    Image = None  # type: ignore
    HAVE_PIL = False

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

CELL_W, CELL_H = 192, 208
GRID_COLS, GRID_ROWS = 8, 11

# Valid pet types.
PET_TYPES = ("lulu", "capybara")

# Default row layout for the nine standard v2 states (from the V2 contract).
# cols == None means "every used cell of that row".
ROW_LAYOUT: Dict[str, Tuple[int, Optional[Sequence[int]]]] = {
    "idle": (0, None),
    "walk": (1, None),
    "walk-left": (2, None),
    "wave": (3, None),
    "jump": (4, None),
    "fail": (5, None),
    "wait": (6, None),
    "work": (7, None),
    "review": (8, None),
}

# Number of used cells per row for the lulu pack (from lulu validation.json).
LULU_USED_CELLS = {0: 7, 1: 8, 2: 8, 3: 4, 4: 5, 5: 8, 6: 6, 7: 6, 8: 6}


class SpriteError(RuntimeError):
    """Raised when a sprite pack cannot be loaded."""


@dataclass
class Clip:
    """A named animation clip: ordered frames plus loop semantics."""

    name: str
    frames: List["object"] = field(default_factory=list)  # PIL Images (RGBA)
    loop: bool = True

    def __len__(self) -> int:
        return len(self.frames)

    def __bool__(self) -> bool:
        return bool(self.frames)


# --------------------------------------------------------------------------- #
# ASCII / pixel-art fallback (used when Pillow is unavailable or a pack is
# missing).  Frames are pixel grids: rows of 24-bit RGB hex strings, '.' for
# transparent.
# --------------------------------------------------------------------------- #

_PALETTE = {
    "Y": (247, 196, 80),  # body yellow
    "y": (232, 172, 62),  # body shade
    "O": (235, 128, 50),  # orange muzzle / hat fruit
    "o": (210, 100, 40),  # orange shade
    "G": (86, 168, 90),  # leaf green
    "K": (66, 58, 46),  # dark outline
    "W": (255, 250, 240),  # white
    "P": (240, 120, 150),  # pink blush
    "B": (90, 120, 200),  # blue bandana
}


def _px(frame: Sequence[str]) -> List[List[Optional[Tuple[int, int, int]]]]:
    grid: List[List[Optional[Tuple[int, int, int]]]] = []
    for row in frame:
        line: List[Optional[Tuple[int, int, int]]] = []
        for ch in row:
            line.append(_PALETTE.get(ch))
        grid.append(line)
    return grid


# 16x14 pixel frames of a tiny capybara face.
_ASCII_FRAMES: Dict[str, List[Sequence[str]]] = {
    "idle": [
        [
            "......KKKK......",
            "....KKYYYYKK....",
            "...KYYYYYYYYK...",
            "..KYYYYYYYYYYK..",
            "..KYYWYYYWYYYK..",
            "..KYWOYYYOWYK...",
            "...KYYYYYYYYK...",
            "..KYYKYYYYKYYK..",
            ".KYYYyKYYKyYYYK.",
            ".KYYYYYYYYYYYYK.",
            ".KYYYyYYYYyYYYK.",
            "..KKKKKKKKKKKK..",
            "...KKK....KKK...",
            "................",
        ],
        [
            "......KKKK......",
            "....KKYYYYKK....",
            "...KYYYYYYYYK...",
            "..KYYYYYYYYYYK..",
            "..KYYWYYYWYYYK..",
            "..KYWOYYYOWYK...",
            "...KYYYYYYYYK...",
            "..KYYKYYYYKYYK..",
            ".KYYYyKYYKyYYYK.",
            ".KYYYYYYYYYYYYK.",
            ".KYYYyYYYYyYYYK.",
            "..KKKKKKKKKKKK..",
            "...KKK....KKK...",
            "................",
        ],
    ],
    "blink": [
        [
            "......KKKK......",
            "....KKYYYYKK....",
            "...KYYYYYYYYK...",
            "..KYYYYYYYYYYK..",
            "..KYY----YYYK...",
            "..KYWOYYYOWYK...",
            "...KYYYYYYYYK...",
            "..KYYKYYYYKYYK..",
            ".KYYYyKYYKyYYYK.",
            ".KYYYYYYYYYYYYK.",
            ".KYYYyYYYYyYYYK.",
            "..KKKKKKKKKKKK..",
            "...KKK....KKK...",
            "................",
        ],
    ],
    "eat": [
        [
            "......KKKK......",
            "....KKYYYYKK....",
            "...KYYYYYYYYK...",
            "..KYYYYYYYYYYK..",
            "..KYYWYYYWYYYK..",
            "..KYWOYYYOWYK...",
            "...KYYYYYYYYK...",
            "..KOYOOOOOOYOK..",
            ".KYYYYYYYYYYYYK.",
            ".KYYYYYYYYYYYYK.",
            "..KKKKKKKKKKKK..",
            "...KKK....KKK...",
            "................",
            "................",
        ],
        [
            "......KKKK......",
            "....KKYYYYKK....",
            "...KYYYYYYYYK...",
            "..KYYYYYYYYYYK..",
            "..KYYWYYYWYYYK..",
            "..KYWOYYYOWYK...",
            "...KYYYYYYYYK...",
            "..KYYYYYYYYYYK..",
            ".KYYYYYYYYYYYYK.",
            ".KYYYYYYYYYYYYK.",
            "..KKKKKKKKKKKK..",
            "...KKK....KKK...",
            "................",
            "................",
        ],
        [
            "......KKKK......",
            "....KKYYYYKK....",
            "...KYYYYYYYYK...",
            "..KYYYYYYYYYYK..",
            "..KYYWYYYWYYYK..",
            "..KYWOYYYOWYK...",
            "...KYYYYYYYYK...",
            "..KOYOOOOOOYOK..",
            ".KYYYYYYYYYYYYK.",
            ".KYYYYYYYYYYYYK.",
            "..KKKKKKKKKKKK..",
            "...KKK....KKK...",
            "................",
            "................",
        ],
    ],
    "wave": [
        [
            "......KKKK......",
            "....KKYYYYKK....",
            "...KYYYYYYYYK...",
            "..KYYYYYYYYYYK..",
            "..KYYWYYYWYYYK..",
            "..KYWOYYYOWYK...",
            "...KYYYYYYYYK...",
            "..KYYKYYYYKYYK..",
            ".KYYYyKYYKyYYYK.",
            ".KYYYYYYYYYYYYK.",
            ".KYYYyYYYYyYYYK.",
            "..KKKKKKKKKKKK..",
            "...KKK....KKK...",
            "................",
        ],
        [
            "......KKKK......",
            "....KKYYYYKK....",
            "...KYYYYYYYYK...",
            "..KYYYYYYYYYYK..",
            "..KYYWYYYWYYYK..",
            "..KYWOYYYOWYK...",
            "...KYYYYYYYYK...",
            "..KYYKYYYYKYYK..",
            ".KYYYyKYYKyYYYK.",
            ".KYYYYYYYYYYYYK.",
            ".KYYYyYYYYyYYYK.",
            "..KKKKKKKKKKKK..",
            "...KKK....KKK...",
            "KKKK............",
        ],
        [
            "......KKKK......",
            "....KKYYYYKK....",
            "...KYYYYYYYYK...",
            "..KYYYYYYYYYYK..",
            "..KYYWYYYWYYYK..",
            "..KYWOYYYOWYK...",
            "...KYYYYYYYYK...",
            "..KYYKYYYYKYYK..",
            ".KYYYyKYYKyYYYK.",
            ".KYYYYYYYYYYYYK.",
            ".KYYYyYYYYyYYYK.",
            "..KKKKKKKKKKKK..",
            "...KKK....KKK...",
            "................",
        ],
    ],
    "sleep": [
        [
            "......KKKK......",
            "....KKYYYYKK....",
            "...KYYYYYYYYK...",
            "..KYYYYYYYYYYK..",
            "..KYY----YYYK...",
            "..KYWOYYYOWYK...",
            "...KYYYYYYYYK...",
            "..KYYKYYYYKYYK..",
            ".KYYYyKYYKyYYYK.",
            ".KYYYYYYYYYYYYK.",
            ".KYYYyYYYYyYYYK.",
            "..KKKKKKKKKKKK..",
            "...KKK....KKK...",
            "................",
        ],
    ],
}


class AsciiSpritePack:
    """Pillow-free fallback sprite pack built from pixel art."""

    def __init__(self) -> None:
        self.clips: Dict[str, Clip] = {}
        for name, frames in _ASCII_FRAMES.items():
            self.clips[name] = Clip(name=name, frames=[_px(f) for f in frames], loop=True)
        # reuse idle frames for the remaining behaviours
        self.clips.setdefault("yawn", Clip("yawn", self.clips["eat"].frames, loop=False))
        self.clips.setdefault("look", self.clips["idle"])
        # behaviours map onto available fallback clips
        self.behaviours: Dict[str, str] = {
            "idle": "idle",
            "blink": "blink",
            "eat": "eat",
            "pet": "wave",
            "jump": "idle",
            "walk": "idle",
            "walk-left": "idle",
            "yawn": "yawn",
            "sleep": "sleep",
            "look": "look",
        }

    def clip_for(self, behaviour: str) -> Clip:
        name = self.behaviours.get(behaviour, "idle")
        return self.clips[name]

    @property
    def display_name(self) -> str:
        return "ascii-lulu (fallback)"


# --------------------------------------------------------------------------- #
# Real sprite packs
# --------------------------------------------------------------------------- #


@dataclass
class _ClipSpec:
    kind: str  # 'row' | 'files' | 'look'
    row: int = 0
    cols: Optional[List[int]] = None  # for 'row': explicit columns
    files: List[str] = field(default_factory=list)  # for 'files': relative paths
    loop: bool = True


def _build_lulu_specs() -> Dict[str, _ClipSpec]:
    specs: Dict[str, _ClipSpec] = {}
    for behaviour, (row, _cols) in ROW_LAYOUT.items():
        n = LULU_USED_CELLS.get(row, 8)
        specs[behaviour] = _ClipSpec(kind="row", row=row, cols=list(range(n)), loop=True)
    specs["look"] = _ClipSpec(kind="look", loop=True)
    # bespoke behavioural clips: eat/yawn/sleep reuse idle cells (best effort)
    specs["eat"] = _ClipSpec(kind="row", row=0, cols=[0, 1, 2, 3], loop=False)
    specs["yawn"] = _ClipSpec(kind="row", row=0, cols=[1], loop=False)
    specs["sleep"] = _ClipSpec(kind="row", row=0, cols=[0], loop=False)
    specs["blink"] = _ClipSpec(kind="row", row=0, cols=[0, 2, 0], loop=False)
    return specs


def _build_capybara_specs() -> Dict[str, _ClipSpec]:
    specs: Dict[str, _ClipSpec] = {}
    states = ("idle", "running-right", "running-left", "waving", "jumping",
              "failed", "waiting", "running", "review")
    state_dir = {
        "idle": "idle", "walk": "running-right", "walk-left": "running-left",
        "wave": "waving", "jump": "jumping", "fail": "failed",
        "wait": "waiting", "work": "running", "review": "review",
    }
    for behaviour, st in state_dir.items():
        files = [f"frames/{st}/{i:02d}.png" for i in range(20)]
        specs[behaviour] = _ClipSpec(kind="files", files=files, loop=True)
    specs["look"] = _ClipSpec(kind="look", loop=True)
    # bespoke clips from the labelled idle phases (idle-phases.json):
    #   00 closed-mouth-rest, 03 mouth-open, 04 mouth-close
    specs["eat"] = _ClipSpec(kind="files",
                             files=["frames/idle/00.png", "frames/idle/03.png",
                                    "frames/idle/04.png", "frames/idle/03.png",
                                    "frames/idle/00.png"],
                             loop=False)
    specs["yawn"] = _ClipSpec(kind="files", files=["frames/idle/03.png",
                                                   "frames/idle/04.png",
                                                   "frames/idle/00.png"], loop=False)
    specs["sleep"] = _ClipSpec(kind="files", files=["frames/idle/00.png"], loop=False)
    specs["blink"] = _ClipSpec(kind="files", files=["frames/idle/00.png",
                                                    "frames/idle/02.png",
                                                    "frames/idle/00.png"], loop=False)
    return specs


def _load_pack_json(pet_dir: str) -> dict:
    path = os.path.join(pet_dir, "pet.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class SpritePack:
    """Loads one pet pack (lulu or capybara) and exposes named clips."""

    def __init__(self, pet_type: str, pet_dir: Optional[str] = None) -> None:
        if not HAVE_PIL:
            raise SpriteError("Pillow is required to load sprite packs")
        self.pet_type = pet_type
        self.pet_dir = pet_dir or os.path.join(ASSETS_DIR, pet_type)
        if not os.path.isdir(self.pet_dir):
            raise SpriteError(f"pet pack not found: {self.pet_dir}")
        self.manifest = _load_pack_json(self.pet_dir)
        self.display_name = self.manifest.get("displayName", pet_type)
        atlas_path = os.path.join(self.pet_dir, self.manifest.get("spritesheetPath", "spritesheet.webp"))
        if not os.path.isfile(atlas_path):
            raise SpriteError(f"spritesheet missing: {atlas_path}")
        self._atlas = Image.open(atlas_path).convert("RGBA")
        self._atlas_path = atlas_path
        self._n_atlas_frames = getattr(self._atlas, "n_frames", 1)
        specs = _build_lulu_specs() if pet_type == "lulu" else _build_capybara_specs()
        self.clips: Dict[str, Clip] = self._load_clips(specs)
        # behaviour -> clip name mapping
        self.behaviours = {
            "idle": "idle", "blink": "blink", "eat": "eat", "pet": "wave",
            "jump": "jump", "walk": "walk", "walk-left": "walk-left",
            "yawn": "yawn", "sleep": "sleep", "look": "look",
        }
        self._block_cache: Dict[Tuple[int, Optional[Tuple[int, int, int]]], dict] = {}

    # ---------------- clip loading ---------------- #

    def _atlas_frame(self, index: int) -> "object":
        if self._n_atlas_frames > 1:
            self._atlas.seek(index % self._n_atlas_frames)
        return self._atlas

    def _crop_cell(self, frame: "object", col: int, row: int) -> "object":
        return frame.crop((col * CELL_W, row * CELL_H, (col + 1) * CELL_W, (row + 1) * CELL_H))

    def _load_clips(self, specs: Dict[str, _ClipSpec]) -> Dict[str, Clip]:
        clips: Dict[str, Clip] = {}
        for name, spec in specs.items():
            frames: List[object] = []
            if spec.kind == "row":
                base = self._atlas_frame(0)
                for col in spec.cols or []:
                    frames.append(self._crop_cell(base, col, spec.row).convert("RGBA"))
            elif spec.kind == "files":
                for rel in spec.files:
                    path = os.path.join(self.pet_dir, rel)
                    if os.path.isfile(path):
                        frames.append(Image.open(path).convert("RGBA"))
                if not frames:
                    # fall back to the atlas row of the same name
                    frames = self._row_fallback(name)
            elif spec.kind == "look":
                frames = self._load_look_frames()
            if not frames:
                raise SpriteError(f"clip {name!r} has no frames in {self.pet_dir}")
            clips[name] = Clip(name=name, frames=frames, loop=spec.loop)
        return clips

    def _row_fallback(self, name: str) -> List[object]:
        if name in ROW_LAYOUT:
            row, _ = ROW_LAYOUT[name]
            base = self._atlas_frame(0)
            return [self._crop_cell(base, c, row).convert("RGBA") for c in range(GRID_COLS)]
        return []

    def _load_look_frames(self) -> List[object]:
        """Sixteen look directions from rows 9-10, or frames/look-directions."""
        explicit = os.path.join(self.pet_dir, "frames", "look-directions")
        if os.path.isdir(explicit):
            files = sorted(f for f in os.listdir(explicit) if f.lower().endswith(".png"))
            if files:
                return [Image.open(os.path.join(explicit, f)).convert("RGBA") for f in files]
        base = self._atlas_frame(0)
        frames = []
        for r in (9, 10):
            for c in range(GRID_COLS):
                frames.append(self._crop_cell(base, c, r).convert("RGBA"))
        return frames

    # ---------------- frame access ---------------- #

    def clip_for(self, behaviour: str) -> Clip:
        name = self.behaviours.get(behaviour, "idle")
        clip = self.clips.get(name)
        if clip is None:
            clip = self.clips["idle"]
        return clip

    # ---------------- downsampling ---------------- #

    def frame_blocks(self, frame: "object", width: int,
                     bg: Optional[Tuple[int, int, int]] = None) -> BlockGrid:
        """Downsample one RGBA frame to half-block rows for ANSI rendering."""
        img_w, img_h = frame.size
        rows = max(1, round(img_h / img_w * width / 2))
        small = frame.resize((width, rows * 2), getattr(Image, "BOX", Image.LANCZOS))
        rgba = small.load()
        blocks: BlockGrid = []
        for y in range(rows):
            line: List[Block] = []
            for x in range(width):
                top = _composite(rgba[x, y * 2], bg)
                bot = _composite(rgba[x, y * 2 + 1], bg)
                line.append((top, bot))
            blocks.append(line)
        return blocks


# A half-block cell: ((top_rgb, top_alpha), (bottom_rgb, bottom_alpha)).
Block = Tuple[Tuple[Tuple[int, int, int], int], Tuple[Tuple[int, int, int], int]]
BlockGrid = List[List[Block]]


def _composite(rgba: Tuple[int, int, int, int],
               bg: Optional[Tuple[int, int, int]]) -> Tuple[Tuple[int, int, int], int]:
    """Return ``(composited_rgb, alpha)`` for one sampled pixel."""
    r, g, b, a = rgba
    if a >= 255:
        return ((r, g, b), 255)
    if a <= 0:
        return ((bg if bg is not None else (0, 0, 0)), 0)
    f = a / 255.0
    if bg is None:
        return ((int(r * f), int(g * f), int(b * f)), a)
    return ((int(r * f + bg[0] * (1 - f)),
             int(g * f + bg[1] * (1 - f)),
             int(b * f + bg[2] * (1 - f))), a)


def blocks_from_grid(frame: Sequence[Sequence[Optional[Tuple[int, int, int]]]],
                     width: int,
                     bg: Optional[Tuple[int, int, int]] = None) -> BlockGrid:
    """Convert an ASCII pixel-art frame (grid of RGB tuples / None) to blocks."""
    grid_h = len(frame)
    grid_w = len(frame[0]) if grid_h else 0
    if grid_w == 0 or grid_h == 0:
        return []
    rows = max(1, round(grid_h / grid_w * width / 2))
    # nearest-neighbour scale to (width, rows*2)
    sx = grid_w / width
    sy = grid_h / (rows * 2)
    blocks: BlockGrid = []
    for y in range(rows):
        line: List[Block] = []
        for x in range(width):
            def sample(px: int, py: int) -> Tuple[Tuple[int, int, int], int]:
                gx = min(grid_w - 1, int(px * sx))
                gy = min(grid_h - 1, int(py * sy))
                colour = frame[gy][gx]
                if colour is None:
                    return ((bg if bg is not None else (0, 0, 0)), 0)
                return (colour, 255)

            top = sample(x, y * 2)
            bot = sample(x, y * 2 + 1)
            line.append((top, bot))
        blocks.append(line)
    return blocks


def frame_blocks(pack: "object", frame: "object", width: int,
                 bg: Optional[Tuple[int, int, int]] = None) -> BlockGrid:
    """Dispatch block conversion for both PIL frames and pixel-art grids."""
    if HAVE_PIL and isinstance(frame, Image.Image):
        return pack.frame_blocks(frame, width, bg)
    return blocks_from_grid(frame, width, bg)


def parse_color(hex_color: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """Parse '#rrggbb' / 'rrggbb' into an RGB tuple (or None)."""
    if not hex_color:
        return None
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        return None
    try:
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except ValueError:
        return None


def load_pack(pet_type: str) -> "object":
    """Load a sprite pack; falls back to the ASCII pack on any failure."""
    pet_type = (pet_type or "lulu").strip().lower()
    if pet_type not in PET_TYPES:
        raise SpriteError(f"unknown pet type {pet_type!r}; choose from {PET_TYPES}")
    try:
        if HAVE_PIL:
            return SpritePack(pet_type)
    except Exception as exc:  # noqa: BLE001 - degrade gracefully
        import warnings

        warnings.warn(f"sprite pack {pet_type!r} could not be loaded ({exc}); "
                      "using ASCII fallback pet")
    return AsciiSpritePack()
