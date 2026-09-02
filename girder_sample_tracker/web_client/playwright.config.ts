import { cpus, totalmem } from 'os';

import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for the sample-tracker web client.
 *
 * Modelled on the upstream Girder configuration (girder/web/playwright.config.ts),
 * with two differences: there is no vite dev server, because these tests drive the
 * plugin as the Girder server actually serves it (a built bundle under
 * /plugin_static/sample_tracker/), and artifacts are written where CI can collect
 * them -- see the "Web client tests" job in .github/workflows/build-test.yaml.
 *
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './tests/spec',
  outputDir: './test-results',
  /* Each spec file runs its own Girder server, so files are not parallel-safe
   * against each other in the way fullyParallel implies. */
  fullyParallel: false,
  /* Fail the build on CI if test.only is in the source code. */
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: (() => {
    if (process.env.PLAYWRIGHT_WORKERS) {
      return parseInt(process.env.PLAYWRIGHT_WORKERS);
    }
    /* One worker on CI: a Girder server per worker, on a 4-vCPU runner. */
    if (process.env.CI) {
      return 1;
    }
    /* Locally, one worker per spec file is fine, but each one costs a Girder
     * server and a Chromium, so cap on memory as well as cores. */
    return Math.max(1, Math.min(cpus().length, Math.floor(totalmem() / (4 * 1024 ** 3))));
  })(),
  /* Starting a Girder server in beforeAll is charged to the first test. */
  timeout: 120000,
  expect: { timeout: 15000 },
  reporter: [
    ['list'],
    /* Screenshots, traces and videos are attached to this report; it is
     * uploaded as an artifact so a failure can be inspected after the fact. */
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
    ...(process.env.CI ? [['github'] as const] : []),
  ],
  reporterOpenTimeout: 0,
  globalSetup: './tests/playwright-setup.ts',
  globalTeardown: './tests/playwright-teardown.ts',
  use: {
    actionTimeout: 30000,
    /* Everything needed to see what went wrong, without paying for it on the
     * happy path. */
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    headless: true,
  },
  /* Chromium only: it is what the V8 coverage collection below needs, and the
   * plugin ships one bundle for every browser. */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
