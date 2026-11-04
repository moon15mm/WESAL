import { expect, test } from "@playwright/test";
import { login, USERS } from "./helpers";

test("anonymous visitor is sent to login", async ({ page }) => {
  await page.goto("/ar/app/store/orders");
  await page.waitForURL(/\/ar\/login/);
});

test("a store cannot open the supplier workspace or admin pages", async ({ page }) => {
  await login(page, USERS.store);
  for (const path of ["/api/v1/supplier/orders", "/api/v1/admin/overview"]) {
    const r = await page.request.get(path, { headers: { "x-locale": "en" } });
    expect([403, 404]).toContain(r.status());
  }
});

test("state-changing API calls without the CSRF header are rejected", async ({ page }) => {
  await login(page, USERS.store);
  const r = await page.request.post("/api/v1/retailer/carts/00000000-0000-0000-0000-000000000000/checkout", { data: {} });
  expect(r.status()).toBe(403);
});

test("wrong password shows an error and does not sign in", async ({ page }) => {
  await page.goto("/en/login");
  await page.fill("input[name=identifier]", USERS.store);
  await page.fill("input[name=password]", "wrong-password-1A!");
  await page.getByTestId("login-form").locator("button[type=submit]").click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page).toHaveURL(/\/en\/login/);
});
