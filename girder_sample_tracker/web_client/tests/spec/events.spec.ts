import { expect, test } from '@playwright/test';

import { setupServer } from '../server';
import {
  addEvent,
  capture,
  createSample,
  createUser,
  eventRows,
  expectEventRow,
  gotoSampleTracker,
  openSample,
  waitForDialog,
  waitForIdlePage,
} from '../util';

/* The add-event dialog prefills the location from navigator.geolocation, so
 * the browser is given a fixed position: somewhere in Urbana, IL. */
const GEOLOCATION = { latitude: 40.1164, longitude: -88.2434 };

test.use({ geolocation: GEOLOCATION, permissions: ['geolocation'] });

test.describe('Events', () => {
  setupServer();

  test('an event can be added and deleted from a sample', async ({ page }, testInfo) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Billet');
    await openSample(page, 'Billet');

    await page.locator('.g-new-event').click();
    await waitForDialog(page);
    await expect(page.locator('.modal-title')).toContainText('Add an event for Billet');
    await capture(page, testInfo, 'add-event-dialog');
    await addEvent(page, { eventType: 'received', comment: 'Arrived warm', location: 'Freezer 3' });

    await expect(eventRows(page)).toHaveCount(1);
    await expectEventRow(page, 0, ['received', 'Arrived warm', 'Freezer 3', 'First Last']);
    await capture(page, testInfo, 'event-recorded');

    await page.locator('#delete-event-0').click();
    await waitForIdlePage(page);
    await expect(eventRows(page)).toHaveCount(0);
  });

  test('declared event types are offered as a dropdown', async ({ page }, testInfo) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Coupon', { eventTypes: ['forging', 'XRD'] });
    await openSample(page, 'Coupon');

    await page.locator('.g-new-event').click();
    await waitForDialog(page);

    const eventType = page.locator('#eventType');
    await expect(eventType).toHaveJSProperty('tagName', 'SELECT');
    await expect(eventType.locator('option')).toHaveText(['forging', 'XRD']);
    await capture(page, testInfo, 'event-type-dropdown');

    await addEvent(page, { eventType: 'XRD' });
    await expect(eventRows(page).first()).toContainText('XRD');
  });

  test('the location is prefilled from the browser position', async ({ page }, testInfo) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Rover');
    await openSample(page, 'Rover');

    await page.locator('.g-new-event').click();
    await waitForDialog(page);

    await expect(page.locator('#location')).toHaveValue(
      `${GEOLOCATION.latitude},${GEOLOCATION.longitude}`,
    );
    await capture(page, testInfo, 'geolocated-event-dialog');

    await page.locator('#eventType').fill('sampled');
    await page.locator('#g-event-btn').click();
    await waitForIdlePage(page);

    /* A location that parses as coordinates is rendered as a map link. */
    const mapLink = eventRows(page).first().locator('a[href*="openstreetmap.org"]');
    await expect(mapLink).toHaveText(`${GEOLOCATION.latitude},${GEOLOCATION.longitude}`);
    await expect(mapLink).toHaveAttribute(
      'href',
      `https://www.openstreetmap.org/#map=18/${GEOLOCATION.latitude}/${GEOLOCATION.longitude}`,
    );
    await capture(page, testInfo, 'event-with-map-link');
  });

  test('a scanned QR code opens the add-event dialog', async ({ page }, testInfo) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Scanned');
    await openSample(page, 'Scanned');
    const sampleId = new URL(page.url()).hash.split('/')[1];

    /* This is the route the QR code on the sample's label points at. */
    await page.goto(`${new URL(page.url()).origin}/#sample/${sampleId}/add`);

    await waitForDialog(page);
    await expect(page.locator('.modal-title')).toContainText('Add an event for Scanned');
    await capture(page, testInfo, 'add-event-from-qr-route');

    await addEvent(page, { eventType: 'scanned', location: 'Bay 4' });
    await expectEventRow(page, 0, ['scanned', 'Bay 4']);
  });

  test('one event can be added to several checked samples', async ({ page }, testInfo) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Tube ', { batchSize: 3 });

    await page.locator('.g-select-all').check();
    await page.locator('.g-checked-actions-button').click();
    await page.locator('a.g-add-event').click();
    await waitForDialog(page);
    await expect(page.locator('.modal-title')).toContainText('Add an event for Samples');
    await addEvent(page, { eventType: 'shipped', location: 'Dock' });

    await expect(page.locator('#g-alerts-container')).toContainText('3 sample(s) received the event');
    await capture(page, testInfo, 'bulk-event-alert');

    await openSample(page, 'Tube2');
    await expectEventRow(page, 0, ['shipped', 'Dock']);
  });

  test('samples that reject the event type are reported, not silently dropped', async ({ page }, testInfo) => {
    await createUser(page);
    await gotoSampleTracker(page);
    await createSample(page, 'Strict', { eventTypes: ['forging'] });
    await createSample(page, 'Loose');

    await page.locator('.g-select-all').check();
    await page.locator('.g-checked-actions-button').click();
    await page.locator('a.g-add-event').click();
    await waitForDialog(page);
    await addEvent(page, { eventType: 'shipped' });

    /* "Strict" only allows forging, so the bulk write is partial: one sample
     * took the event, one refused it. */
    await expect(page.locator('#g-alerts-container')).toContainText(
      '1 sample(s) failed to receive the event',
    );
    await expect(page.locator('#g-alerts-container')).toContainText(
      '1 sample(s) received the event',
    );
    await capture(page, testInfo, 'bulk-event-partial-failure');

    await openSample(page, 'Strict');
    await expect(eventRows(page)).toHaveCount(0);
  });
});
