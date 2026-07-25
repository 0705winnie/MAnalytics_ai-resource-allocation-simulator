# Account System Implementation Progress

Last updated: July 25, 2026
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
Use `git rev-parse HEAD` to replace this abbreviated display with the exact
local commit hash before publishing this document.

## 3. Current system capabilities

The backend can currently demonstrate:

1. An instructor account signs in securely.
2. The instructor creates a course instance.
3. The instructor imports a roster CSV.
4. The system generates a different one-time activation code for every new
   enrollment.
5. A student verifies their course, username, and activation code.
6. A first-time student creates a global password and course nickname.
7. A returning student confirms the existing global password and chooses a
   nickname for another course.
8. The activation code is consumed and cannot be reused.
9. The student receives a course-scoped authenticated session.
10. Disabled users, disabled enrollments, inactive courses, and inconsistent
    activation states are rejected.

## 4. Work still required

### Phase 3C — Regular student login

- Add login using course code, Berkeley username, and password.
- Resolve the correct enrollment for the selected course.
- Issue a course-scoped Student access cookie.
- Add logout and session-expiration behavior for the Student flow.
- Add login throttling or rate limiting.
- Add tests for multi-course users and disabled states.

### Phase 4 — Authentication user interface

- Build the Student Login page.
- Build the First-Time Activation page.
- Build the Create/Confirm Password and Nickname step.
- Add an application-level auth provider.
- Add protected routes and role-based navigation.
- Add instructor login and logout UI.
- Display safe, actionable errors without revealing whether a roster username
  exists.

### Phase 5 — Move simulation data to PostgreSQL

- Add models and migrations for:
  - simulation sessions
  - monthly results
  - policy versions/submissions
  - warnings and invalid actions
- Bind every record to both the authenticated enrollment and course.
- Add APIs to create, resume, run, and inspect simulations.
- Stop trusting student IDs or course IDs supplied arbitrarily by the browser.
- Keep `localStorage` only for drafts and temporary UI preferences.
- Add a safe transition strategy for existing local prototype data.

### Phase 6 — Instructor administration UI

- Build course creation and course listing screens.
- Build roster upload and one-time activation CSV download.
- Build student/enrollment management.
- Add activation regeneration and enrollment enable/disable controls.
- Add result export for instructors.
- Add clear counts for pending, active, and disabled enrollments.

### Phase 7 — Saved runs and analysis

- Persist complete run history and monthly snapshots.
- Link each result to its exact policy version, parameters, warnings, and
  errors.
- Add run-detail and run-comparison pages.
- Add personal best results grouped by equal progress.
- Add CSV, JSON, policy-code, and report exports.

### Phase 8 — Rankings

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

### Phase 9 — Security, operations, and deployment

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

## 5. Remaining MVP acceptance criteria

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

## 6. Branch and publishing notes

- The completed work currently consists of ten local commits on
  `integration/main-dashboard`.
- Publish these commits from the current local HEAD to
  `integration/main-dashboard-login`.
- Do not commit `.env`, generated review patches, plaintext credentials, or
  one-time activation CSV files.
- Do not rewrite or force-push the shared `integration/main-dashboard` branch.
