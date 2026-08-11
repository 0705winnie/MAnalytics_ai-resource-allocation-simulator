# Phase 3 Frontend Toolchain Recovery and Verification Report

Date: 2026-08-10

Scope: recover the local frontend dependency installation and verify the existing Phase 3 implementation. No production service, Neon database, deployment, commit, or push was performed.

## A. Root cause summary

### 1. Confirmed Vite/plugin-react incompatibility

The Git `HEAD` dependency declarations were incompatible:

- `vite`: `^8.1.0`
- `@vitejs/plugin-react`: `^4.3.4`
- lockfile resolution: Vite `8.1.0` and plugin-react `4.7.0`

Plugin-react `4.7.0` declares support for Vite 4 through 7, not Vite 8. This is a confirmed incompatible peer relationship and is consistent with the earlier Vitest startup and Vite transformation hangs.

Repository history also shows that the compatible Vite 7 line had already been used successfully:

- commit `bc286a7` changed Vite to `^7.3.6`
- a later auth branch still contained Vite 8 (`57ee7c7`)
- merge `5148066` reintroduced Vite 8

The minimal compatibility repair therefore restores Vite 7 rather than upgrading the broader React/Vite ecosystem.

### 2. Unhealthy/stalled node_modules behavior

The previous dependency tree was independently unhealthy even after the Vite declaration was corrected:

- Vite/Vitest/build processes repeatedly stalled.
- `npm ls` and filesystem traversal were abnormally slow.
- an interrupted/sandboxed `npm ci` left Vite and Vitest present but React, ReactDOM, and plugin-react missing.
- the partial tree could not be treated as a valid installation.

The old tree and the temporary backup tree were removed, and a clean lockfile installation produced a complete, internally consistent dependency tree.

### 3. Filesystem/repository-location assessment

Repository path:

```text
/Users/starrism/Documents/GitHub/MAnalytics_ai-resource-allocation-simulator
```

The path is on the local macOS APFS data volume. Its name does not indicate OneDrive, iCloud Drive, Dropbox, a network mount, or an external filesystem. There is no evidence that a cloud-synced repository location caused the dependency corruption.

Disk state during recovery:

```text
228 GiB total, 190 GiB used, 9.8 GiB available, 96% capacity
```

Available space was sufficient for the clean install, but the disk is relatively full and should be monitored.

Two additional local execution issues were observed:

- the first sandboxed `npm ci` could not write to the normal user-level npm log/cache area and exited with npm's `Exit handler never called!`; the same clean command succeeded immediately when allowed to use the normal npm environment;
- ordinary Git worktree scans intermittently stalled, while `GIT_OPTIONAL_LOCKS=0 git ...` completed immediately. This points to a local optional index-refresh/locking issue, not a Phase 3 source-code error.

## B. Cleanup performed

Only disposable/generated dependency and build artifacts were removed:

- removed the incomplete `./node_modules`;
- removed `./.phase3-dependency-backup/node_modules`;
- removed the now-empty `./.phase3-dependency-backup` directory;
- removed the generated `./dist` after recording the successful production build.

The `dist` removal was also necessary because the backend SPA fallback serves `dist/index.html` for otherwise test-only paths when `dist` exists. That caused 11 backend authentication tests to receive HTML rather than their test JSON/401/403 responses. All 11 affected tests passed after the generated directory was removed.

No application source, migration, `.env`, Git data, or Phase 0/1/2/3 implementation was reverted.

No task-owned npm, Vite, Vitest, tsc, or pytest process remained at the final process check.

## C. Final exact dependency versions

Environment:

- Node: `v22.23.1`
- npm: `10.9.8`

Clean-installed core dependency relationship:

- Vite: `7.3.6`
- `@vitejs/plugin-react`: `4.7.0`
- React: `18.3.1`
- ReactDOM: `18.3.1`
- TypeScript: `5.6.3`
- Vitest: `4.1.10`
- jsdom: `30.0.1`
- `@testing-library/react`: `16.3.2`
- `@testing-library/dom`: `10.4.1`
- `@testing-library/user-event`: `14.6.3`

`npm ls vite @vitejs/plugin-react vitest react react-dom --depth=0` exited with code 0 in 5.51 seconds and reported no peer or `ELSPROBLEMS` errors.

## D. package.json changes

Compared with Git `HEAD`, the existing Phase 3 worktree intentionally contains:

- Vite changed from `^8.1.0` to the compatible `^7.3.6` line;
- plugin-react left unchanged at `^4.3.4` (resolved as compatible `4.7.0`);
- React and ReactDOM left unchanged at `^18.3.1`;
- a one-shot `test` script using `vitest run`;
- Phase 3 testing dependencies: Vitest, jsdom, Testing Library React/DOM/user-event.

No broad frontend ecosystem upgrade was performed.

## E. package-lock.json changes

The lockfile now resolves the root Vite dependency to `7.3.6`, not Vite 8, and resolves plugin-react to `4.7.0`.

It also contains the intentionally added Vitest/jsdom/Testing Library dependency graph. The large mechanical lockfile diff reflects:

- replacing Vite 8's Rolldown-oriented graph with Vite 7's Rollup/esbuild graph;
- adding the test runner and jsdom dependency graph.

The successful clean `npm ci` consumed the existing lockfile and did not regenerate or further edit it.

## F. Clean install result and elapsed time

Command:

```bash
npm ci --no-audit --no-fund
```

The initial sandboxed attempt exited after approximately 77 seconds because npm could not use its normal user cache/log directory. Its partial `node_modules` was deleted.

The same clean lockfile command was then rerun with the required npm filesystem permissions:

```text
added 364 packages in 12s
exit code 0
measured command time: 12.23 seconds
```

No `npm install`, dependency upgrade, or repeated incremental repair was performed after the successful clean install.

## G. TypeScript result and elapsed time

`npx tsc --noEmit` stalled in the `npx` wrapper and was terminated at the two-minute fail-fast threshold.

The installed local compiler itself was healthy:

```bash
./node_modules/.bin/tsc --version
./node_modules/.bin/tsc --showConfig
./node_modules/.bin/tsc --noEmit
```

Final result:

- TypeScript `5.6.3`
- 35 files under `src` in the effective configuration
- `./node_modules/.bin/tsc --noEmit`: exit code 0
- elapsed time: 7.67 seconds

This isolates the earlier stall to the local `npx` launch path rather than TypeScript compilation or Phase 3 code.

## H. Production build result and elapsed time

Command:

```bash
npm run build
```

Result:

- exit code 0
- total measured command time: 19.92 seconds
- Vite build time: 12.20 seconds
- Vite version: 7.3.6
- 673 modules transformed

Output summary before the generated `dist` directory was removed:

```text
dist/index.html                   0.80 kB | gzip 0.43 kB
dist/assets/index-CeyResZe.css   26.09 kB | gzip 5.45 kB
dist/assets/index-C4EykS7u.js   689.77 kB | gzip 190.79 kB
```

The only build warning was the existing JavaScript chunk-size warning for a chunk larger than 500 kB. It did not fail the build.

## I. Vitest startup result

Minimal one-shot startup probe:

```bash
./node_modules/.bin/vitest run __vitest_startup_probe__ --passWithNoTests --config vitest.config.mjs
```

Result:

- Vitest started normally;
- no test files were intentionally collected;
- exit code 0;
- elapsed time: 2.29 seconds;
- no watch process or orphan remained.

## J. Focused Phase 3 test result

All focused Phase 3 test files passed sequentially in one-shot mode:

| Test file | Result | Vitest duration |
| --- | ---: | ---: |
| `src/pages/SimulationPage.test.tsx` | 9/9 passed | 1.72s |
| `src/App.test.tsx` | 8/8 passed | 1.02s |
| `src/lib/api.test.ts` | 3/3 passed | 1.05s |
| `src/pages/LeaderboardPage.test.tsx` | 4/4 passed | 1.32s |

Focused total: 24/24 passed.

## K. Full frontend test result

Command:

```bash
npm test
```

The package script uses `vitest run`, so it is one-shot/non-watch.

Result:

- 4/4 test files passed;
- 24/24 tests passed;
- Vitest duration: 2.60 seconds;
- measured command time: 3.26 seconds;
- exit code 0.

## L. Backend regression result

The backend suite was run only against the disposable local PostgreSQL database `resource_allocation_test` on `127.0.0.1:55432`.

Safety controls used:

- the repository test guard requires `postgresql+psycopg` and a database name ending exactly in `_test`;
- both `DATABASE_URL` and `TEST_DATABASE_URL` were overridden only inside the pytest process to the local test URL;
- no URL or credentials were printed by the test launcher;
- no Neon or production connection was used;
- the local Compose database was started on the README-documented alternate port 55432 because an unrelated owner prevented use of 5432;
- the local PostgreSQL container was left running, not terminated or deleted.

Pytest assertion rewriting was disabled with `--assert=plain` because the local Python environment repeatedly spent more than two minutes in `_pytest/assertion/rewrite.py`. This changes failure formatting, not which tests or assertions execute.

Final complete suite result after removing generated `dist`:

```text
370 passed, 1 failed, 4 warnings in 38.36s
```

The sole remaining failure is:

```text
tests/test_migrations.py::test_alembic_check_reports_no_drift
```

Alembic autogenerate reports two existing named check constraints as removal drift:

- `enrollment_status` on `enrollments`
- `user_role` on `users`

This is a backend migration/model metadata consistency issue outside the frontend recovery and Phase 3 scope. It was not changed.

An earlier run with `dist` present reported 12 failures and 359 passes. The 11 SPA-fallback authentication failures were isolated and all passed after removing `dist`; the final complete run therefore cleanly reports only the Alembic drift failure.

## M. git diff --check and final worktree result

Plain Git worktree scans intermittently stalled. The equivalent non-refreshing command completed immediately:

```bash
GIT_OPTIONAL_LOCKS=0 git diff --no-ext-diff --check
```

Final result: exit code 0, no whitespace errors.

One trailing space in `src/pages/PolicyAIPage.tsx` was found by a direct scan and removed without changing behavior before the final check.

Final status was captured with:

```bash
GIT_OPTIONAL_LOCKS=0 git status --short
```

It confirms that all existing Phase 0/1/2/3 tracked and untracked changes remain present. It also confirms:

- `node_modules` is not listed and remains ignored;
- `.env` is not listed and remains ignored;
- generated `dist` is absent;
- no secret/config file was added;
- no production data or deployment file was generated by verification.

No commit or push was performed.

## N. Phase 3 requirement audit

### A. Restoration

Confirmed:

- `App` calls `GET /api/simulation/session` through `getOfficialSimulationSession` after the authenticated student application mounts.
- The application remains in an explicit loading state until restoration succeeds.
- A failed restoration shows an error and retry action.
- No fabricated Month 1/session fallback is created.
- Simulation controls are not rendered, and therefore cannot run, until the official session is loaded.

### B. Official Run

Confirmed:

- `SimulationPage` calls `POST /api/simulation/session/months/next`.
- `expected_month` comes from `session.next_month` returned by the server.
- A fresh `crypto.randomUUID()` is created per new Run Month action.
- An uncertain retry retains and reuses the same complete request and idempotency UUID.
- The official request contains only `expected_month`, `idempotency_key`, `policy_code`, and `params`.
- It sends no `previous_months` and no client-authoritative user, course, enrollment, session, or current-month identifier.

### C. State replacement

Confirmed:

- A successful run replaces the client state with `response.session`, the complete official server session.
- There is no optimistic local month increment.

### D. HTTP 409 behavior

Confirmed:

- `wrong_expected_month` and `session_completed` trigger one official session restoration.
- Restoration replaces state and displays a notice.
- The UI does not automatically submit another Run Month request after restoration.
- `idempotency_key_conflict` is displayed as an explicit error and is not auto-retried.

### E. Submit flow

Confirmed:

- Student `Submit Result` UI and the `/api/submissions` frontend call are absent from production source.

### F. History

Confirmed:

- `Save to My History` is absent.
- Page 4 history is driven by `officialSession.monthly_results` restored from the backend.
- Completed months are described as saved automatically.

### G. Page 4 structure

Confirmed on the same page:

- Simulation History
- Same-Stage Leaderboard
- Final Leaderboard

### H. Leaderboards

Confirmed:

- Same-Stage and Final views are honest unavailable-state panels pending shared course ranking.
- No mock classmates, fake scores, or `Sharp Cluster` identity are displayed as real data.
- Real shared leaderboard implementation remains outside Phase 3 (Phase 5).

### I. localStorage

Confirmed:

- production `src` contains no `localStorage` or `sessionStorage` usage for official simulation progress/history;
- the former storage helper was removed;
- browser storage cannot authoritatively alter official session progress or history.

### J. Policy behavior

Confirmed:

- on first restoration, `latest_policy` restores the policy editor baseline;
- each historical monthly result provides a collapsed `View Policy Used` details control;
- historical policy code and parameters are available on demand;
- full policy source is not expanded by default.

## O. Remaining issues

1. Backend Alembic drift test remains failing because model metadata does not match two existing named check constraints. This predates and is independent of the frontend toolchain/Phase 3 work. No fix was attempted.
2. Plain Git commands can stall during optional worktree index refresh. `GIT_OPTIONAL_LOCKS=0` is an effective local diagnostic workaround; the underlying local Git/filesystem condition remains to be investigated separately.
3. `npx tsc --noEmit` stalled while the direct installed compiler completed in 7.67 seconds. Prefer the local binary or the validated `npm run build` until the local npx behavior is separately diagnosed.
4. The disk is 96% full with approximately 9.8 GiB available. This did not prevent recovery but may contribute to future local tool slowness.
5. The production build reports a non-fatal chunk-size warning for the 689.77 kB JavaScript bundle. Bundle splitting is outside this recovery scope.
6. The repository's local Docker PostgreSQL service remains running and healthy on port 55432 because the task explicitly prohibited terminating PostgreSQL. It contains the disposable local `resource_allocation_test` database used by regression tests.

## Final outcome

The frontend toolchain is recovered: the compatible Vite 7/plugin-react 4 stack installs cleanly, TypeScript passes, the production build exits successfully, Vitest starts normally, and all 24 Phase 3/frontend tests pass.

Phase 3 frontend verification is complete. Overall repository verification is not fully green because one pre-existing backend Alembic drift regression remains unresolved and was intentionally left unchanged.
