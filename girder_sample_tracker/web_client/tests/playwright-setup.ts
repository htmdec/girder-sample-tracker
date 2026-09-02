import fs from 'fs';

import { PlaywrightTestConfig } from '@playwright/test';

import { COVERAGE_DATA_DIR } from './coverage';
import { SCREENSHOT_DIR } from './util';

/** Start every run with no stale coverage fragments or screenshots around. */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default (_config: PlaywrightTestConfig) => {
  for (const dir of ['coverage', SCREENSHOT_DIR]) {
    fs.rmSync(dir, { recursive: true, force: true });
  }
  fs.mkdirSync(COVERAGE_DATA_DIR, { recursive: true });
};
