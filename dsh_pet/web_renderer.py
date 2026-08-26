"""WebRenderer: render the pet in a browser (the default mode).

The pet logic stays in Python (:class:`dsh_pet.pet_core.PetCore` drives the
state machine, random actions and dsh status polling); a tiny HTTP server
(standard library only) serves

* a self-contained HTML page (vanilla JS, no framework) that draws the pet
  with CSS sprite animation,
* ``/api/manifest`` - the spritesheet geometry and per-clip tracks,
* ``/api/state``   - the live animation/status snapshot (polled by the page),
* ``/api/sheet/<clip>.png`` - one horizontal strip per animation clip,
* ``/api/interact``, ``/api/sleep``, ``/api/random``, ``/api/hide``,
  ``/api/summon``, ``/api/quit`` - interactions.

The page renders whatever clip the server selects (idle/eat/pet/jump/...),
so one dumb client displays every pet and every behaviour.
"""

from __future__ import annotations

import io
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional, Tuple

from . import sprite as sprite_mod
from .pet_core import EVENT_SLEEP, REACTION_TEXT, PetCore

DEFAULT_PORT = 8765

# --------------------------------------------------------------------------- #
# sprite strip building
# --------------------------------------------------------------------------- #


def _grid_to_pil(grid):
    """Convert an ASCII pixel-art frame (grid of RGB/None) to a PIL image."""
    from PIL import Image

    h = len(grid)
    w = len(grid[0]) if h else 0
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(grid):
        for x, colour in enumerate(row):
            if colour is not None:
                px[x, y] = (colour[0], colour[1], colour[2], 255)
    return img


def _frame_to_pil(frame):
    """Normalise a pack frame (PIL Image or ASCII pixel grid) to RGBA PIL."""
    if sprite_mod.HAVE_PIL and hasattr(frame, "convert"):
        return frame.convert("RGBA")
    return _grid_to_pil(frame)


def build_clip_sheet(frames) -> bytes:
    """Lay one clip's frames horizontally into a single RGBA PNG (bytes)."""
    from PIL import Image

    imgs = [_frame_to_pil(f) for f in frames]
    if not imgs:
        raise ValueError("clip has no frames")
    w, h = imgs[0].size
    sheet = Image.new("RGBA", (w * len(imgs), h), (0, 0, 0, 0))
    for i, img in enumerate(imgs):
        sheet.paste(img, (i * w, 0))
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    return buf.getvalue()


def _frame_size(frame) -> Tuple[int, int]:
    if hasattr(frame, "size"):
        return (frame.size[0], frame.size[1])
    return (len(frame[0]) if frame else 0, len(frame) if frame else 0)


def _escape_html(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


# --------------------------------------------------------------------------- #
# HTML page
# --------------------------------------------------------------------------- #

_HTML = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  :root { --bg: #17151f; --panel: rgba(30,28,40,.94); --line: #3a3650; }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; background: var(--bg); overflow: hidden;
               font-family: "Segoe UI", system-ui, sans-serif; color: #ddd; }
  #hint { position: fixed; left: 12px; bottom: 8px; font-size: 12px; color: #777; z-index: 5; }
  #status-line { position: fixed; right: 12px; top: 8px; font-size: 12px; color: #999; z-index: 5;
                 text-align: right; max-width: 60%; }
  #pet { position: fixed; right: 40px; bottom: 40px; z-index: 2147483000;
         cursor: grab; user-select: none; touch-action: none; }
  #pet .sprite { background-repeat: no-repeat; image-rendering: pixelated; }
  #bubble { position: absolute; left: 50%; bottom: calc(100% + 10px); transform: translateX(-50%);
            background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
            padding: 6px 12px; font-size: 13px; white-space: pre; text-align: center;
            max-width: 340px; box-shadow: 0 6px 24px rgba(0,0,0,.45); }
  #panel { position: absolute; left: 50%; bottom: calc(100% + 46px); transform: translateX(-50%);
           background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
           padding: 10px 12px; font-size: 13px; min-width: 210px; display: none;
           box-shadow: 0 6px 24px rgba(0,0,0,.45); }
  #pet:hover #panel { display: block; }
  #panel .row { display: flex; justify-content: space-between; gap: 14px; margin: 2px 0; color: #c8c3d8; }
  #panel .btns { display: flex; gap: 8px; margin-top: 8px; }
  #panel button, #summon button { background: #4a3f78; color: #fff; border: 0; border-radius: 8px;
                                  padding: 5px 12px; cursor: pointer; font-size: 13px; }
  #panel button:hover, #summon button:hover { background: #5d4f95; }
  #summon { position: fixed; right: 40px; bottom: 40px; z-index: 2147483000; }
  #summon button { padding: 8px 16px; font-size: 14px; box-shadow: 0 6px 24px rgba(0,0,0,.5); }
  #toast { position: fixed; left: 50%; top: 24px; transform: translateX(-50%);
           background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
           padding: 8px 16px; font-size: 13px; opacity: 0; transition: opacity .25s; z-index: 6; }
  .hidden { display: none !important; }
</style>
</head>
<body>
  <div id="hint">f 喂食 · p 抚摸 · s 睡觉/唤醒 · h 隐藏 · q 关闭页面</div>
  <div id="status-line">…</div>
  <div id="toast"></div>
  <div id="summon" class="hidden"><button>召唤宠物</button></div>
<script>
"use strict";
const api = "";
let manifest = null;
let state = null;
let feedback = null;

/* ---------- fetch helpers ---------- */
async function getJSON(url) {
  const r = await fetch(api + url, { cache: "no-store" });
  if (!r.ok) throw new Error(url + " -> " + r.status);
  return r.json();
}
async function postJSON(url, body) {
  const r = await fetch(api + url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return r.json();
}
function toast(text) {
  const el = document.getElementById("toast");
  el.textContent = text;
  el.style.opacity = "1";
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.style.opacity = "0"), 1800);
}

/* ---------- pet sprite ---------- */
const pet = document.createElement("div");
pet.id = "pet";
pet.innerHTML = '<div class="sprite"></div><div id="bubble" class="hidden"></div><div id="panel" class="hidden"></div>';
document.body.appendChild(pet);
const sprite = pet.querySelector(".sprite");
const bubble = pet.querySelector("#bubble");
const panel = pet.querySelector("#panel");
const summon = document.getElementById("summon");

let anim = null; // { clip, frame, last, elapsed, raf }

function startClip(clip, frame) {
  if (anim && anim.raf) cancelAnimationFrame(anim.raf);
  anim = { clip, frame: frame || 0, last: performance.now(), elapsed: 0, raf: 0 };
  drawFrame();
  anim.raf = requestAnimationFrame(loop);
}

function drawFrame() {
  if (!anim || !manifest) return;
  const c = manifest.clips[anim.clip];
  if (!c) return;
  const cell = manifest.cell;
  const scale = manifest.displayScale;
  const per = cell.width * scale;
  sprite.style.width = per + "px";
  sprite.style.height = (cell.height * scale) + "px";
  sprite.style.backgroundImage = "url(" + api + "/sheet/" + anim.clip + ".png)";
  sprite.style.backgroundSize = (per * c.frames) + "px " + (cell.height * scale) + "px";
  sprite.style.backgroundPosition = (-anim.frame * per) + "px 0";
}

function loop(ts) {
  if (!anim) return;
  const c = manifest.clips[anim.clip];
  if (!c) return;
  const d = (c.durations[anim.frame] || 120);
  anim.elapsed += ts - anim.last;
  anim.last = ts;
  const max = c.frames - 1;
  while (anim.elapsed >= d && anim.frame < max) {
    anim.elapsed -= d;
    anim.frame += 1;
  }
  if (anim.elapsed >= d) {
    if (c.loop) { anim.elapsed = 0; anim.frame = 0; }
    else anim.frame = max;
  }
  drawFrame();
  anim.raf = requestAnimationFrame(loop);
}

function stopAnimation() {
  if (anim && anim.raf) cancelAnimationFrame(anim.raf);
  anim = null;
}

/* ---------- state ---------- */
let wasVisible = true;
function applyState(s) {
  state = s;
  if (s.visible) {
    summon.classList.add("hidden");
    pet.classList.remove("hidden");
    if (!wasVisible || !anim || anim.clip !== s.clip) startClip(s.clip, s.frame);
    wasVisible = true;
  } else {
    pet.classList.add("hidden");
    summon.classList.remove("hidden");
    stopAnimation();
    wasVisible = false;
  }
  const text = feedback || (s.bubble && s.bubble.length ? s.bubble.join("\n") : "");
  if (text) { bubble.textContent = text; bubble.classList.remove("hidden"); }
  else bubble.classList.add("hidden");
  const line = (s.displayName || "") + (s.sleeping ? " · 睡觉中" : " · 状态: " + (s.status_source || "?")) + " · " + (s.behaviour || "");
  document.getElementById("status-line").textContent = line;
}

async function poll() {
  try { applyState(await getJSON("/api/state")); }
  catch (_) { /* server restarting */ }
}
setInterval(poll, 500);

/* ---------- interactions ---------- */
async function doInteract(kind) {
  const r = await postJSON("/api/interact", { kind });
  if (r.text) { feedback = r.text; toast(r.text); setTimeout(() => { feedback = null; }, 1800); }
}
async function doSleep() {
  const r = await postJSON("/api/sleep", {});
  toast(r.sleeping ? "睡觉了 💤" : "醒啦！");
}
async function doHide() {
  await postJSON("/api/hide", {});
}

sprite.addEventListener("click", async () => {
  if (dragging) { dragging = false; return; }
  await doInteract("pet");
});
summon.querySelector("button").addEventListener("click", () => postJSON("/api/summon", {}));

/* drag */
let dragging = false;
let drag = null;
pet.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  dragging = false;
  drag = { x: e.clientX, y: e.clientY,
           right: parseFloat(pet.style.right || "40"), bottom: parseFloat(pet.style.bottom || "40") };
  pet.setPointerCapture && pet.setPointerCapture(e.pointerId);
});
pet.addEventListener("pointermove", (e) => {
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) dragging = true;
  const right = Math.max(0, Math.min(window.innerWidth - 60, drag.right - dx));
  const bottom = Math.max(0, Math.min(window.innerHeight - 60, drag.bottom - dy));
  pet.style.right = right + "px";
  pet.style.bottom = bottom + "px";
  try { localStorage.setItem("dsh-pet-lulu-pos", JSON.stringify({ right, bottom })); } catch (_) {}
});
pet.addEventListener("pointerup", () => { drag = null; });

/* keyboard */
document.addEventListener("keydown", async (e) => {
  if (e.isComposing) return;
  const k = e.key.toLowerCase();
  if (k === "f") await doInteract("feed");
  else if (k === "p") await doInteract("pet");
  else if (k === "s") await doSleep();
  else if (k === "h") await doHide();
  else if (k === "q") await postJSON("/api/quit", {});
});

/* boot */
(async () => {
  try {
    manifest = await getJSON("/api/manifest");
    document.title = manifest.displayName + " · dsh-pet-lulu";
    document.getElementById("status-line").textContent = manifest.displayName + " · 加载中…";
    try {
      const pos = JSON.parse(localStorage.getItem("dsh-pet-lulu-pos") || "null");
      if (pos && typeof pos.right === "number") {
        pet.style.right = pos.right + "px";
        pet.style.bottom = pos.bottom + "px";
      }
    } catch (_) {}
    panel.innerHTML =
      '<div class="row"><span class="pname"></span><span class="prank"></span></div>' +
      '<div class="row"><span class="ptreats"></span><span class="ppoints"></span></div>' +
      '<div class="btns">' +
      '<button data-act="feed">喂食</button>' +
      '<button data-act="sleep">睡觉</button>' +
      '<button data-act="hide">隐藏</button>' +
      '</div>';
    panel.querySelectorAll("[data-act]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const act = btn.dataset.act;
        if (act === "feed") await doInteract("feed");
        else if (act === "sleep") await doSleep();
        else if (act === "hide") await doHide();
      });
    });
    panel.classList.remove("hidden");
    await poll();
  } catch (err) {
    document.getElementById("status-line").textContent = "加载失败: " + err.message;
  }
})();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #

class _PetHandler(BaseHTTPRequestHandler):
    """Serves the pet page and its JSON/image API."""

    server_version = "dsh-pet-lulu/0.1.1"

    # injected by WebRenderer on the per-renderer subclass
    renderer: "WebRenderer" = None  # type: ignore

    def log_message(self, fmt, *args):  # keep the console quiet
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, code: int, data) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    # ------------------------------------------------------------------ #

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/":
            return self._send(200, self.renderer.html.encode("utf-8"), "text/html; charset=utf-8")
        if path == "/api/manifest":
            return self._json(200, self.renderer.manifest())
        if path == "/api/state":
            return self._json(200, self.renderer.state_snapshot())
        if path.startswith("/api/sheet/") and path.endswith(".png"):
            clip = path[len("/api/sheet/"):-len(".png")]
            try:
                return self._send(200, self.renderer.sheet(clip), "image/png")
            except KeyError:
                return self._send(404, b"no such clip", "text/plain")
        return self._send(404, b"not found", "text/plain")

    def do_POST(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            body = {}
        if path == "/api/interact":
            return self._json(200, self.renderer.interact(body.get("kind", "pet")))
        if path == "/api/sleep":
            return self._json(200, self.renderer.toggle_sleep())
        if path == "/api/random":
            return self._json(200, self.renderer.random_action())
        if path == "/api/hide":
            return self._json(200, self.renderer.set_visible(False))
        if path == "/api/summon":
            return self._json(200, self.renderer.set_visible(True))
        if path == "/api/quit":
            self._json(200, {"ok": True})
            threading.Timer(0.2, self.renderer.stop).start()
            return
        return self._send(404, b"not found", "text/plain")


# --------------------------------------------------------------------------- #
# renderer
# --------------------------------------------------------------------------- #

class WebRenderer:
    """Runs the pet's state machine and serves it to a browser page."""

    def __init__(self, core: PetCore, port: int = DEFAULT_PORT,
                 host: str = "127.0.0.1", open_browser: bool = True,
                 title: Optional[str] = None) -> None:
        self.core = core
        self.host = host
        self.port = port
        self.open_browser = open_browser
        self.title = title or f"{core.pack.display_name} · dsh-pet-lulu"
        self._visible = True
        self._stop_event = threading.Event()
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._tick_thread: Optional[threading.Thread] = None
        self._server_thread: Optional[threading.Thread] = None
        self._sheet_cache: Dict[str, bytes] = {}
        self.html = _HTML.replace("__TITLE__", _escape_html(self.title))

    # ------------------------------------------------------------------ #

    @property
    def url(self) -> str:
        port = self._httpd.server_address[1] if self._httpd else self.port
        return f"http://{self.host}:{port}/"

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Bind the server and start the state thread (non-blocking)."""
        handler = type("Handler", (_PetHandler,), {"renderer": self})
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self._server_thread = threading.Thread(target=self._httpd.serve_forever,
                                               name="dsh-pet-web-http", daemon=True)
        self._server_thread.start()
        self._tick_thread = threading.Thread(target=self._tick_loop,
                                             name="dsh-pet-web-tick", daemon=True)
        self._tick_thread.start()
        if self.open_browser:
            try:
                webbrowser.open(self.url)
            except Exception:  # noqa: BLE001 - headless environments
                pass

    def run(self) -> None:
        """Start and block until :meth:`stop` (e.g. the page's quit button)."""
        self.start()
        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(0.2)
        finally:
            self.stop()

    def stop(self) -> None:
        self._stop_event.set()
        if self._httpd is not None:
            threading.Thread(target=self._httpd.shutdown, daemon=True).start()
            self._httpd.server_close()
        if self._tick_thread is not None and self._tick_thread.is_alive():
            self._tick_thread.join(timeout=1.0)
        if self._server_thread is not None and self._server_thread.is_alive():
            self._server_thread.join(timeout=1.0)

    def _tick_loop(self) -> None:
        period = self.core.period
        while not self._stop_event.is_set():
            started = time.monotonic()
            self.core.tick(period)
            delay = period - (time.monotonic() - started)
            if delay > 0:
                self._stop_event.wait(delay)

    # ------------------------------------------------------------------ #
    # api
    # ------------------------------------------------------------------ #

    def manifest(self) -> dict:
        ms = max(40, round(1000.0 / self.core.fps))
        clips = {}
        for name, clip in self.core.pack.clips.items():
            n = len(clip.frames)
            if n == 0:
                continue
            clips[name] = {
                "frames": n,
                "loop": bool(clip.loop),
                "durations": [ms] * n,
            }
        cell = (sprite_mod.CELL_W, sprite_mod.CELL_H)
        first = next(iter(self.core.pack.clips.values()), None)
        if first is not None and first.frames:
            cell = _frame_size(first.frames[0])
        return {
            "displayName": self.core.pack.display_name,
            "petType": getattr(self.core.pack, "pet_type", "ascii"),
            "cell": {"width": cell[0], "height": cell[1]},
            "displayScale": 1.6,
            "clips": clips,
            "behaviours": self.core.pack.behaviours,
            "fps": self.core.fps,
        }

    def state_snapshot(self) -> dict:
        behaviour, frame = self.core.current_frame()
        clip = self.core.pack.behaviours.get(behaviour, "idle")
        return {
            "visible": self._visible,
            "behaviour": behaviour,
            "clip": clip,
            "frame": int(frame),
            "sleeping": self.core.is_sleeping(),
            "bubble": self.core.bubble_lines(),
            "displayName": self.core.pack.display_name,
            "status_source": self.core.status_source.name,
        }

    def sheet(self, clip: str) -> bytes:
        if clip not in self._sheet_cache:
            c = self.core.pack.clips.get(clip)
            if c is None or not c.frames:
                raise KeyError(clip)
            self._sheet_cache[clip] = build_clip_sheet(c.frames)
        return self._sheet_cache[clip]

    # ------------------------------------------------------------------ #
    # interactions
    # ------------------------------------------------------------------ #

    def interact(self, kind: str) -> dict:
        event = {"pet": "pet", "feed": "feed"}.get(kind)
        text_key = {"pet": "pet", "feed": "eat"}.get(kind)
        if event is None:
            return {"ok": False, "text": "未知操作"}
        self.core.post_event(event)
        self.core.drain_events()  # apply immediately so the next poll sees it
        return {"ok": True, "text": REACTION_TEXT.get(text_key or "", "")}

    def toggle_sleep(self) -> dict:
        self.core.post_event(EVENT_SLEEP)
        self.core.drain_events()
        return {"ok": True, "sleeping": self.core.is_sleeping()}

    def random_action(self) -> dict:
        self.core.post_event("random")
        self.core.drain_events()
        return {"ok": True}

    def set_visible(self, visible: bool) -> dict:
        self._visible = bool(visible)
        return {"ok": True, "visible": self._visible}
