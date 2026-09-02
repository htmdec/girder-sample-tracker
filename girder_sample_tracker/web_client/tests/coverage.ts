import fs from 'fs/promises';
import path from 'path';

import { Page } from '@playwright/test';
import v8toIstanbul from 'v8-to-istanbul';

/** Per-test istanbul JSON is dropped here; playwright-teardown merges it. */
export const COVERAGE_DATA_DIR = 'coverage/data';

/** The bundle Girder serves for this plugin, and the build that produced it. */
const BUNDLE = 'girder-plugin-sample-tracker.umd.cjs';
const BUNDLE_PATH = path.join('dist', BUNDLE);

let fileCounter = 0;

export const startCoverage = async (page: Page) => {
  try {
    await page.coverage.startJSCoverage({ resetOnNavigation: false });
  } catch {
    // Only Chromium exposes V8 coverage; elsewhere we simply collect none.
  }
};

/**
 * Convert the V8 coverage of the plugin bundle into istanbul JSON.
 *
 * The bundle's source map is fed to v8-to-istanbul, so the report is keyed by
 * the files a reader recognizes (views/SampleListView.js and friends) rather
 * than by one line-less blob of built output.
 */
export const outputCoverageReport = async (page: Page) => {
  let coverage;
  try {
    coverage = await page.coverage.stopJSCoverage();
  } catch {
    return;
  }

  const entries = coverage.filter((entry) => entry.url.split('?')[0].endsWith(BUNDLE));
  if (entries.length === 0) {
    return;
  }

  let sourceMap;
  try {
    sourceMap = JSON.parse(await fs.readFile(`${BUNDLE_PATH}.map`, 'utf8'));
  } catch {
    /* Built without sourcemaps: still report, against the bundle itself. */
    sourceMap = undefined;
  }

  await fs.mkdir(COVERAGE_DATA_DIR, { recursive: true });
  for (const entry of entries) {
    const converter = v8toIstanbul(
      BUNDLE_PATH,
      0,
      { source: entry.source ?? '', sourceMap: sourceMap && { sourcemap: sourceMap } },
      (filePath) => filePath.includes('node_modules'),
    );
    await converter.load();
    converter.applyCoverage(entry.functions);
    fileCounter += 1;
    await fs.writeFile(
      path.join(COVERAGE_DATA_DIR, `istanbul-${process.pid}-${fileCounter}.json`),
      JSON.stringify(converter.toIstanbul()),
    );
    converter.destroy();
  }
};
