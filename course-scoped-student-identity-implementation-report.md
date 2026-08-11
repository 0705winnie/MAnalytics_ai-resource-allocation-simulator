# Course-Scoped Student Identity Implementation Report

Status: implemented in the local worktree for review. No commit, push, deploy, Neon access, or production migration was performed.

## A. Current root cause of Existing Password behavior

Before this change, `users.berkeley_username` was globally unique and `password_hash` lived on that global User row. Roster import looked up that global username and reused the User across courses. Activation looked up an enrollment by course plus username, but then inspected the shared User password hash. Once the first enrollment set a password, activation for another enrollment with the same username selected the “confirm existing password” path.

The behavior was therefore caused by a mismatch between course-scoped enrollments and a globally shared Student credential row. It was not a browser password-manager issue.

## B. Chosen course-specific Student identity model

The selected model keeps one `users` table with two scopes:

- Instructor: global account, `users.course_id IS NULL`.
- Student: course-scoped account, `users.course_id IS NOT NULL`.
- Student steady state: one User to one Enrollment to one Course.

The database uses:

- a partial unique index on `(course_id, berkeley_username)` for Students;
- a partial unique index on `berkeley_username` for Instructors;
- a unique constraint on `enrollments.user_id`;
- a composite enrollment foreign key `(user_id, course_id) -> users(id, course_id)`;
- a role/scope check requiring Student course scope and prohibiting Instructor course scope.

This avoids duplicating usernames on Enrollment as a competing identity source. Instructor ownership and global Instructor login remain unchanged.

## C. Database/model changes

- Added nullable `users.course_id`, with a restrictive foreign key to `course_instances`.
- Removed global username uniqueness.
- Added separate Student and Instructor partial unique indexes.
- Added the Student role/course-scope check.
- Added `users(id, course_id)` uniqueness to support the composite Enrollment foreign key.
- Replaced `uq_enrollments_course_user` with `uq_enrollments_user_id`.
- Added `course_instances.semester_normalized` as a generated lowercase/trimmed column.
- Replaced global normalized Course Code uniqueness with normalized Course Code plus normalized Semester uniqueness.
- ORM relationships explicitly disambiguate Instructor-created courses from Student account scope. SQLAlchemy mapper configuration passes without relationship warnings.

## D. Course uniqueness implementation

Course uniqueness is now enforced at the database level by:

`(course_code_normalized, semester_normalized)`

Both normalized columns ignore surrounding spaces and case. Thus `ieor150 + 2026fall` conflicts with `IEOR150 + 2026FALL`, while `IEOR150 + 2027SPRING` is allowed.

The Create Course API and UI now use the approved conflict message:

> This Course Code and Semester combination already exists. Please modify one of the fields and try again.

## E. Course ID generation/normalization

Course ID is derived, not stored as an independently editable field:

`normalized Course Code + "-" + normalized Semester`

The shared backend helper trims and uppercases both components. Course creation stores canonical uppercase/trimmed components. Authentication queries use the generated normalized database columns, making lookup case- and surrounding-space-insensitive.

Example: `ieor150` and `2026fall` produce `IEOR150-2026FALL`.

## F. Student Login changes

Student Login now sends and accepts:

- Course ID
- Berkeley Username
- Password

The backend resolves the exact Course, Student User, and Enrollment using normalized Course ID plus normalized username. It also requires `User.course_id` to match the selected Course. Password verification retains the constant-shape dummy-hash path and the generic error:

> Invalid course, username, or password

The access token still contains exact `user_id`, `course_id`, and `enrollment_id` claims. `/api/auth/me` now additionally verifies that `users.course_id` matches the token course claim.

## G. Student Activation changes

Activation verification now accepts Course ID, Berkeley Username, and Activation Code. The response no longer contains a create/confirm password mode.

Completion always hashes the submitted New Password into the course-specific Student User row. It never asks for or verifies a password belonging to another course account. The frontend always shows:

- New Password
- Confirm Password
- Leaderboard Nickname

Both password fields use `autocomplete="new-password"`. The UI no longer contains “Existing Password,” “Current Password,” or global Student-password language. Activation token restoration also validates `users.course_id` against the exact token course.

## H. Roster/import changes

Roster import now searches only Student users whose `course_id` is the target Course. It does not reuse a global User with the same username.

- First import in Course A creates a Course A Student User and Enrollment.
- Import of the same username in Course B creates a different User and Enrollment.
- Reimport in the same Course is reported as already enrolled; database constraints provide final race protection.
- A global Instructor with the same username is not reused as a Student.

New Student users are created with `password_hash=NULL`, the target `course_id`, a pending Enrollment, a Simulation Session, and a one-time activation code.

## I. Existing account migration behavior

Revision `0006` processes every legacy Student User:

1. Enrollment rows are ordered deterministically by creation time and ID.
2. The original User row is assigned to the first Enrollment’s Course.
3. A new Student User row is created for every additional Enrollment.
4. Each additional Enrollment is repointed to its new User.
5. Legacy orphan Student users are removed after their ambiguous AI usage is removed.
6. Instructor rows are left global and unchanged.

Enrollment IDs do not change.

## J. Password-hash migration behavior

The migration copies the existing `password_hash` value to every split Student User row. It never reads, reconstructs, logs, or exports plaintext passwords.

Immediately after migration, split active accounts may accept the same former password because the hashes are identical. They are independent rows: a later password change to one course account does not update another course account. For pending accounts, successful activation replaces that course account’s copied hash with the newly submitted password hash.

## K. Nickname migration behavior

Nickname and nickname uniqueness remain on Enrollment. Because Enrollment rows and IDs are preserved, each course’s nickname, activation hash, activation expiry, activation-used timestamp, status, and creation timestamps remain associated with the same Course.

## L. Simulation/history migration behavior

The implementation preserves:

- Simulation Sessions: preserved, because `simulation_sessions.enrollment_id` is unchanged.
- Monthly Results: preserved, because Simulation Session IDs are unchanged.
- Leaderboard progress: preserved, because it derives from the preserved Enrollment/Session/Monthly Result chain.
- Legacy Submissions: preserved, because Enrollment IDs are unchanged.
- Student AI usage: reset during `0006`.

Student AI usage is deliberately reset because a legacy `llm_daily_usage.user_id` row belongs to the formerly shared cross-course User and cannot be assigned to one split course account without inventing an allocation. Instructor usage rows, if any, are not reset.

No simulation engine or persistence behavior was redesigned.

## M. AI quota implications

The quota schema remains `user_id + usage_date`. After migration, Course A/abc123 and Course B/abc123 have different User IDs and therefore independent daily quotas. No username-shared or enrollment-shared quota was added.

The Student AI context remains scoped through the authenticated User, Enrollment, and Course.

## N. Remove Student behavior

Removing a Student from an owned Course now deletes, in dependency order:

- that Enrollment’s Monthly Results;
- Simulation Session;
- legacy Submission rows;
- Enrollment;
- that course-specific User’s AI usage;
- that course-specific Student User.

The deletion is constrained by owned `course_id`, enrollment ID, Student role, and the Student User’s matching `course_id`. Instructor users are not eligible for deletion.

## O. Delete Course behavior

Deleting an owned Course now removes:

- Monthly Results;
- Simulation Sessions;
- legacy Submissions;
- Enrollments;
- AI usage belonging to Student users scoped to that Course;
- all Student users scoped to that Course, including any abnormal orphan;
- the Course.

The creating Instructor remains. A Student account with the same Berkeley Username in another Course has a different User ID/course scope and remains untouched.

## P. Activation export/instructor notice

Roster and regenerated-code CSV files now use these identity columns:

- `berkeley_username`
- `course_id`
- `activation_code`

Course ID is generated by the backend; the Instructor does not concatenate fields manually. CSV formula-injection protection remains.

The import-result and regenerated-code UIs now instruct:

> Send students their Berkeley Username, Course ID, and Activation Code together.

## Q. History UI/privacy changes

Student History retains monthly summary counts, revenue, utilization, warnings, benchmark/policy status, and policy snapshots.

It now:

- removes the complete Remaining Capacity section;
- shows By Type as request type plus revenue only;
- does not show type-level total, admitted, or completed counts.

The official Student session/history response no longer contains `remaining_capacity`. Its monthly and cumulative `by_type` entries contain only `type` and `total_revenue`. The persisted database field remains available to internal simulation persistence; simulation engine behavior is unchanged.

## R. AI context privacy changes

`StudentAIContextAssembler` now explicitly maps only:

- visible monthly/cumulative summary metrics;
- `by_type_revenue` containing type and revenue only;
- visible utilization;
- warnings;
- the Student’s own policy/history.

It does not serialize the stored Remaining Capacity snapshot. A focused test asserts that `remaining_capacity` is absent and that By Type context contains only type and revenue.

## S. Migration revision created

- Revision: `0006_course_scoped_students`
- Parent: `0005_llm_daily_usage`
- `alembic heads`: `0006_course_scoped_students (head)`
- Number of heads: one

Downgrade is guarded. It succeeds only while usernames and Course Codes can still satisfy the old global uniqueness rules. Once course-specific duplicate usernames or repeated Course Codes exist, it refuses rather than silently merging accounts, choosing a password, or losing course identity.

## T. Focused test results

Passed:

- `PYTHONPATH=backend python -m pytest -q backend/tests/test_course_identity.py backend/tests/test_student_ai_context.py`
  - Result: 5 passed.
- Explicit Python compilation of all changed backend/model/router/service/schema/migration files.
  - Result: passed.
- SQLAlchemy `configure_mappers()`.
  - Result: passed without relationship warnings.
- `python -m alembic heads`.
  - Result: one `0006` head.
- Static metadata inspection.
  - Result: expected composite constraints, role-scope check, and partial indexes are present.

Added/updated focused coverage for:

- canonical Course ID generation and shared login/activation normalization;
- absence of Existing Password mode;
- multi-enrollment migration splitting, password-hash copying, nickname preservation, independent User IDs/password rows/AI usage, Instructor preservation, Session preservation, normalized course combination uniqueness, and same-code/different-semester allowance;
- Student History API exclusion of Remaining Capacity and detailed per-type counts;
- AI-context exclusion of hidden capacity;
- History UI absence of Remaining Capacity and completed/total type fractions;
- activation CSV Course ID columns.

Not completed in this environment:

- The disposable local PostgreSQL migration run was attempted only against explicit localhost port 55432 and a database ending in `_test`. Sandbox networking denied the connection. The required escalation was then rejected because the tool account reached its usage limit. No alternate path was used, and Neon was not contacted.
- Focused Vitest entered the known local pre-test startup stall; it was stopped after 60 seconds with no test case executed.
- `npm run build` entered the known local TypeScript/toolchain stall with no compiler output; it was stopped after 60 seconds.
- `git diff --check` and full pytest collection also stalled on local filesystem reads and were stopped. No orphaned managed exec session remains.

Therefore the migration fixture exists but its PostgreSQL execution result is still pending. A clean local/CI/Render build must be required before approval to deploy.

## U. Exact files changed

Backend implementation:

- `backend/alembic/versions/0006_course_scoped_student_accounts.py`
- `backend/app/models/user.py`
- `backend/app/models/course_instance.py`
- `backend/app/models/enrollment.py`
- `backend/app/core/auth.py`
- `backend/app/core/activation_auth.py`
- `backend/app/schemas/auth.py`
- `backend/app/schemas/activation.py`
- `backend/app/schemas/simulation_sessions.py`
- `backend/app/routers/auth.py`
- `backend/app/routers/activation.py`
- `backend/app/routers/instructor_courses.py`
- `backend/app/services/course_identity.py`
- `backend/app/services/student_authentication.py`
- `backend/app/services/activation_verification.py`
- `backend/app/services/activation_completion.py`
- `backend/app/services/roster_imports.py`
- `backend/app/services/instructor_enrollments.py`
- `backend/app/services/course_deletions.py`
- `backend/app/services/simulation_persistence.py`
- `backend/app/services/student_ai_context.py`

Backend tests:

- `backend/tests/test_course_identity.py`
- `backend/tests/test_migrations.py`
- `backend/tests/test_instructor_courses.py`
- `backend/tests/test_instructor_roster.py`
- `backend/tests/test_instructor_enrollments.py`
- `backend/tests/test_official_simulation.py`
- `backend/tests/test_student_ai_context.py`

Frontend implementation/tests:

- `src/auth/types.ts`
- `src/auth/api.ts`
- `src/components/NavBar.tsx`
- `src/instructor/types.ts`
- `src/instructor/api.ts`
- `src/instructor/InstructorBreadcrumbs.tsx`
- `src/instructor/InstructorRosterManagement.tsx`
- `src/instructor/InstructorLeaderboards.test.tsx`
- `src/pages/StudentLoginPage.tsx`
- `src/pages/StudentActivationPage.tsx`
- `src/pages/InstructorCourseCreatePage.tsx`
- `src/pages/InstructorCoursesPage.tsx`
- `src/pages/InstructorCourseDetailPage.tsx`
- `src/pages/InstructorRosterImportPage.tsx`
- `src/pages/SimulationPage.tsx`
- `src/pages/SimulationPage.test.tsx`
- `src/types/simulation.ts`
- `src/test/fixtures.ts`

Report:

- `course-scoped-student-identity-implementation-report.md`

## V. Ambiguous or risky issues requiring approval

1. Production execution of `0006` must not be approved until the migration test runs successfully on a disposable PostgreSQL database and the migrated schema is inspected.
2. Resetting all legacy Student `llm_daily_usage` is intentional and documented. Approval should explicitly accept that reset; simulation sessions, monthly results, leaderboard progress, nicknames, and legacy submissions are preserved.
3. A direct production downgrade becomes unsafe once duplicate cross-course usernames, repeated Course Codes, or independent passwords exist. The migration refuses such a downgrade. Recovery should use a reviewed forward migration or database restore, not stamp/drop/manual merge operations.
4. The full legacy backend suite contains fixtures built around the old “Student before Course/global Student” model. Focused tests were updated/added, but a full successful integration run is still required to locate and update every obsolete fixture before deployment.
5. Local Vitest/build stalls remain an environment/toolchain issue. Deployment approval should require a clean frontend build and focused UI test in a clean environment.

Production remains unchanged at revision `0005_llm_daily_usage` until an explicitly approved deployment runs the reviewed migration.
