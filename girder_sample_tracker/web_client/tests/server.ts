import { spawn, ChildProcessWithoutNullStreams } from 'child_process';

import getPort from 'get-port';
import { MongoClient } from 'mongodb';
import { expect, test } from '@playwright/test';

import { outputCoverageReport, startCoverage } from './coverage';
import { capture } from './util';

const mongoUri = process.env.GIRDER_CLIENT_TESTING_MONGO_URI ?? 'mongodb://localhost:27017';
const girderExecutable = process.env.GIRDER_CLIENT_TESTING_GIRDER_EXECUTABLE ?? 'girder';

/** How long the server gets to answer its first request before we give up. */
const STARTUP_TIMEOUT = 90000;

interface GirderServer {
  process: ChildProcessWithoutNullStreams;
  logs: string[];
  port: number;
  database: string;
}

const waitForApi = async (port: number, logs: string[]) => {
  const deadline = Date.now() + STARTUP_TIMEOUT;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://localhost:${port}/api/v1/system/version`);
      if (response.ok) {
        return;
      }
    } catch {
      // Not listening yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(
    `Girder did not start within ${STARTUP_TIMEOUT}ms. Server output:\n${logs.join('')}`,
  );
};

const startServer = async (): Promise<GirderServer> => {
  const port = await getPort();
  const database = `${mongoUri}/girder-sample-tracker-ui-${port}`;
  const logs: string[] = [];
  const serverProcess = spawn(girderExecutable, [
    'serve',
    '--database', database,
    '--port', `${port}`,
    '--with-temp-assetstore',
  ], {
    env: {
      ...process.env,
      GIRDER_SETTING_CORE_CORS_ALLOW_ORIGIN: '*',
      GIRDER_EMAIL_TO_CONSOLE: 'true',
    },
  });
  serverProcess.stdout.on('data', (data: string) => logs.push(`stdout: ${data}`));
  serverProcess.stderr.on('data', (data: string) => logs.push(`stderr: ${data}`));
  serverProcess.on('close', (code) => logs.push(`girder exited with code ${code}\n`));

  await waitForApi(port, logs);
  return { process: serverProcess, logs, port, database };
};

const dropDatabase = async (uri: string) => {
  const client = new MongoClient(uri);
  try {
    await client.connect();
    await client.db().dropDatabase();
  } finally {
    await client.close();
  }
};

/**
 * Run a Girder server with this plugin installed for the enclosing describe
 * block, and open its home page before each test.
 *
 * Each spec file gets its own server, port and database, so specs cannot see
 * each other's samples. Set GIRDER_CLIENT_TESTING_KEEP_SERVER_ALIVE to leave
 * the server (and its database) running after the tests, to poke at by hand.
 */
export const setupServer = () => {
  let server: GirderServer | null = null;

  test.beforeAll(async () => {
    server = await startServer();
  });

  test.afterAll(async () => {
    if (!server) {
      return;
    }
    if (process.env.GIRDER_CLIENT_TESTING_KEEP_SERVER_ALIVE) {
      console.log(`Girder left running on http://localhost:${server.port} (kill ${server.process.pid})`);
      return;
    }
    server.process.kill();
    try {
      await dropDatabase(server.database);
    } catch (e) {
      console.error(`Could not drop ${server.database}:`, e);
    }
  });

  test.beforeEach(async ({ page }) => {
    await startCoverage(page);
    /* The first navigation can race the server's own lazy initialization, so
     * retry the whole "is the app up" check rather than a bare goto. */
    await expect(async () => {
      await page.goto(`http://localhost:${server!.port}/`);
      await expect(page.getByRole('link', { name: 'About' })).toBeVisible();
    }).toPass({ timeout: 60000 });
  });

  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== testInfo.expectedStatus) {
      /* A failure gets a screenshot of the page as it was left, on top of the
       * automatic only-on-failure one, plus the server's side of the story. */
      await capture(page, testInfo, 'failure');
      if (server && server.logs.length > 0) {
        console.log(`Girder output for failed test "${testInfo.title}":`);
        console.log(server.logs.join(''));
      }
    }
    if (server) {
      server.logs = [];
    }
    await outputCoverageReport(page);
  });
};
