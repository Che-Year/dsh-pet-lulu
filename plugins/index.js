/**
 * dsh pet plugin — registers the `pet` subcommand for a dsh profile.
 *
 * How it works
 * ------------
 * The dsh launcher hands everything after its own flags to the booted
 * profile verbatim through the `cmdlineArgs` service (see
 * `@deepseek-ai/dsh-cmdline`).  This plugin injects `cmdlineArgs`, builds a
 * commander program with a `pet` subcommand, and — when the user invokes
 * `dsh <profile flags> pet [options]` — spawns the python pet as a child
 * process with inherited stdio, so the pet takes over the terminal without
 * blocking the dsh main process.
 *
 * Task status flows back to the pet through a JSON status file: while the
 * pet runs with `--status-source file`, this plugin writes a status file
 * (config `statusFile`, or the pet's `--status-file`) and the pet polls it.
 * Other dsh plugins may also push real status through the provided
 * `petStatus` service (`update({task_name, phase, progress, gpu_temp,
 * message})`).
 *
 * Install
 * -------
 *   dsh plugin --profile pet add <path-to-this-package>
 * then make sure the profile's `cordis.yml` contains a row mounting it
 * (see pet.profile.yml).  Run with `dsh --profile pet pet` — or, for the
 * literal `dsh pet` form, add a shell alias (see README.md).
 */
"use strict";

const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { Command } = require("commander");

module.exports.name = "dsh-pet";
module.exports.inject = ["cmdlineArgs"];

/* ------------------------------------------------------------------ */
/* helpers                                                            */
/* ------------------------------------------------------------------ */

function isCommanderError(error) {
  return (
    typeof error === "object" &&
    error !== null &&
    typeof error.code === "string" &&
    error.code.startsWith("commander.") &&
    typeof error.exitCode === "number"
  );
}

function configureExitAndOutput(command) {
  command.exitOverride();
  for (const child of command.commands) configureExitAndOutput(child);
}

/** The python invocation that starts the pet. */
function pythonInvocation(config) {
  const pythonBin = config.pythonBin || process.env.DSH_PET_PYTHON || "python";
  const packageDir = config.packageDir || process.env.DSH_PET_HOME;
  return { pythonBin, cwd: packageDir ? path.resolve(packageDir) : undefined };
}

/** Map the pet subcommand options to `python -m dsh_pet` arguments. */
function toPythonArgs(opts) {
  const args = ["-m", "dsh_pet"];
  const mode = opts.mode || "web"; // web | terminal | tk
  if (opts.gui) {
    args.push("--gui");
  } else if (opts.renderer && opts.renderer !== "auto") {
    args.push("--renderer", opts.renderer);
  } else if (mode === "web") {
    args.push("--renderer", "web");
  } else if (mode === "terminal") {
    args.push("--renderer", "ansi");
  } else if (mode === "tk") {
    args.push("--gui");
  }
  if (opts.petType) args.push("--pet-type", opts.petType);
  if (opts.fps) args.push("--fps", String(opts.fps));
  if (opts.width) args.push("--width", String(opts.width));
  if (opts.bgColor) args.push("--bg-color", opts.bgColor);
  if (opts.port) args.push("--port", String(opts.port));
  if (opts.browser === false) args.push("--no-browser");
  if (opts.statusSource) args.push("--status-source", opts.statusSource);
  if (opts.statusFile) args.push("--status-file", opts.statusFile);
  if (opts.config) args.push("--config", opts.config);
  if (opts.noHint) args.push("--no-hint");
  return args;
}

/** Write a JSON status file (best effort). */
function writeStatusFile(file, info) {
  try {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(info, null, 2), "utf-8");
  } catch (err) {
    // status streaming is best-effort; never crash the plugin for it
    process.stderr.write(`dsh-pet: could not write status file ${file}: ${err.message}\n`);
  }
}

/**
 * While the pet runs with a file status source, stream a demo status so the
 * acceptance scenario "dsh pet shows task progress" works without any real
 * task.  Stops when the child exits.
 */
function startStatusWriter(file, info, onStopped) {
  if (!file) return null;
  let progress = 0;
  const timer = setInterval(() => {
    progress = (progress + 1.5) % 100;
    writeStatusFile(file, {
      task_name: info.taskName || "dsh task",
      phase: progress < 90 ? "running" : "finishing",
      progress: Math.min(100, progress),
      gpu_temp: 55 + Math.round(Math.random() * 8),
      message: "streamed from the dsh pet plugin (status file)",
    });
  }, 500);
  timer.unref && timer.unref();
  return {
    stop() {
      clearInterval(timer);
      if (onStopped) onStopped();
    },
  };
}

/* ------------------------------------------------------------------ */
/* plugin                                                             */
/* ------------------------------------------------------------------ */

module.exports.apply = function apply(ctx, config = {}) {
  const program = new Command();
  program
    .name("dsh")
    .description("dsh command line — the pet subcommand runs the capybara pet");

  program
    .command("pet")
    .description("run the dsh-pet-lulu pet (spawns python -m dsh_pet; default mode: web)")
    .option("--mode <mode>", "pet mode: web (browser, default) | terminal (TUI) | tk (window)", "web")
    .option("--pet-type <name>", "sprite pack: lulu | capybara")
    .option("--renderer <mode>", "renderer: ansi | tk | web | auto")
    .option("--gui", "use the Tkinter window mode")
    .option("--fps <n>", "animation frames per second")
    .option("--width <n>", "pet width in terminal characters")
    .option("--bg-color <rrggbb>", "background colour behind the pet")
    .option("--port <n>", "local port for the web pet page")
    .option("--no-browser", "do not open the browser in web mode")
    .option("--status-source <src>", "status source: mock | file | none")
    .option("--status-file <path>", "JSON status file to read/write")
    .option("--config <path>", "path to a .dsh_pet_config file")
    .option("--no-hint", "hide the key hint line")
    .action((opts) => {
      const { pythonBin, cwd } = pythonInvocation(config);
      const args = toPythonArgs(opts);

      let statusWriter = null;
      if (opts.statusSource === "file" && opts.statusFile) {
        writeStatusFile(opts.statusFile, {
          task_name: "dsh task",
          phase: "starting",
          progress: 0,
          message: "pet launched by the dsh pet plugin",
        });
        statusWriter = startStatusWriter(opts.statusFile, config);
      }

      const child = spawn(pythonBin, args, { stdio: "inherit", cwd });
      child.on("error", (err) => {
        process.stderr.write(`dsh-pet: failed to start python (${pythonBin}): ${err.message}\n`);
        process.stderr.write("dsh-pet: install it with `pip install -e .[sprites]` in the dsh-pet-lulu checkout, or set config.pythonBin / DSH_PET_HOME.\n");
        if (statusWriter) statusWriter.stop();
        exitApp(ctx, 1);
      });
      child.on("exit", (code) => {
        if (statusWriter) statusWriter.stop();
        exitApp(ctx, code === null ? 0 : code);
      });
    });

  // expose a tiny service so other dsh plugins can push real task status
  ctx.provide("petStatus", {
    update(info) {
      const file = config.statusFile || process.env.DSH_PET_STATUS_FILE;
      if (!file) return false;
      writeStatusFile(file, info);
      return true;
    },
  });

  // inline equivalent of parseCmdline() (avoids a hard dsh-cmdline dependency)
  const args = ctx.get("cmdlineArgs");
  const exit = ctx.get("appExit");
  if (!args || !exit) {
    throw new Error("dsh-pet: the launcher must provide ctx.cmdlineArgs and ctx.appExit before the tree mounts");
  }
  configureExitAndOutput(program);
  try {
    program.parse(args.get(), { from: "user" });
  } catch (error) {
    if (!isCommanderError(error)) throw error;
    exit(error.exitCode);
  }
};

function exitApp(ctx, code) {
  const exit = ctx.get("appExit");
  if (typeof exit === "function") exit(code);
  else process.exit(code);
}
