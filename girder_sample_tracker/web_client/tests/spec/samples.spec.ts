import { expect, test } from '@playwright/test';

import { setupServer } from '../server';
import {
  capture,
  createSample,
  createUser,
  gotoSampleTracker,
  logout,
  openSample,
  waitForDialog,
  waitForIdlePage,
} from '../util';

test.describe('Sample list', () => {
  setupServer();

  test('a sample can be created, found and opened', async ({ page }, testInfo) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await expect(page.locator('.g-no-samples-record')).toContainText('No samples found');
    await capture(page, testInfo, 'empty-list');

    await createSample(page, 'Ingot A', {
      description: 'An ingot of something',
      eventTypes: ['forging', 'XRD'],
    });

    await expect(page.locator('.g-view-sample')).toHaveText(['Ingot A']);
    await capture(page, testInfo, 'one-sample');

    await openSample(page, 'Ingot A');
    await expect(page.locator('.g-sample-description')).toContainText('An ingot of something');
    /* The QR code that a phone scans to reach the add-event route. */
    await expect(page.locator('canvas#g-sample-qr')).toBeVisible();
    await capture(page, testInfo, 'sample-detail');
  });

  test('a batch creates one numbered sample per member', async ({ page }, testInfo) => {
    await createUser(page);
    await gotoSampleTracker(page);

    await createSample(page, 'Tube ', { batchSize: 3 });

    /* The dialog trims the name before using it as the stem. */
    await expect(page.locator('.g-view-sample')).toHaveText(['Tube1', 'Tube2', 'Tube3']);
    await capture(page, testInfo, 'batch-of-three');
  });

  test('the filter field narrows the list by regex', async ({ page }, testInfo) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Alpha');
    await createSample(page, 'Beta');
    await createSample(page, 'Gamma');
    await expect(page.locator('.g-view-sample')).toHaveCount(3);

    /* The view debounces typing for 500ms before it refetches and filters. */
    await page.locator('.g-filter-field').fill('lph');

    await expect(page.locator('.g-view-sample')).toHaveText(['Alpha']);
    await capture(page, testInfo, 'filtered-list');

    /* Matching is case-insensitive... */
    await page.locator('.g-filter-field').fill('BET');
    await expect(page.locator('.g-view-sample')).toHaveText(['Beta']);

    /* ...and regex metacharacters are stripped before the match, so an anchor
     * matches nothing in particular rather than anchoring. */
    await page.locator('.g-filter-field').fill('^a');
    await expect(page.locator('.g-view-sample')).toHaveText(['Alpha', 'Beta', 'Gamma']);

    await page.locator('.g-filter-field').fill('');
    await expect(page.locator('.g-view-sample')).toHaveCount(3);
  });

  test('checking samples enables the batch actions menu', async ({ page }, testInfo) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Coupon 1');
    await createSample(page, 'Coupon 2');

    await expect(page.locator('.g-checked-actions-button')).toBeDisabled();

    await page.locator('.g-select-all').check();
    await expect(page.locator('.g-checked-actions-button')).toBeEnabled();
    await page.locator('.g-checked-actions-button').click();

    await expect(page.locator('.g-checked-picked-count')).toHaveText('2');
    await expect(page.locator('a.g-download-checked')).toBeVisible();
    await expect(page.locator('a.g-add-event')).toBeVisible();
    await expect(page.locator('a.g-access-checked')).toBeVisible();
    await expect(page.locator('a.g-delete-checked')).toBeVisible();
    await capture(page, testInfo, 'checked-actions-menu');
  });

  test('checked samples can be deleted', async ({ page }) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Scrap');
    await expect(page.locator('.g-view-sample')).toHaveCount(1);

    await page.locator('.g-select-all').check();
    await page.locator('.g-checked-actions-button').click();
    await page.locator('a.g-delete-checked').click();
    await waitForDialog(page);
    await page.locator('#g-confirm-button').click();
    await waitForIdlePage(page);

    await expect(page.locator('.g-no-samples-record')).toContainText('No samples found');
  });

  test('a QR code label can be downloaded for a sample', async ({ page }) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Labelled');
    await openSample(page, 'Labelled');

    const download = page.waitForEvent('download');
    await page.locator('.g-download-sample').click();

    /* The PNG the lab prints and sticks on the tube. */
    expect((await download).suggestedFilename()).toBe('Labelled.png');
  });

  test('an anonymous visitor sees no create button', async ({ page }) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Public-ish');
    await logout(page);

    await gotoSampleTracker(page);

    await expect(page.locator('.g-new-sample')).toHaveCount(0);
    /* ...and none of the samples, since they are private to their creator. */
    await expect(page.locator('.g-no-samples-record')).toContainText('No samples found');
  });
});
