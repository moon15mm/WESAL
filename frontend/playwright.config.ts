import { defineConfig, devices } from "@playwright/test";

// E2E runs against a running DEMO environment (backend with DEMO_MODE=true + `reset-demo`, frontend `next start`).
//   E2E_BASE_URL=http://localhost:3000 npx playwright test
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "e2e-report" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    launchOptions: process.env.CHROMIUM_PATH || process.env.CI ? {} : { executablePath: "/opt/pw-browsers/chromium" },
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1360, height: 900 } }, testIgnore: /mobile/ },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: /mobile/ },
  ],
});
