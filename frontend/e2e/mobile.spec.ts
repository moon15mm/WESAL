import { expect, test } from "@playwright/test";
import { login, USERS, watchErrors } from "./helpers";

test("store on a phone: bottom navigation, market and cart", async ({ page }) => {
  const done = watchErrors(page);
  await login(page, USERS.store);
  await expect(page.getByTestId("bottom-nav")).toBeVisible();
  await page.goto("/ar/app/store/market");
  await page.getByTestId("offer-card").first().getByTestId("add-offer").click();
  await page.goto("/ar/app/store/cart");
  await expect(page.getByTestId("checkout").first()).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  done();
});

test("representative on a phone sees today's work", async ({ page }) => {
  await login(page, USERS.rep);
  await expect(page.getByTestId("bottom-nav")).toBeVisible();
  for (const p of ["rep", "rep/visits", "rep/orders", "rep/commissions"]) {
    await page.goto(`/ar/app/${p}`);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, p).toBeLessThanOrEqual(1);
  }
});
