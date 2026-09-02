import fs from 'fs';
import path from 'path';

import { expect, Locator, Page, test, TestInfo } from '@playwright/test';

/** Where key-point screenshots land, in addition to the HTML report. */
export const SCREENSHOT_DIR = 'screenshots';

/**
 * Save a screenshot of a moment worth looking at later.
 *
 * The image is both attached to the Playwright HTML report (so it shows up
 * inline next to the step that took it) and written to screenshots/ as a
 * flatly-named file, which is what makes it browsable in the CI artifact
 * without opening the report.
 */
export const capture = async (page: Page, testInfo: TestInfo, name: string) => {
  const slug = `${testInfo.titlePath.join(' ')} ${name}`
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  const file = path.join(SCREENSHOT_DIR, `${slug}.png`);
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  await page.screenshot({ path: file, fullPage: true });
  await testInfo.attach(name, { path: file, contentType: 'image/png' });
};

/** Wait for all outstanding REST requests to complete. */
const waitForRestIdle = (page: Page) => page.waitForFunction(
  // @ts-ignore -- girder is a global installed by the app bundle.
  () => window.girder?.rest?.numberOutstandingRestRequests() === 0,
  { timeout: 10000 },
);

/** Wait for the app to be settled with no dialog on top of it. */
export const waitForIdlePage = async (page: Page) => {
  await expect(page.locator('#g-dialog-container')).toBeHidden();
  await expect(page.locator('.modal-backdrop')).toBeHidden();
  await waitForRestIdle(page);
};

/** Wait for a dialog to be up and done loading. */
export const waitForDialog = async (page: Page) => {
  await expect(page.locator('#g-dialog-container')).toBeVisible();
  await expect(page.locator('.modal-backdrop')).toBeVisible();
  await waitForRestIdle(page);
};

/**
 * A login unique to the running test.
 *
 * One Girder server is shared by all the tests in a spec file, so tests cannot
 * share a login -- the second registration of a name fails. Deriving it from
 * the test title also isolates the data: samples are private to their creator,
 * so each test only ever sees its own.
 */
const testUserLogin = () => {
  const slug = test.info().titlePath.join('')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '');
  return `u${slug}`.slice(0, 30);
};

/**
 * Register a user through the UI. The first user registered on a fresh Girder
 * is an administrator, which is what the sample views need to show their
 * admin-only controls.
 */
export const createUser = async (
  page: Page,
  login: string = testUserLogin(),
  email: string = `${login}@girder.test`,
  firstName: string = 'First',
  lastName: string = 'Last',
  password: string = 'password',
) => {
  await expect(page.locator('.g-register')).toBeVisible();
  await page.locator('.g-register').click();
  await waitForDialog(page);
  await expect(page.locator('input#g-email')).toBeVisible();
  await page.locator('#g-login').fill(login);
  await page.locator('#g-email').fill(email);
  await page.locator('#g-firstName').fill(firstName);
  await page.locator('#g-lastName').fill(lastName);
  await page.locator('#g-password').fill(password);
  await page.locator('#g-password2').fill(password);
  await page.locator('#g-register-button').click();
  await waitForIdlePage(page);
  await expect(page.locator('.g-user-dropdown-link')).toContainText(login);
};

export const login = async (page: Page, user: string, password: string = 'password') => {
  await expect(page.locator('.g-login')).toBeVisible();
  await page.locator('.g-login').click();
  await waitForDialog(page);
  await page.locator('#g-login').fill(user);
  await page.locator('#g-password').fill(password);
  await page.locator('#g-login-button').click();
  await waitForIdlePage(page);
  await expect(page.locator('.g-user-dropdown-link')).toContainText(user);
};

export const logout = async (page: Page) => {
  await page.locator('.g-user-dropdown-link').click();
  await page.locator('.g-logout').click();
  await expect(page.locator('.g-login')).toBeVisible();
};

/** Follow the plugin's entry in the global navigation. */
export const gotoSampleTracker = async (page: Page) => {
  await page.getByRole('link', { name: 'Sample Tracker' }).click();
  await expect(page.locator('.g-samples-title')).toContainText('Samples');
  await waitForIdlePage(page);
};

/**
 * Create a sample through the "Add a new sample" dialog, ending back on the
 * sample list.
 *
 * Saving takes the app to the new sample's own view, so this asserts that
 * landing (which is the proof the sample was created) and then returns to the
 * list, so every caller starts from the same place. For a batch, the app lands
 * on the first sample of the batch.
 *
 * ``eventTypes`` are typed into the tagsinput widget, which replaces the
 * original input with its own; each Enter turns the typed word into a tag.
 */
export const createSample = async (
  page: Page,
  name: string,
  { description, eventTypes, batchSize }: {
    description?: string;
    eventTypes?: string[];
    batchSize?: number;
  } = {},
) => {
  await page.locator('.g-new-sample').click();
  await waitForDialog(page);
  await page.locator('#name').fill(name);
  if (description) {
    await page.locator('#description').fill(description);
  }
  for (const eventType of eventTypes ?? []) {
    const tagsField = page.locator('.bootstrap-tagsinput input');
    await tagsField.fill(eventType);
    await tagsField.press('Enter');
  }
  if (batchSize) {
    await page.locator('#batchSize').fill(`${batchSize}`);
  }
  await page.locator('#g-sample-btn').click();
  await expect(page.locator('.g-sample-title')).toBeVisible();
  await waitForIdlePage(page);
  await gotoSampleTracker(page);
};

/** Open a sample's detail view from the list. */
export const openSample = async (page: Page, name: string) => {
  await page.locator('.g-view-sample', { hasText: name }).first().click();
  await expect(page.locator('.g-sample-title')).toContainText(name);
  await waitForIdlePage(page);
};

/** Add an event from a sample detail view, or from the checked-samples menu. */
export const addEvent = async (
  page: Page,
  { eventType, comment, location }: {
    eventType: string;
    comment?: string;
    location?: string;
  },
) => {
  const eventTypeField = page.locator('#eventType');
  if (await eventTypeField.evaluate((el) => el.tagName === 'SELECT')) {
    await eventTypeField.selectOption(eventType);
  } else {
    await eventTypeField.fill(eventType);
  }
  if (comment) {
    await page.locator('#comment').fill(comment);
  }
  /* The dialog prefills the location from navigator.geolocation, which lands
   * asynchronously and would overwrite whatever we typed. Wait for the settled
   * value -- "lat,long", or "Unknown" when the browser will not say, never the
   * interim "Locating..." or the empty field before the dialog is shown -- and
   * only then take the field over. */
  const locationField = page.locator('#location');
  await expect(locationField).toHaveValue(/^(?!Locating).+/);
  await locationField.fill(location ?? '');
  await page.locator('#g-event-btn').click();
  await waitForIdlePage(page);
};

/** The rows of the event table on a sample detail view. */
export const eventRows = (page: Page): Locator => page.locator('.g-events-widget tbody tr');

/**
 * Assert that one event row mentions all of ``texts``.
 *
 * One assertion per string, because toContainText with an array matches the
 * array against a *list* of elements, not one element against every string.
 */
export const expectEventRow = async (page: Page, index: number, texts: string[]) => {
  const row = eventRows(page).nth(index);
  for (const text of texts) {
    await expect(row).toContainText(text);
  }
};
