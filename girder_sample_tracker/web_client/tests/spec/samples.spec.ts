import fs from 'fs';

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

  test('filtering costs one request and leaves the field alone', async ({ page }) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Alpha');
    await createSample(page, 'Beta');
    await expect(page.locator('.g-view-sample')).toHaveCount(2);

    /* The server does the matching. Filtering in the browser meant fetching
     * page after page until enough of them matched, so the request count is
     * what keeps that from coming back. */
    const listed: string[] = [];
    page.on('request', (request) => {
      const match = /\/api\/v1\/sample\?(.*)$/.exec(request.url());
      if (match) {
        listed.push(decodeURIComponent(match[1]));
      }
    });

    await page.locator('.g-filter-field').fill('lph');
    await expect(page.locator('.g-view-sample')).toHaveText(['Alpha']);

    expect(listed).toHaveLength(1);
    expect(listed[0]).toContain('query=lph');

    /* Results arriving must not steal the value or the focus from someone
     * still typing. */
    await expect(page.locator('.g-filter-field')).toHaveValue('lph');
    await expect(page.locator('.g-filter-field')).toBeFocused();

    /* Page turns carry the filter rather than dropping back to everything. */
    listed.length = 0;
    await page.locator('.g-filter-field').fill('');
    await expect(page.locator('.g-view-sample')).toHaveCount(2);
    expect(listed).toHaveLength(1);
    expect(listed[0]).not.toContain('query=');
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
    await expect(page.locator('a.g-clear-checked')).toBeVisible();

    /* toBeVisible only looks at the element's own box, so it says yes to a
     * menu an ancestor's `overflow: hidden` has clipped away to nothing --
     * which is what the actions bar did to it once a floated control was
     * added. Hit-testing is what the user does. */
    const painted = await page.evaluate(() => [...document.querySelectorAll(
      '.g-checked-actions-menu a')].map((a) => {
      const box = a.getBoundingClientRect();
      const hit = document.elementFromPoint(box.left + 5, box.top + box.height / 2);
      return a.contains(hit) || a === hit;
    }));
    expect(painted).toEqual([true, true, true, true, true]);
    await capture(page, testInfo, 'checked-actions-menu');
  });

  test('the page size can be changed, and is remembered', async ({ page }, testInfo) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Coupon ', { batchSize: 30 });

    /* The default of 50 leaves all 30 on one page. */
    await expect(page.locator('.g-view-sample')).toHaveCount(30);

    await page.locator('select.g-page-size').selectOption('25');
    await waitForIdlePage(page);
    await expect(page.locator('.g-view-sample')).toHaveCount(25);
    await capture(page, testInfo, 'page-size-25');

    /* Leaving the list and coming back keeps the choice: printing one batch
     * of labels after another should not mean setting this every time. */
    await openSample(page, 'Coupon01');
    await gotoSampleTracker(page);
    await expect(page.locator('select.g-page-size')).toHaveValue('25');
    await expect(page.locator('.g-view-sample')).toHaveCount(25);
  });

  test('a selection survives a page turn', async ({ page }, testInfo) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Plate ', { batchSize: 30 });
    await page.locator('select.g-page-size').selectOption('25');
    await waitForIdlePage(page);

    /* Select-all takes this page, which is all it can see. */
    await page.locator('.g-select-all').check();
    await page.locator('.g-checked-actions-button').click();
    await expect(page.locator('.g-checked-picked-count')).toHaveText('25');
    await capture(page, testInfo, 'first-page-selected');
    /* The menu hangs over the rows below it -- and over the pager, once a
     * page is short enough -- so put it away before reaching past it. */
    await page.keyboard.press('Escape');

    await page.locator('.g-page-next a').click();
    await waitForIdlePage(page);
    await expect(page.locator('.g-view-sample')).toHaveCount(5);
    /* Nothing here was chosen, so nothing here is ticked... */
    await expect(page.locator('.g-select-sample:checked')).toHaveCount(0);
    await expect(page.locator('.g-select-all')).not.toBeChecked();
    /* ...and the 25 from the page before are still part of the selection. */
    await page.locator('.g-select-sample').first().check();
    await page.locator('.g-checked-actions-button').click();
    await expect(page.locator('.g-checked-picked-count')).toHaveText('26');
    await page.keyboard.press('Escape');

    /* Going back shows them still ticked, rather than merely counted. */
    await page.locator('.g-page-prev a').click();
    await waitForIdlePage(page);
    await expect(page.locator('.g-select-sample:checked')).toHaveCount(25);
    await expect(page.locator('.g-select-all')).toBeChecked();

    /* A selection that outgrows the page needs a way out that is not
     * hunting down every checkbox that made it. */
    await page.locator('.g-checked-actions-button').click();
    await page.locator('a.g-clear-checked').click();
    await expect(page.locator('.g-select-sample:checked')).toHaveCount(0);
    await expect(page.locator('.g-checked-actions-button')).toBeDisabled();
  });

  test('samples checked across pages download as one zip', async ({ page }) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Tag ', { batchSize: 30 });
    await page.locator('select.g-page-size').selectOption('25');
    await waitForIdlePage(page);

    /* Sorted by name, so this page is Tag01 through Tag25. */
    await page.locator('.g-select-all').check();
    await page.locator('.g-page-next a').click();
    await waitForIdlePage(page);
    /* ...and the first row of the next one is Tag26. */
    await page.locator('.g-select-sample').first().check();

    const download = page.waitForEvent('download');
    await page.locator('.g-checked-actions-button').click();
    await page.locator('a.g-download-checked').click();
    const saved = await download;

    expect(saved.suggestedFilename()).toBe('samples.zip');
    /* Zip entry names sit in the local file headers uncompressed, so the
     * archive can be read for what it holds without unpacking it. */
    const names = fs.readFileSync(await saved.path()).toString('latin1');
    expect(names).toContain('Tag01.png');
    expect(names).toContain('Tag25.png');
    expect(names).toContain('Tag26.png');
    /* One page's worth plus the one row, and nothing swept up along the way. */
    expect(names).not.toContain('Tag27.png');
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
