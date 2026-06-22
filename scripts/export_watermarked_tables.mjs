#!/usr/bin/env node

import { createServer } from "node:http";
import { access, mkdir, readFile, readdir, stat } from "node:fs/promises";
import { createRequire } from "node:module";
import { homedir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const PAGE_NAMES = ["lump-sum", "dca", "difference"];
const MIME_TYPES = new Map([
  [".css", "text/css; charset=utf-8"], [".csv", "text/csv; charset=utf-8"],
  [".html", "text/html; charset=utf-8"], [".jpg", "image/jpeg"],
  [".js", "text/javascript; charset=utf-8"], [".png", "image/png"], [".svg", "image/svg+xml"],
]);

function usage() {
  return `Usage: node scripts/export_watermarked_tables.mjs [options]

  --site-dir PATH           Static site root (default: docs)
  --output-dir PATH         Image directory (default: <site-dir>/downloads/wechat)
  --assets LIST             Comma-separated asset folders or all (default: all)
  --pages LIST              lump-sum,dca,difference or a subset
  --query STRING            Query enabling poster mode (default: poster=1)
  --watermark TEXT          Required watermark text (default: 炼金魔女手记)
  --format jpg|png          Output format (default: jpg)
  --quality 1-100           JPEG quality (default: 92)
  --browser chrome|chromium Browser channel (default: chrome)
  --help                    Show this help
`;
}

function parseArgs(argv) {
  const values = new Map();
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--help") return { help: true };
    if (!token.startsWith("--") || index + 1 >= argv.length) throw new Error(`Invalid argument: ${token}`);
    values.set(token.slice(2), argv[index + 1]);
    index += 1;
  }
  const siteDir = path.resolve(values.get("site-dir") ?? "docs");
  const format = (values.get("format") ?? "jpg").toLowerCase();
  const quality = Number(values.get("quality") ?? "92");
  const browser = values.get("browser") ?? "chrome";
  if (!["jpg", "png"].includes(format)) throw new Error("--format must be jpg or png");
  if (!Number.isInteger(quality) || quality < 1 || quality > 100) throw new Error("--quality must be 1-100");
  if (!["chrome", "chromium"].includes(browser)) throw new Error("--browser must be chrome or chromium");
  const list = (name, fallback) => (values.get(name) ?? fallback).split(",").map((item) => item.trim()).filter(Boolean);
  const pages = list("pages", PAGE_NAMES.join(","));
  const invalidPages = pages.filter((name) => !PAGE_NAMES.includes(name));
  if (invalidPages.length) throw new Error(`Unknown pages: ${invalidPages.join(", ")}`);
  return {
    help: false, siteDir,
    outputDir: path.resolve(values.get("output-dir") ?? path.join(siteDir, "downloads", "wechat")),
    assets: list("assets", "all"), pages,
    query: values.get("query") ?? "poster=1",
    watermark: values.get("watermark") ?? "炼金魔女手记",
    format, quality, browser,
  };
}

async function importPlaywright() {
  const require = createRequire(import.meta.url);
  const candidates = [
    process.env.PLAYWRIGHT_NODE_MODULES,
    path.join(homedir(), ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies", "node", "node_modules"),
  ].filter(Boolean);
  for (const searchPath of [path.dirname(new URL(import.meta.url).pathname), ...candidates]) {
    try {
      const resolved = require.resolve("playwright", { paths: [searchPath] });
      const module = await import(pathToFileURL(resolved).href);
      return module.default ?? module;
    } catch { /* Try the next known module location. */ }
  }
  throw new Error("Playwright not found. Run `npm install --save-dev playwright` or set PLAYWRIGHT_NODE_MODULES.");
}

async function discoverAssets(siteDir, requested, pages) {
  const root = path.join(siteDir, "assets");
  const entries = await readdir(root, { withFileTypes: true });
  const available = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort();
  const selected = requested.includes("all") ? available : requested;
  const unknown = selected.filter((asset) => !available.includes(asset));
  if (unknown.length) throw new Error(`Unknown asset folders: ${unknown.join(", ")}`);
  for (const asset of selected) {
    for (const pageName of pages) await access(path.join(root, asset, `${pageName}.html`));
  }
  return selected;
}

function startStaticServer(siteDir) {
  const server = createServer(async (request, response) => {
    try {
      const requestPath = decodeURIComponent(new URL(request.url ?? "/", "http://localhost").pathname);
      let filePath = path.resolve(siteDir, `.${requestPath}`);
      if (!filePath.startsWith(`${siteDir}${path.sep}`) && filePath !== siteDir) return response.writeHead(403).end("Forbidden");
      if ((await stat(filePath)).isDirectory()) filePath = path.join(filePath, "index.html");
      const body = await readFile(filePath);
      response.writeHead(200, { "content-type": MIME_TYPES.get(path.extname(filePath)) ?? "application/octet-stream" });
      response.end(body);
    } catch { response.writeHead(404).end("Not found"); }
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

async function launchBrowser(chromium, preferred) {
  if (preferred === "chrome") {
    try { return await chromium.launch({ channel: "chrome", headless: true }); }
    catch (error) { process.stderr.write(`Chrome unavailable; trying Chromium. ${error.message}\n`); }
  }
  return chromium.launch({ headless: true });
}

async function exportPage(page, url, outputPath, options) {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForSelector("body.poster");
  const watermark = page.locator(".watermark-layer");
  await watermark.waitFor({ state: "visible" });
  const text = (await watermark.textContent()) ?? "";
  if (options.watermark && !text.includes(options.watermark)) throw new Error(`Watermark text not found at ${url}`);
  const width = await page.evaluate(() => Math.ceil(Math.max(
    document.documentElement.scrollWidth, document.body.scrollWidth,
    document.querySelector("main")?.scrollWidth ?? 0,
  )));
  await page.setViewportSize({ width: Math.min(Math.max(width, 1280), 8000), height: 900 });
  await page.evaluate(() => document.fonts.ready);
  const screenshot = options.format === "png"
    ? { path: outputPath, type: "png", fullPage: true }
    : { path: outputPath, type: "jpeg", quality: options.quality, fullPage: true };
  await page.screenshot(screenshot);
  const info = await stat(outputPath);
  if (info.size < 10_000) throw new Error(`Screenshot appears incomplete: ${outputPath}`);
  return { width, bytes: info.size };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) return process.stdout.write(usage());
  const assets = await discoverAssets(options.siteDir, options.assets, options.pages);
  await mkdir(options.outputDir, { recursive: true });
  const { chromium } = await importPlaywright();
  const server = await startStaticServer(options.siteDir);
  const address = server.address();
  const browser = await launchBrowser(chromium, options.browser);
  const context = await browser.newContext({ deviceScaleFactor: 1 });
  const page = await context.newPage();
  let count = 0;
  try {
    for (const asset of assets) {
      for (const pageName of options.pages) {
        const extension = options.format === "png" ? "png" : "jpg";
        const outputPath = path.join(options.outputDir, `${asset}-${pageName}.${extension}`);
        const suffix = options.query ? `?${options.query}` : "";
        const url = `http://127.0.0.1:${address.port}/assets/${encodeURIComponent(asset)}/${pageName}.html${suffix}`;
        const result = await exportPage(page, url, outputPath, options);
        count += 1;
        process.stdout.write(`✓ ${path.relative(process.cwd(), outputPath)} (${result.width}px, ${Math.round(result.bytes / 1024)}KB)\n`);
      }
    }
  } finally {
    await context.close(); await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
  process.stdout.write(`Exported ${count} validated watermarked images.\n`);
}

main().catch((error) => { process.stderr.write(`Export failed: ${error.message}\n`); process.exitCode = 1; });
