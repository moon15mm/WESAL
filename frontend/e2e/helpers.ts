import fs from "node:fs";
import path from "node:path";
import { expect, type Page } from "@playwright/test";

export const PASSWORD = process.env.DEMO_PASSWORD || "Wesal-Demo-2026";
export const USERS = {
  store: "demo.store.rayyan@example.com",
  storeHay: "demo.store.hay@example.com",
  supplier: "demo.supplier.nokhba@example.com",
  rep: "demo.rep.riyadh@example.com",
  admin: "demo.admin@example.com",
};

const AUTH_DIR = path.join(__dirname, ".auth");

/** Signs in through the UI once per user and reuses the session cookie afterwards
 *  (the API rate-limits repeated sign-ins of one account, as it should). */
export async function login(page: Page, email: string, locale = "ar") {
  const file = path.join(AUTH_DIR, `${email}.json`);
  if (fs.existsSync(file)) {
    const state = JSON.parse(fs.readFileSync(file, "utf8"));
    await page.context().addCookies(state.cookies);
    await page.goto(`/${locale}/app`);
    if (!/\/login/.test(page.url())) {
      await page.waitForURL(/\/app(\/|$)/);
      if (!/\/login/.test(page.url())) return;
    }
  }
  await uiLogin(page, email, locale);
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  await page.context().storageState({ path: file });
}

export async function uiLogin(page: Page, email: string, locale = "ar") {
  await page.goto(`/${locale}/login`);
  await page.fill("input[name=identifier]", email);
  await page.fill("input[name=password]", PASSWORD);
  await page.getByTestId("login-form").locator("button[type=submit]").click();
  await page.waitForURL(/\/app(\/|$)/);
}

/** Fails on uncaught page errors and on any 5xx from the API. */
export function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 500) errors.push(`${r.status()} ${r.url()}`); });
  return () => expect(errors, errors.join("\n")).toEqual([]);
}

/** No untranslated message keys (e.g. "orders.status.new") visible on the page. */
export async function expectNoRawKeys(page: Page) {
  const text = await page.locator("main, body").first().innerText();
  const raw = (text.match(/\b[a-z]+(?:_[a-z]+)*\.[a-z_]+(?:\.[a-z_]+)*\b/g) || []).filter((s) => !/@|example\.com|\.(png|pdf|csv|com|sa)$/.test(s));
  expect(raw, raw.join(", ")).toEqual([]);
}
