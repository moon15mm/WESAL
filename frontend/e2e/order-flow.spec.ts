import { expect, test } from "@playwright/test";
import { login, USERS, watchErrors } from "./helpers";

test.describe.serial("representative order → store approval → supplier", () => {
  let orderNumber = "";

  test("representative builds an order and sends it to the store", async ({ page }) => {
    const done = watchErrors(page);
    await login(page, USERS.rep);
    await page.goto("/ar/app/rep/orders/new");
    const store = page.getByTestId("rep-order-store");
    await expect(store.locator("option")).not.toHaveCount(1);
    await store.selectOption({ label: "بقالة الحي الحديثة" });
    await page.getByTestId("rep-order-supplier").selectOption({ label: "شركة النخبة للأغذية" });
    await page.getByTestId("offer-card").first().getByTestId("add-offer").click();
    await page.getByTestId("send-to-store").click();
    await page.waitForURL(/\/app\/rep\/orders\/[0-9a-f-]{36}/);
    orderNumber = (await page.locator("h1 .ltr, h1").first().innerText()).match(/WSL-\d{4}-\d+/)![0];
    await expect(page.getByText("بانتظار موافقة المحل").first()).toBeVisible();
    done();
  });

  test("supplier cannot see it before the store approves", async ({ page }) => {
    await login(page, USERS.supplier);
    await page.goto("/ar/app/supplier/orders");
    await expect(page.locator("table")).toBeVisible();
    await expect(page.getByText(orderNumber)).toHaveCount(0);
  });

  test("store reviews and approves the exact version", async ({ page }) => {
    const done = watchErrors(page);
    await login(page, USERS.storeHay);
    await page.goto("/ar/app/store/approvals");
    await page.getByText(orderNumber).first().click();
    await page.getByTestId("approve-order").click();
    await expect(page.getByText("جديد").first()).toBeVisible();
    done();
  });

  test("supplier now receives the order", async ({ page }) => {
    await login(page, USERS.supplier);
    await page.goto("/ar/app/supplier/orders");
    await expect(page.getByText(orderNumber).first()).toBeVisible();
  });
});
