#!/usr/bin/env node
/**
 * Zero-dependency CLI for https://aiym168.github.io
 * Usage: npx github:aiym168/aiym168.github.io <command>
 */
"use strict";

const BASE = process.env.AI168_API || "https://aiym168.github.io";
const args = process.argv.slice(2);

const c = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  dim: "\x1b[2m",
  cyan: "\x1b[36m",
  mag: "\x1b[35m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  gray: "\x1b[90m",
  white: "\x1b[37m",
};

function paint(s, ...cols) {
  if (process.env.NO_COLOR) return String(s);
  return cols.join("") + s + c.reset;
}

function usage() {
  console.log(`
${paint("ai168", c.bold, c.cyan)} — AI大模型免费资源导航 CLI

${paint("Commands", c.bold)}
  list [module]     List deals (or a module id)
  search <kw>       Search titles/summaries
  hot               Hot topics
  github            GitHub trending AI repos
  open <id>         Open item URL in browser
  json [endpoint]   Print raw JSON (default: meta)
  help              Show help

${paint("Options", c.bold)}
  --limit N         Max rows (default 20)
  --api URL         Override API base

${paint("Modules", c.dim)}
  damoxing-mianfei-api, ai-huiyuan-shiyong, ai-kaifa-gongju,
  mianfei-gpu-yunfuwu, keji-app-xianmian, github-hot, hot-topics

${paint("Examples", c.dim)}
  npx github:aiym168/aiym168.github.io list --limit 10
  npx github:aiym168/aiym168.github.io search 免费GPU
  curl -fsSL ${BASE}/cli.sh | bash -s -- list
`);
}

function parseArgs(argv) {
  const out = { cmd: "help", rest: [], limit: 20, api: BASE };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--limit") out.limit = Math.max(1, parseInt(argv[++i] || "20", 10) || 20);
    else if (a.startsWith("--limit=")) out.limit = Math.max(1, parseInt(a.split("=")[1], 10) || 20);
    else if (a === "--api") out.api = (argv[++i] || BASE).replace(/\/$/, "");
    else if (a === "--help" || a === "-h") out.cmd = "help";
    else rest.push(a);
  }
  if (rest[0]) out.cmd = rest[0];
  out.rest = rest.slice(1);
  return out;
}

async function getJson(api, path) {
  const url = `${api.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
  const res = await fetch(url, {
    headers: { "User-Agent": "ai168-cli/1.0", Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return res.json();
}

function trunc(s, n) {
  s = String(s || "").replace(/\s+/g, " ").trim();
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

function table(rows, cols) {
  const widths = cols.map((col, i) =>
    Math.min(col.max || 40, Math.max(col.name.length, ...rows.map((r) => String(r[i] || "").length)))
  );
  const line = (cells, color) =>
    cells
      .map((cell, i) => {
        const t = trunc(cell, widths[i]);
        return t + " ".repeat(Math.max(0, widths[i] - [...t].length));
      })
      .join("  ");
  console.log(paint(line(cols.map((c) => c.name)), c.bold, c.cyan));
  console.log(paint(widths.map((w) => "─".repeat(w)).join("──"), c.dim));
  for (const r of rows) {
    console.log(line(r));
  }
}

function openUrl(url) {
  if (!url) return console.error("No URL");
  const { spawn } = require("child_process");
  const plat = process.platform;
  if (plat === "darwin") spawn("open", [url], { stdio: "ignore", detached: true });
  else if (plat === "win32") spawn("cmd", ["/c", "start", "", url], { stdio: "ignore", detached: true });
  else spawn("xdg-open", [url], { stdio: "ignore", detached: true });
  console.log(paint("Opened ", c.dim) + url);
}

async function main() {
  const opt = parseArgs(args);
  if (!opt.cmd || opt.cmd === "help") return usage();

  try {
    if (opt.cmd === "json") {
      const ep = opt.rest[0] || "api/meta.json";
      const path = ep.includes("/") ? ep : `api/${ep}.json`;
      const data = await getJson(opt.api, path);
      console.log(JSON.stringify(data, null, 2));
      return;
    }

    if (opt.cmd === "meta") {
      const data = await getJson(opt.api, "api/meta.json");
      console.log(paint(data.name || "aiym168", c.bold, c.cyan));
      console.log(paint(`updated ${data.updated_at_label || "?"}  version ${data.version || "?"}`, c.dim));
      console.log(data.counts || {});
      return;
    }

    if (opt.cmd === "list") {
      const mod = opt.rest[0];
      let items = [];
      let title = "latest";
      if (mod) {
        const data = await getJson(opt.api, `api/${mod}.json`);
        items = data.items || [];
        title = data.title || mod;
      } else {
        const data = await getJson(opt.api, "api/latest.json");
        items = data.items || [];
      }
      items = items.slice(0, opt.limit);
      console.log(paint(`\n${title} `, c.bold, c.mag) + paint(`(${items.length})`, c.dim));
      table(
        items.map((it, i) => [
          String(i + 1),
          trunc(it.id || "", 16),
          trunc(it.title || it.name || "", 48),
          trunc(it.source || it.category || "", 14),
        ]),
        [
          { name: "#", max: 3 },
          { name: "ID", max: 16 },
          { name: "TITLE", max: 48 },
          { name: "SOURCE", max: 14 },
        ]
      );
      return;
    }

    if (opt.cmd === "search") {
      const kw = (opt.rest.join(" ") || "").trim().toLowerCase();
      if (!kw) {
        console.error("search requires a keyword");
        process.exitCode = 1;
        return;
      }
      const data = await getJson(opt.api, "api/latest.json");
      const items = (data.items || [])
        .filter((it) =>
          `${it.title || ""} ${it.summary || ""} ${it.how || ""} ${it.category || ""}`
            .toLowerCase()
            .includes(kw)
        )
        .slice(0, opt.limit);
      console.log(paint(`\nsearch "${kw}" `, c.bold, c.yellow) + paint(`(${items.length})`, c.dim));
      table(
        items.map((it, i) => [
          String(i + 1),
          trunc(it.id || "", 16),
          trunc(it.title || "", 52),
        ]),
        [
          { name: "#", max: 3 },
          { name: "ID", max: 16 },
          { name: "TITLE", max: 52 },
        ]
      );
      return;
    }

    if (opt.cmd === "hot" || opt.cmd === "github") {
      const path = opt.cmd === "hot" ? "api/hot.json" : "api/github-hot.json";
      const data = await getJson(opt.api, path);
      const items = (data.items || []).slice(0, opt.limit);
      console.log(paint(`\n${opt.cmd} `, c.bold, c.green) + paint(`(${items.length})`, c.dim));
      table(
        items.map((it, i) => [
          String(i + 1),
          trunc(it.id || "", 18),
          trunc(it.title || it.name || "", 50),
          trunc(it.heat || it.stars || it.source || "", 16),
        ]),
        [
          { name: "#", max: 3 },
          { name: "ID", max: 18 },
          { name: "TITLE", max: 50 },
          { name: "HEAT", max: 16 },
        ]
      );
      return;
    }

    if (opt.cmd === "open") {
      const id = opt.rest[0];
      if (!id) {
        console.error("open requires an id");
        process.exitCode = 1;
        return;
      }
      const latest = await getJson(opt.api, "api/latest.json");
      const hot = await getJson(opt.api, "api/hot.json");
      const gh = await getJson(opt.api, "api/github-hot.json");
      const all = [...(latest.items || []), ...(hot.items || []), ...(gh.items || [])];
      const hit = all.find((it) => String(it.id) === id || String(it.id).includes(id));
      if (!hit) {
        console.error("Not found:", id);
        process.exitCode = 1;
        return;
      }
      openUrl(hit.url || (hit.path ? `${opt.api}/${hit.path}` : null));
      return;
    }

    console.error("Unknown command:", opt.cmd);
    usage();
    process.exitCode = 1;
  } catch (e) {
    console.error(paint("Error: ", c.bold) + e.message);
    process.exitCode = 1;
  }
}

main();
