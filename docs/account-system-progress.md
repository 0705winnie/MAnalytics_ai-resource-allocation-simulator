# Account System Implementation Progress

Last updated: July 28, 2026
Repository: `MunazzaNadir/ai-resource-allocation-simulator`
Development base branch: `integration/main-dashboard`
Login feature branch: `integration/main-dashboard-login`

## 1. Purpose and confirmed product decisions

The project is adding a course-specific, roster-based account system to replace
browser `localStorage` as the source of truth for identity and simulation
history.

Confirmed decisions:

- Use a course-specific login system rather than Berkeley CalNet/SSO.
- Use PostgreSQL as the application database.
- Run PostgreSQL locally with Docker during development.
- Support multiple course instances and semesters.
- Allow one global user to enroll in more than one course.
- Store the global password on the user account.
- Store the leaderboard nickname on the course enrollment.
- Require a unique, one-time activation code for each student enrollment.
- Store passwords and activation codes only as secure Argon2 hashes.
- Use HttpOnly authentication cookies rather than persistent credentials in
  `localStorage`.
- Show nicknames, not Berkeley usernames, on public rankings.
- Treat both Same-Stage Comparison and the 12-month Final Leaderboard as formal
  rankings, but keep them separate.

## 2. Completed work

### Phase 1A — PostgreSQL foundation

- Added PostgreSQL configuration for the FastAPI backend.
- Established Docker-based local database development.
- Added strict separation between development and test databases.
- Added database connectivity and configuration validation.

Commit: `0a81010a28592d461f5ee1d51d9dc1544216083d`

### Phase 1B — Core account models and migrations

- Added SQLAlchemy models for:
  - `User`
  - `CourseInstance`
  - `Enrollment`
- Added Alembic migrations.
- Added foreign keys, enums, relationships, and uniqueness constraints.
- Enforced test database names ending in `_test` to reduce accidental data
  loss.

Commit: `fe0bd0415f29f7a1ada94a295bed026cdb3119a4`

### Phase 1C — Credential security and instructor seed

- Added Argon2 password hashing and verification.
- Added validated authentication configuration.
- Added a safe initial instructor-account seed workflow.
- Ensured real credentials are loaded from `.env` and are not committed.

Commit: `21183bb8c5053736e2f3366ad79c2594e0347e98`

### Phase 2A — Activation-code lifecycle

- Added cryptographically secure activation-code generation.
- Stored activation codes as hashes only.
- Added activation expiration, single-use behavior, regeneration, and
  invalidation.
- Prevented plaintext activation codes from being recoverable from the
  database.

Commit: `c721cbcf37f8d4579740caa10c736041d4842667`

### Phase 2B — Instructor authentication

- Added instructor login with signed JWT access tokens.
- Stored access tokens in HttpOnly cookies.
- Added logout and database-backed `/api/auth/me`.
- Added role checks and active-account checks.
- Added uniform authentication errors without leaking credential details.

Commit: `f095aef9e938f213309325ce1ce4b576562590b2`

### Phase 2C-1 — Instructor course management

- Added instructor-protected course creation and course listing.
- Added course-code normalization and uniqueness validation.
- Bound created courses to the authenticated instructor.
- Added authorization and database tests.

Commit: `366cc4a0ebc37dcf45593f480c6d141b94b67a23`

### Phase 2C-2 — Secure roster import

- Added instructor-protected CSV roster upload.
- Normalized and deduplicated Berkeley usernames.
- Created users and course enrollments safely.
- Generated a distinct activation code for each new enrollment.
- Returned plaintext activation codes only in the one-time import result.
- Added import validation, duplicate handling, rollback, and security tests.

Commit: `4dca54b`

### Phase 2C-3 — Instructor enrollment management

- Added instructor views for course enrollments.
- Added activation-code regeneration.
- Added student enrollment enable/disable management.
- Added course ownership checks and safe error handling.

Commit: `f3e1ad27d740cf45094f90c63b6bd943f8fe3527`

### Phase 3A — Student activation verification

- Added student verification using:
  - course code
  - Berkeley username
  - activation code
- Added a short-lived, course-bound activation JWT cookie.
- Revalidated the current user, course, enrollment, expiration, and activation
  hash.
- Kept activation verification separate from activation consumption.
- Added uniform failure responses to limit identity and roster enumeration.

Commit: `cb7211d14b499572fca66bc8a81d5428c2da9a80`

### Phase 3B — Student activation completion

- Added account activation completion with:
  - password creation for a new global account
  - existing-password confirmation for a user already enrolled elsewhere
  - course-specific leaderboard nickname creation
- Added nickname normalization, validation, and course-level uniqueness.
- Prevented a nickname from reproducing the student's Berkeley username.
- Atomically consumed the activation code and activated the enrollment.
- Added course-scoped Student JWT claims containing `course_id` and
  `enrollment_id`.
- Added database-backed Student session validation.
- Added row locks on `Enrollment`, `User`, and `CourseInstance` during
  activation completion.
- Rejected incomplete or inconsistent active-enrollment states.
- Prevented validation errors from echoing passwords or oversized raw inputs.
- Preserved the existing Instructor `/api/auth/me` response while adding
  Student course and nickname information.

Verification results:

- Targeted account tests: `187 passed`
- Full backend suite: `296 passed, 5 failed`
- The five failures are pre-existing simulation baseline failures.
- No new test failures were introduced.
- TypeScript check passed.
- Frontend production build passed with only non-blocking Vite warnings.
- Staged diff and secret scan passed.

Commit: `58228055f9e9a0e7feaeebe720d48835ff479d49`

### Phase 3C — Student regular login

- Added Student login using Course Code, Berkeley Username, and Password.
- Added course-scoped Student JWTs and multi-course enrollment selection.
- Added uniform authentication failure responses and shared dummy Argon2
  verification.
- Revalidated inactive users, courses, and enrollments.
- Added HttpOnly access cookies, Student `/api/auth/me`, and logout.

Targeted tests:

- `test_student_login.py`: `35 passed`
- `test_auth.py`: `41 passed`

Commit: `71ea89201eda32ec9ccbff2d0579e42c59b2c258`

### Phase 4A — Frontend authentication foundation

- Added React Router with `/login` and `/app/*`.
- Added `AuthProvider` and `/api/auth/me` session restoration.
- Added protected Student routes, the Student Login page, and Student logout.
- Displayed the authenticated course nickname and course code.
- Clearly marked the legacy local profile as a local prototype.
- Verified desktop and 390px layouts.

Commit: `57ee7c7b24fc63cd18659716d426420a6e7613ef`

### Phase 4B — Student activation UI

- Added `/activate` with a two-step activation flow.
- Added activation-code verification.
- Added create-password and confirm-existing-password modes.
- Added course-specific leaderboard nickname setup.
- Added an in-memory expiration countdown and sensitive-state cleanup.
- Updated `AuthProvider` after successful activation and entered `/app`.
- Kept passwords, activation codes, tokens, and activation state out of
  `localStorage`.

Commit: `7a691c23ef07a9f55ea52785d54d3dcc487895aa`

### Phase 4C — Instructor authentication UI

- Added `/instructor/login` and `/instructor/*`.
- Added Instructor login, session restoration, and logout.
- Added Student/Instructor role routing and role-protected routes.
- Added an Instructor landing page.
- Marked course, roster, and progress tools clearly as upcoming work.
- Did not display fake course or student statistics.

Commit: `d70554ab629be37f60eb96f853e689e7241853eb`

### Phase 6A — Instructor Course Management UI

- Added a PostgreSQL-backed course list.
- Added Create Course.
- Added course data loading, error, and empty states.
- Protected the interface by Instructor role.
- Added a responsive layout.

Commit: `0a44f702d74695e4af214342a522748d5a966c73`

### Phase 6B — Roster Import UI

- Added UTF-8 roster CSV import.
- Kept validation backend-authoritative.
- Added a row-level import summary.
- Added the one-time activation-code CSV download.
- Added no-store/no-cache response validation.
- Kept downloaded results in temporary Blob/Object URLs.
- Protected undownloaded codes from silent overwrite.
- Manually verified the Instructor-to-Student activation flow.

Commit: `5726f5f1fe025fdef436bfbeb95cf82057df1a72`

### Phase 6C — Roster Status and Activation Code Reissue

- Added the real enrollment list and pagination.
- Added Berkeley Username search.
- Added Pending/Activated filtering.
- Displayed activation, enrollment, and account status separately.
- Enforced Instructor course ownership.
- Added activation-code regeneration and old-code invalidation.
- Kept plaintext activation codes out of the database.

Targeted backend tests: `21 passed`

Commit: `0eaa5a72b3d150bbc5954910a016033eda33caaf`

### Instructor navigation UX follow-up

- Corrected Dashboard roster navigation.

Commit: `7bde1b5048ee495d201d6d8629c8b23df168ac99`

### Course-first navigation redesign

- Removed the standalone Instructor Dashboard.
- Made Instructor login open My Courses.
- Made `/instructor` redirect with replace to `/instructor/courses`.
- Kept Create Course only within My Courses.
- Added a reusable breadcrumb hierarchy.
- Moved Student Progress into course-level navigation as Coming later.
- Simplified the header to Instructor identity and Sign Out.

Commit: `ed49e2f3c29f85ef5dba1ce486b6f686f28c305e`

### Unified Course Workspace

- Made a selected course open directly into Roster Management.
- Removed the Overview tab and intermediate Manage Roster page/button.
- Embedded roster content using the course already loaded by the workspace.
- Avoided a duplicate `getInstructorCourse` request.
- Redirected the legacy `/courses/:courseId/roster` URL with replace.
- Kept only these course modules:
  - Roster Management
  - Student Progress — Coming later
- Standardized My Courses, Course Workspace, and Import pages on `max-w-6xl`.
- Added an explicit Back to My Courses control.
- Made Import Cancel return to the unified course workspace.

Commit: `1bf1f25eef283a0961b22a8e8f42cd5676b1ef95`

## 3. Current system capabilities

The current **Instructor Course/Roster Administration MVP** can:

1. Send an Instructor directly to My Courses after login.
2. Let an Instructor create and view courses.
3. Open a selected course directly in Roster Management.
4. Let an Instructor upload a roster CSV.
5. Let an Instructor download activation codes for new enrollments.
6. Let an Instructor view, search, and filter a roster.
7. Show activation, enrollment, and account status.
8. Regenerate a code for an eligible Pending enrollment.
9. Let a Student complete first-time activation and enter the Dashboard.
10. Let a Student sign out and later sign in with a password.
11. Keep Student and Instructor pages isolated.
12. Complete a verified local Instructor-to-Student demo.

## 4. Current milestone

- Authentication backend: complete for current MVP scope.
- Authentication frontend: complete for current MVP scope.
- Instructor Course/Roster Administration MVP: complete.
- Course-first Instructor navigation: complete.
- Instructor-to-Student end-to-end demo: verified.
- Simulation persistence: not yet implemented.
- Student Progress: not yet implemented.
- Overall complete platform estimate: approximately 65–70%.

## 5. Work still required

### Phase 5 — Simulation Persistence

- Add simulation session/run persistence.
- Add monthly policy/result persistence.
- Add cross-browser restoration.
- Add server-side ownership and validation.

### Phase 6D — Optional Enrollment Administration

- Add manual single-student enrollment.
- Add enrollment deactivate/reactivate controls.
- Add additional administrative actions.

### Student Progress

- Keep progress course-scoped.
- Implement it after Simulation Persistence.
- Use only real database data.
- Do not use mock or `localStorage` data.

### Phase 7 — Saved Runs and Analysis

- Persist complete run history and monthly snapshots.
- Link each result to its exact policy version, parameters, warnings, and
  errors.
- Add run-detail and run-comparison pages.
- Add personal best results grouped by equal progress.
- Add CSV, JSON, policy-code, and report exports.

### Phase 8 — Same-Stage and Final Rankings

- Add a Class Progress view that is not a performance ranking.
- Add a formal Same-Stage Comparison:
  - compare students at the same completed month
  - use identical simulation rules and request seeds
  - calculate metrics from the same number of months
- Add a formal Final Leaderboard:
  - require all 12 months
  - require eligibility and valid execution
  - keep courses and semesters isolated
- Define and document ranking metrics and tie-breaking rules.
- Display metric definitions such as VIP admission and completion rates.
- Never expose Berkeley usernames, internal user IDs, or private student data.

### Phase 9 — Security, Operations, and Deployment

- Add production PostgreSQL configuration and migrations.
- Require HTTPS and Secure cookies in production.
- Add CSRF protection where required by the final deployment architecture.
- Add rate limits for login and activation attempts.
- Add audit logging for instructor actions and credential resets.
- Add instructor-managed password reset for the MVP.
- Add database backup and restore procedures.
- Add deployment health checks and CI validation.
- Resolve or formally document the five existing simulation baseline test
  failures.

## 6. Remaining MVP acceptance criteria

The account-system MVP is complete when:

- A student can activate and later log in from another browser.
- Clearing `localStorage` does not delete identity or simulation history.
- Student A cannot access Student B's private records.
- Instructor operations are limited to courses the instructor owns.
- Simulation sessions and monthly results persist in PostgreSQL.
- Instructor course and roster workflows are available in the UI.
- Same-stage and final rankings use only eligible, comparable records.
- Public rankings expose only course nicknames.
- Production configuration contains no committed secrets.
- Database migrations, backend tests, type checks, and frontend builds pass in
  CI, apart from any explicitly documented legacy baseline failures.

## 7. Branch and publishing notes

- Account-system integration work is maintained on
  `integration/main-dashboard-login`.
- Do not commit `.env`, generated review patches, plaintext credentials, or
  one-time activation CSV files.
- Do not rewrite or force-push the shared `integration/main-dashboard` branch.
