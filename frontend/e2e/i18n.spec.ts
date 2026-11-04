import { expect, test } from "@playwright/test";
import { expectNoRawKeys, login, USERS, watchErrors } from "./helpers";

const LOCALES = [
  { code: "ar", dir: "rtl", word: "وِصال" },
  { code: "en", dir: "ltr", word: "WESAL" },
  { code: "ur", dir: "rtl", word: "" },
  { code: "hi", dir: "ltr", word: "" },
];

for (const l of LOCALES) {
  test(`landing page renders in ${l.code} with ${l.dir}`, async ({ page }) => {
    const done = watchErrors(page);
    await page.goto(`/${l.code}`);
    await expect(page.locator("html")).toHaveAttribute("lang", l.code);
    await expect(page.locator("html")).toHaveAttribute("dir", l.dir);
    await expect(page.getByTestId("cta-register").first()).toBeVisible();
    await expectNoRawKeys(page);
    done();
  });

  test(`dashboard renders in ${l.code}`, async ({ page }) => {
    const done = watchErrors(page);
    await login(page, USERS.supplier, l.code);
    await expect(page.locator("html")).toHaveAttribute("dir", l.dir);
    await page.goto(`/${l.code}/app/supplier/orders`);
    await expect(page.locator("table, [data-testid=empty]").first()).toBeVisible();
    await expectNoRawKeys(page);
    done();
  });
}

test("language switcher changes direction and keeps the page", async ({ page }) => {
  await page.goto("/ar/faq");
  await page.getByTestId("language-switcher").first().click();
  await page.getByTestId("lang-en").click();
  await page.waitForURL(/\/en\/faq/);
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
});

test("legal pages are published in Arabic and English", async ({ page }) => {
  for (const loc of ["ar", "en"]) {
    await page.goto(`/${loc}/legal/terms`);
    await expect(page.locator("article h1")).toBeVisible();
  }
});
