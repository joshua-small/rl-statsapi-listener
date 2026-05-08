const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests",
  testMatch: "**/*.playwright.spec.js",
  outputDir: "test-results/playwright",
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 2560, height: 1440 },
    trace: "on-first-retry",
  },
});
