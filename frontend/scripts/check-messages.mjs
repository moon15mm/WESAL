#!/usr/bin/env node
/* Verifies UI translations:
   1. every locale has exactly the same keys as en.json (no missing / extra keys)
   2. every static key used in code (t("..."), t.rich("..."), t.has excluded) exists in en.json
   3. dynamic keys (template literals) are listed for manual review with --verbose
   Exit code 1 on any problem. */
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const LOCALES = ["ar", "en", "ur", "hi"];
const verbose = process.argv.includes("--verbose");
const flatten = (o, p = "") => Object.entries(o).flatMap(([k, v]) => (v && typeof v === "object" ? flatten(v, `${p}${k}.`) : [[`${p}${k}`, v]]));
const msgs = Object.fromEntries(LOCALES.map((l) => [l, new Map(flatten(JSON.parse(fs.readFileSync(path.join(ROOT, "messages", `${l}.json`), "utf8"))))]));
let problems = 0;

const ref = msgs.en;
for (const l of LOCALES) {
  const missing = [...ref.keys()].filter((k) => !msgs[l].has(k));
  const extra = [...msgs[l].keys()].filter((k) => !ref.has(k));
  const empty = [...msgs[l].entries()].filter(([, v]) => typeof v === "string" && !v.trim()).map(([k]) => k);
  if (missing.length || extra.length || empty.length) {
    problems++;
    console.log(`✗ ${l}: ${missing.length} missing, ${extra.length} extra, ${empty.length} empty`);
    for (const k of [...missing, ...extra, ...empty].slice(0, 40)) console.log("   ", k);
  } else console.log(`✓ ${l}: ${msgs[l].size} keys`);
}

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(dir, e.name)) : /\.(tsx?|mjs)$/.test(e.name) ? [path.join(dir, e.name)] : []));
}
const used = new Set();
const dynamic = new Set();
for (const file of walk(path.join(ROOT, "src"))) {
  const src = fs.readFileSync(file, "utf8");
  const vars = {};
  for (const m of src.matchAll(/const\s+(\w+)\s*=\s*(?:await\s+)?(?:useTranslations|getTranslations)\(\s*(?:\{[^}]*namespace:\s*)?["']([\w.]+)["']/g)) vars[m[1]] = m[2];
  for (const [v, ns] of Object.entries(vars)) {
    for (const m of src.matchAll(new RegExp(`\\b${v}(?:\\.rich)?\\(\\s*"([\\w.]+)"`, "g"))) used.add(`${ns}.${m[1]}`);
    for (const m of src.matchAll(new RegExp(`\\b${v}(?:\\.rich)?\\(\\s*\`([^\`]+)\``, "g"))) dynamic.add(`${ns}.${m[1]}`);
  }
}
const absent = [...used].filter((k) => !ref.has(k)).sort();
if (absent.length) {
  problems++;
  console.log(`✗ ${absent.length} keys used in code but missing in en.json:`);
  for (const k of absent) console.log("   ", k);
} else console.log(`✓ ${used.size} static keys used in code are defined`);
// dynamic keys: check that the namespace prefix exists
const unresolved = [...dynamic].filter((d) => {
  const prefix = d.split("${")[0];
  return ![...ref.keys()].some((k) => k.startsWith(prefix));
});
if (unresolved.length) {
  problems++;
  console.log(`✗ dynamic key prefixes without any translation:`);
  for (const k of unresolved) console.log("   ", k);
}
if (verbose) for (const d of [...dynamic].sort()) console.log("  dyn:", d);
process.exit(problems ? 1 : 0);
