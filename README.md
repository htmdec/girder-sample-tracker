### Girder Sample Tracker

This plugin provides a simple tracker for material samples. It is intended to be used in conjunction with the [Girder](https://girder.readthedocs.io/en/latest/) data management platform.

### Testing

Both suites need a MongoDB on `localhost:27017`.

```bash
tox -e lint      # ruff
tox -e pytest    # server-side tests (pytest-girder)
tox -e ui        # web client tests (Playwright)
```

`tox -e ui` builds the web client, then drives it in Chromium against a real
Girder server that the tests start themselves -- one per spec file, each with
its own port and database. The first run needs the browser's system libraries,
which tox cannot install because they need root:

```bash
npm --prefix girder_sample_tracker/web_client run install-browsers
```

Arguments are passed through, so `tox -e ui -- --headed --workers 1` watches the
tests happen, and `tox -e ui -- events` runs only `events.spec.ts`.

Afterwards, in `girder_sample_tracker/web_client/`:

| Path | What it holds |
| --- | --- |
| `playwright-report/` | The HTML report: every test, its screenshots, and the trace and video of anything that failed. Open it with `npm run test:report`. |
| `screenshots/` | Screenshots of the key points of each test, as plain files. |
| `coverage/html/` | Web client coverage, mapped back to the original sources. |
| `test-results/` | Traces and videos, per failed test. |

CI runs the same command (the "Web client tests" job in
`.github/workflows/build-test.yaml`) and uploads all four as artifacts, so a
failure on a pull request comes with the screenshot of what the page looked
like when it broke.
