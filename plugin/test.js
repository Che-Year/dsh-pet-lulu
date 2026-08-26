/**
 * Plugin test — exercises command registration, arg mapping, status-file
 * streaming and exit-code propagation without a real dsh launcher.
 *
 * Run with:  node plugin/test.js
 * (requires plugin/node_modules/commander — see plugin/.gitignore)
 */
"use strict";

const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

/* ---- stub node:child_process so no real python is spawned ---------- */
const calls = [];
let spawnBehavior = null; // (bin, args, opts) -> child-like object, or default

const fakeChild = (bin, args, opts) => ({
  on(ev, cb) {
    if (ev === "exit") setImmediate(() => cb(0));
  },
});

const fakeSpawn = {
  spawn(bin, args, opts) {
    calls.push({ bin, args, opts });
    return spawnBehavior ? spawnBehavior(bin, args, opts) : fakeChild(bin, args, opts);
  },
};
const Module = require("node:module");
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === "node:child_process") return fakeSpawn;
  return origLoad.apply(this, arguments);
};

const plugin = require("./index.js");

/* ---- tiny fake ctx ------------------------------------------------- */
function makeCtx(args, config = {}) {
  const state = { exitCode: null, provided: {} };
  const ctx = {
    get(name) {
      if (name === "cmdlineArgs") return { get: () => Object.freeze([...args]) };
      if (name === "appExit") return (code) => { state.exitCode = code; };
      return undefined;
    },
    provide(name, value) { state.provided[name] = value; },
    config,
  };
  return { ctx, state };
}

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "dsh-pet-test-"));

function main() {
  // plugin metadata
  assert.strictEqual(plugin.name, "dsh-pet");
  assert.ok(plugin.inject.includes("cmdlineArgs"));

  // 1. `pet` registers and spawns python -m dsh_pet (default mode: web)
  calls.length = 0;
  plugin.apply(makeCtx(["pet"]).ctx, {});
  assert.strictEqual(calls.length, 1, "exactly one spawn expected");
  assert.strictEqual(calls[0].bin, "python");
  assert.deepStrictEqual(calls[0].args, ["-m", "dsh_pet", "--renderer", "web"]);

  // 2. options are mapped onto the python CLI (deterministic order; --gui wins)
  calls.length = 0;
  plugin.apply(makeCtx(["pet", "--pet-type", "capybara", "--fps", "20", "--gui",
                        "--status-source", "file", "--status-file", "s.json"]).ctx, {});
  assert.deepStrictEqual(calls[0].args, [
    "-m", "dsh_pet",
    "--gui",
    "--pet-type", "capybara",
    "--fps", "20",
    "--status-source", "file",
    "--status-file", "s.json",
  ]);

  // 2b. mode selection maps to the renderer flags
  calls.length = 0;
  plugin.apply(makeCtx(["pet", "--mode", "terminal"]).ctx, {});
  assert.deepStrictEqual(calls[0].args, ["-m", "dsh_pet", "--renderer", "ansi"]);
  calls.length = 0;
  plugin.apply(makeCtx(["pet", "--mode", "tk"]).ctx, {});
  assert.deepStrictEqual(calls[0].args, ["-m", "dsh_pet", "--gui"]);
  calls.length = 0;
  plugin.apply(makeCtx(["pet", "--port", "9000", "--no-browser"]).ctx, {});
  assert.deepStrictEqual(calls[0].args,
    ["-m", "dsh_pet", "--renderer", "web", "--port", "9000", "--no-browser"]);

  // 3. config.pythonBin / packageDir are honoured
  calls.length = 0;
  plugin.apply(makeCtx(["pet"], { pythonBin: "python3", packageDir: "/tmp/pet" }).ctx,
               { pythonBin: "python3", packageDir: "/tmp/pet" });
  assert.strictEqual(calls[0].bin, "python3");
  assert.strictEqual(calls[0].opts.cwd, path.resolve("/tmp/pet"));

  // 4. petStatus service writes a status file (and is a no-op without one)
  const statusFile = path.join(tmpDir, "status.json");
  const { ctx: ctx4, state: state4 } = makeCtx(["pet"], { statusFile });
  plugin.apply(ctx4, { statusFile });
  const petStatus = state4.provided.petStatus;
  assert.ok(petStatus, "petStatus service must be provided");
  assert.strictEqual(petStatus.update({ task_name: "demo", progress: 12 }), true);
  const written = JSON.parse(fs.readFileSync(statusFile, "utf-8"));
  assert.strictEqual(written.task_name, "demo");
  assert.strictEqual(written.progress, 12);
  const { ctx: ctxNF, state: stNF } = makeCtx(["pet"]);
  plugin.apply(ctxNF, {});
  assert.strictEqual(stNF.provided.petStatus.update({}), false);

  // 5. child exit code is propagated via appExit
  spawnBehavior = () => ({
    on(ev, cb) { if (ev === "exit") setImmediate(() => cb(3)); },
  });
  const { state: state5 } = makeCtx(["pet"]);
  plugin.apply(makeCtx(["pet"]).ctx, {});
  setImmediate(() => {
    assert.strictEqual(makeCtx(["pet"]).state.exitCode, null); // untouched ctx
  });
  // run once more and capture the exit through the same instance's action
  const { ctx: ctx5, state: st5 } = makeCtx(["pet"]);
  plugin.apply(ctx5, {});
  setImmediate(() => {
    assert.strictEqual(st5.exitCode, 3);
    spawnBehavior = null;
    console.log("plugin tests OK");
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });
}

main();
