// Renders brand/svg/*.svg to PNG exports with Chromium (Playwright). Run from frontend/: node ../brand/tools/render.mjs
import { createRequire } from "node:module";
const { chromium } = createRequire(process.cwd() + "/package.json")("playwright");
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const svgDir = path.join(root, "svg");
const pngDir = path.join(root, "png");
fs.mkdirSync(pngDir, { recursive: true });
const jobs = [
  ["wesal-logo-primary.svg", "wesal-logo-primary", [1, 2, 4]],
  ["wesal-logo-primary-tagline.svg", "wesal-logo-primary-tagline", [1, 2]],
  ["wesal-logo-ar.svg", "wesal-logo-ar", [1, 2]],
  ["wesal-logo-en.svg", "wesal-logo-en", [1, 2]],
  ["wesal-logo-mono.svg", "wesal-logo-mono", [2]],
  ["wesal-logo-mono-white.svg", "wesal-logo-mono-white", [2]],
  ["wesal-logo-on-dark.svg", "wesal-logo-on-dark", [2]],
  ["wesal-logo-on-light.svg", "wesal-logo-on-light", [2]],
  ["wesal-og-image.svg", "og-image", [1]],
  ["wesal-splash.svg", "splash-1242x2688", [1]],
];
const icons = [16, 32, 48, 64, 128, 180, 192, 256, 512, 1024];
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || "/opt/pw-browsers/chromium" }).catch(() => chromium.launch());
async function render(file, out, scale, size) {
  const svg = fs.readFileSync(path.join(svgDir, file), "utf8");
  const m = svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  const w = size || Math.round(+m[1]), h = size || Math.round(+m[2]);
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: scale });
  await page.setContent(`<html><body style="margin:0;background:transparent">${svg.replace(/width="[\d.]+" height="[\d.]+"/, `width="${w}" height="${h}"`)}</body></html>`);
  await page.screenshot({ path: path.join(pngDir, out), omitBackground: true, clip: { x: 0, y: 0, width: w, height: h } });
  await page.close();
}
for (const [file, base, scales] of jobs) for (const s of scales) await render(file, `${base}${scales.length > 1 || s !== 1 ? `@${s}x` : ""}.png`, s);
for (const s of icons) await render("wesal-app-icon.svg", `app-icon-${s}.png`, 1, s);
for (const s of [16, 32, 48]) await render("wesal-favicon.svg", `favicon-${s}.png`, 1, s);
await browser.close();
console.log(fs.readdirSync(pngDir).join("\n"));
