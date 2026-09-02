import fs from 'fs/promises';
import path from 'path';

import { PlaywrightTestConfig } from '@playwright/test';
import libCoverage from 'istanbul-lib-coverage';
import libReport from 'istanbul-lib-report';
import reports from 'istanbul-reports';

import { COVERAGE_DATA_DIR } from './coverage';

const LCOV_FILE = 'coverage/lcov.info';

/** Vite's stub for node built-ins it externalized; not a file anyone wrote. */
const isRealSource = (file: string) =>
  !path.basename(file).startsWith('__') && !file.includes('node_modules');

/**
 * Rewrite the lcov paths to be relative to the repository root.
 *
 * istanbul writes them relative to this directory (the common root of the
 * covered files), but Codecov matches what it is given against the repository,
 * so views/SampleListView.js has to become
 * girder_sample_tracker/web_client/views/SampleListView.js.
 */
const repoRelativeLcov = async () => {
  const repoRoot = path.resolve('../..');
  const report = await fs.readFile(LCOV_FILE, 'utf8');
  await fs.writeFile(
    LCOV_FILE,
    report.replace(/^SF:(.*)$/gm, (_line, file) => `SF:${path.relative(repoRoot, path.resolve(file))}`),
  );
};

/**
 * Merge the per-test istanbul fragments into one report.
 *
 * Three formats, for three readers: html for a person, lcov for Codecov (see
 * the "Web client tests" job in .github/workflows/build-test.yaml), and a
 * summary for whoever is watching the run.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default async (_config: PlaywrightTestConfig) => {
  let files: string[] = [];
  try {
    files = await fs.readdir(COVERAGE_DATA_DIR);
  } catch {
    // Nothing was collected; nothing to merge.
  }
  console.log(`Merging ${files.length} coverage fragment(s)`);
  if (files.length === 0) {
    return;
  }

  const merged = libCoverage.createCoverageMap({});
  for (const file of files) {
    merged.merge(JSON.parse(await fs.readFile(`${COVERAGE_DATA_DIR}/${file}`, 'utf8')));
  }
  const coverageMap = libCoverage.createCoverageMap({});
  for (const file of merged.files().filter(isRealSource)) {
    coverageMap.addFileCoverage(merged.fileCoverageFor(file).toJSON());
  }

  const context = libReport.createContext({
    dir: 'coverage',
    defaultSummarizer: 'nested',
    watermarks: {
      statements: [50, 80] as [number, number],
      functions: [50, 80] as [number, number],
      branches: [50, 80] as [number, number],
      lines: [50, 80] as [number, number],
    },
    coverageMap,
  });

  reports.create('html', { skipEmpty: false, subdir: 'html' }).execute(context);
  reports.create('lcovonly', { file: path.basename(LCOV_FILE) }).execute(context);
  reports.create('text-summary').execute(context);
  await repoRelativeLcov();
};
