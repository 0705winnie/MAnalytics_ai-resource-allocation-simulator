# Course Account and Data Persistence System Design

**Project:** AI Resource Allocation Simulator  
**Document version:** 1.0  
**Status:** Requirements confirmed  
**Last updated:** 2026-07-24

## 1. Purpose

This document defines the account, course, data persistence, run history, and
leaderboard design for the AI Resource Allocation Simulator before
implementation begins.

The system will replace the current browser-only identity and history model with
a course-specific backend account system. PostgreSQL will be the source of truth
for accounts, simulation runs, monthly results, policy versions, warnings, and
leaderboard records.

## 2. Confirmed Product Decisions

| Decision | Confirmed choice |
|---|---|
| Authentication model | Course-specific accounts; no Berkeley CalNet/SSO |
| Student authorization | Instructor-uploaded roster |
| First-time login | Individual one-time activation code |
| Database | PostgreSQL only |
| Public identity | Course-specific leaderboard nickname |
| Credential storage | Passwords and activation codes stored only as secure hashes |
| Data ownership | Every business record is associated with a course and student enrollment |
| Same-stage comparison | Included in the MVP and treated as a formal ranking |
| Final leaderboard | Only eligible 12-month runs are ranked |
| Multiple runs | Practice runs are allowed; the student selects one final submission |
| Default ranking | Revenue by default, with other sortable metrics |
| Password reset | Instructor generates a one-time reset code |
| Nickname changes | Instructor reset only in the MVP |
| Activation expiry | 14 days |
| Student export | CSV/JSON plus policy code |
| Prototype data | No migration of old localStorage records; production begins with an empty database |
| VIP metrics | Show both admission rate and post-admission completion |
| Invalid actions | Penalized in scoring; they do not automatically remove ranking eligibility |

## 3. Scope

### 3.1 Goals

- Provide an independent account for every enrolled student.
- Support multiple course instances and semesters.
- Connect identity, simulation progress, policies, results, warnings, and
  leaderboard records.
- Allow students to recover saved work after clearing localStorage or changing
  browsers.
- Protect student identity by displaying only nicknames on public course
  rankings.
- Give instructors course, roster, account, progress, reset, and export tools.
- Provide both same-stage and final formal rankings.

### 3.2 Not included in the MVP

- Berkeley CalNet/SSO.
- Multi-factor authentication.
- Automatic email delivery of activation or password-reset codes.
- Self-service email password recovery.
- School-wide administrators or complex instructor permission hierarchies.
- Real-time WebSocket leaderboard updates.

## 4. MVP Definition

MVP means **Minimum Viable Product**: the smallest first version that completes
the full workflow and can be used and demonstrated reliably.

The account-system MVP must support:

1. Instructor login.
2. Course creation.
3. Roster CSV upload.
4. Individual activation-code generation.
5. Student account activation.
6. Password and nickname creation.
7. Student login and logout.
8. PostgreSQL persistence of runs, policies, results, and warnings.
9. Cross-browser recovery of submitted data.
10. Instructor student-management tools.
11. Same-stage formal leaderboards.
12. The final 12-month leaderboard.

## 5. Roles and Permissions

### 5.1 Student

A student can:

- Activate an account using a course code, Berkeley username, and activation
  code.
- Create a password and course nickname.
- Log in and log out.
- Create practice runs.
- Save monthly policies and simulation results.
- View personal run history and warnings.
- Select one completed run as the final submission.
- View same-stage and final course leaderboards.
- Export personal results as CSV or JSON and download policy code.

A student cannot:

- Read or modify another student's private runs.
- Access instructor pages.
- provide an arbitrary student or enrollment ID to change data ownership.
- See another student's Berkeley username through a leaderboard API.

### 5.2 Instructor

An instructor can:

- Create and deactivate course instances.
- Upload or update a roster.
- Download newly generated activation codes.
- View enrollment and activation status.
- Generate a new activation code.
- Generate a one-time password-reset code.
- Disable or reactivate an enrollment.
- Reset an inappropriate or conflicting nickname.
- View course progress.
- Export course-level simulation results.

## 6. User Workflows

### 6.1 Instructor course and roster setup

1. The instructor logs in.
2. The instructor creates a course instance, such as
   `IEOR150-Fall2026`.
3. The instructor uploads `roster.csv`.
4. The backend trims, normalizes, validates, and deduplicates usernames.
5. The system creates missing users and course enrollments.
6. The system generates a different activation code for every new enrollment.
7. Plaintext codes appear only in the one-time import result.
8. The instructor downloads the activation CSV and distributes codes through
   an approved course channel.

Minimum roster format:

```csv
berkeley_username
yguo
abc123
wenchia
```

One-time activation export:

```csv
berkeley_username,course_code,activation_code,status
yguo,IEOR150-Fall2026,K7QX-4M9P-2DLC,created
```

### 6.2 Student first-time activation

The student enters:

```text
Course Code
Berkeley Username
Activation Code
```

The backend verifies:

1. The course exists and is active.
2. The username is in the course roster.
3. The user and enrollment are active.
4. The activation code has not been used.
5. The activation code has not expired.
6. The submitted code matches the stored hash.

After successful verification, the backend issues a short-lived activation
token. The student then enters:

```text
Password
Confirm Password
Leaderboard Nickname
```

The backend hashes the password, marks the activation code as used, saves the
course nickname, and starts an authenticated session.

### 6.3 Subsequent login

The student enters:

```text
Course Code
Berkeley Username
Password
```

The backend resolves and validates the combined:

```text
user + course instance + enrollment
```

The frontend then calls `GET /api/auth/me` and loads the authenticated
student's records from PostgreSQL.

### 6.4 Password reset

The MVP uses an instructor-assisted reset:

1. The instructor selects the enrollment.
2. The system generates a one-time reset code.
3. The old unused reset code is invalidated.
4. The student enters the reset code and creates a new password.
5. The reset code is marked as used.

The instructor never sees the student's old or new password.

## 7. System Architecture

```text
React/Vite frontend
        ↓
FastAPI endpoints
        ↓
Authentication and authorization layer
        ↓
Course, run, and leaderboard services
        ↓
SQLAlchemy ORM + Alembic migrations
        ↓
PostgreSQL
```

### 7.1 Required database software and libraries

PostgreSQL is the only database engine required. SQLite and MySQL are not
required.

| Component | Purpose | Required |
|---|---|---|
| PostgreSQL | Stores all persistent system data | Yes |
| SQLAlchemy | Python ORM used by FastAPI | Yes |
| Alembic | Database schema migrations | Yes |
| psycopg | PostgreSQL Python driver | Yes |
| pgAdmin or DBeaver | Optional graphical database management | No |
| Docker | Optional local PostgreSQL environment | No |

The backend package set should include:

```text
fastapi
sqlalchemy
alembic
psycopg
pwdlib[argon2]
pyjwt[crypto]
```

## 8. Data Model

### 8.1 `users`

Stores the global account.

```text
id
berkeley_username
password_hash
role
is_active
created_at
updated_at
```

`berkeley_username` is globally unique after normalization.

### 8.2 `course_instances`

Represents a course and semester.

```text
id
course_code
course_name
semester
created_by
is_active
created_at
updated_at
```

`course_code` is unique.

### 8.3 `enrollments`

Connects a user with a course.

```text
id
course_id
user_id
nickname
activation_code_hash
activation_expires_at
activation_used_at
status
created_at
updated_at
```

Required constraints:

```text
UNIQUE(course_id, user_id)
UNIQUE(course_id, normalized_nickname)
```

Nickname rules:

- Unique within a course.
- 3–30 characters.
- May contain letters, numbers, spaces, and hyphens.
- Must not expose the Berkeley username.
- Instructor reset only in the MVP.

### 8.4 `password_reset_tokens`

```text
id
user_id
course_id
reset_code_hash
expires_at
used_at
created_by
created_at
```

### 8.5 `simulation_sessions`

Represents one practice or final-candidate run.

```text
id
course_id
enrollment_id
run_name
run_type
simulation_version
seed_group
status
completed_months
total_revenue
created_at
updated_at
completed_at
```

`run_type` begins as `practice`. A completed run can later be selected through
`final_submissions`.

### 8.6 `monthly_results`

```text
id
session_id
month
vip_arrivals
vip_admitted
vip_completed
vip_rejected
regular_arrivals
regular_admitted
regular_completed
regular_rejected
unfinished_count
unfinished_value
revenue
warning_count
invalid_action_count
total_action_count
created_at
```

Required constraint:

```text
UNIQUE(session_id, month)
```

### 8.7 `policy_versions`

```text
id
session_id
month
version_number
policy_code
parameters_json
validation_status
created_at
```

Multiple policy versions may exist for the same month, but the monthly result
must identify the exact executed version.

### 8.8 `run_events`

Stores traceable warnings, errors, and invalid actions.

```text
id
session_id
month
severity
event_type
message
action_payload_json
created_at
```

### 8.9 `final_submissions`

```text
id
course_id
enrollment_id
session_id
submitted_at
eligibility_status
score_snapshot_json
```

An enrollment can have multiple practice runs but only one active final
submission for a course.

### 8.10 `admin_audit_events`

```text
id
actor_user_id
course_id
target_enrollment_id
event_type
event_metadata_json
created_at
```

This table records roster imports, activation resets, password resets,
enrollment status changes, nickname resets, and exports. Secret values must not
be recorded.

## 9. Data Ownership Rules

- Every enrollment belongs to exactly one user and one course.
- Every simulation session belongs to one enrollment and one course.
- The session `course_id` must match `enrollment.course_id`.
- Monthly results, policies, and events inherit ownership through the session.
- The backend derives ownership from the authenticated session.
- The backend must not trust `user_id`, `student_id`, or `enrollment_id`
  provided by the student client.
- Cross-course and cross-student access must return `403` or privacy-preserving
  `404` responses.
- Disabling an account or enrollment does not delete its historical records.

## 10. API Design

### 10.1 Authentication

```text
POST /api/auth/activate/verify
POST /api/auth/activate/complete
POST /api/auth/login
POST /api/auth/logout
POST /api/auth/password-reset/verify
POST /api/auth/password-reset/complete
GET  /api/auth/me
```

### 10.2 Instructor

```text
POST  /api/instructor/courses
GET   /api/instructor/courses
POST  /api/instructor/courses/{course_id}/roster
GET   /api/instructor/courses/{course_id}/students
POST  /api/instructor/enrollments/{enrollment_id}/reset-activation
POST  /api/instructor/enrollments/{enrollment_id}/reset-password
POST  /api/instructor/enrollments/{enrollment_id}/reset-nickname
PATCH /api/instructor/enrollments/{enrollment_id}/status
GET   /api/instructor/courses/{course_id}/results/export
```

### 10.3 Simulation and history

```text
POST /api/courses/{course_id}/sessions
GET  /api/courses/{course_id}/sessions
GET  /api/sessions/{session_id}
POST /api/sessions/{session_id}/months/run
GET  /api/sessions/{session_id}/months
GET  /api/sessions/{session_id}/events
POST /api/sessions/{session_id}/final-submit
GET  /api/sessions/{session_id}/export
```

Running a month must save the policy version, monthly result, run events, and
session summary in one PostgreSQL transaction.

### 10.4 Rankings

```text
GET /api/courses/{course_id}/progress
GET /api/courses/{course_id}/leaderboards/stage/{month}
GET /api/courses/{course_id}/leaderboards/final
```

Public ranking responses may contain:

```text
nickname
rank
stage_month
revenue
overall_completion
vip_admission_rate
vip_completion_after_admission
unfinished_value
invalid_action_rate
warning_count
utilization_balance
score
```

They must not contain:

```text
berkeley_username
email
user_id
enrollment_id
```

## 11. Security Design

### 11.1 Password and code storage

- Use Argon2id through `pwdlib`.
- Never store plaintext passwords, activation codes, or reset codes.
- Do not use plain SHA-256 for passwords.
- Activation and reset codes are generated with Python `secrets`.
- A newly generated code immediately invalidates the previous unused code.

### 11.2 Activation rules

- Activation code expiration: 14 days.
- Activation code: one-time use.
- Successful activation marks the code as used.
- Repeated failed attempts are rate-limited.
- Authentication failures use general messages that do not reveal whether a
  username exists.

### 11.3 Login session

- Use a short-lived signed access token or server-side session.
- Store the browser credential in an `HttpOnly` cookie.
- Use `SameSite=Lax` or stricter.
- Enable `Secure` in HTTPS production.
- Do not store long-term authentication credentials in localStorage.

### 11.4 Authorization

Every protected endpoint verifies:

1. Current authenticated user.
2. Current role.
3. Active course.
4. Active enrollment or instructor authorization.
5. Resource ownership.

### 11.5 Environment secrets

Database credentials, signing secrets, and service keys must be stored in
environment variables and must not be committed to Git.

## 12. localStorage Policy

localStorage may contain:

- Current page.
- UI preferences.
- Unsaved policy drafts, with a clear unsaved warning.
- Temporary non-sensitive form state.

PostgreSQL must contain:

- Accounts and enrollments.
- Authentication status.
- Simulation sessions.
- Monthly results.
- Policy versions.
- Warnings, runtime errors, and invalid actions.
- Saved runs and final submissions.
- Leaderboard snapshots and eligibility.

Old prototype localStorage data will not be migrated. The production account
system will begin with an empty PostgreSQL database.

## 13. Progress and Ranking Design

The page must clearly separate progress information from formal strategy
rankings.

### 13.1 My Progress

Shows:

- Current runs.
- Completed months.
- Latest saved policy.
- Warnings and invalid actions.
- Personal best at each stage.
- Final-submission status.

This is not a class ranking.

### 13.2 Class Progress

Shows:

- Student nickname.
- Months completed.
- In-progress or completed status.
- Class median completed month.
- Number of students who completed all 12 months.

Class Progress is not ordered by revenue and is not a strategy ranking.

### 13.3 Same-Stage Formal Leaderboard

Same-stage ranking is included in the MVP.

Available stages:

```text
Month 1 Leaderboard
Month 2 Leaderboard
...
Month 12 Leaderboard
```

A student at Month 4 is compared with the Month 4 snapshots of other students,
including the first four months of students who later continued further.

The stage leaderboard:

- Uses metrics accumulated only through the selected month.
- Uses the same simulation version and comparable seed rules.
- Displays a formal stage rank.
- Defaults to revenue ranking.
- Allows sorting by other approved metrics.
- Applies the invalid-action scoring penalty through that stage.
- Never compares four-month total revenue directly with twelve-month total
  revenue.

### 13.4 Final Performance Leaderboard

The final leaderboard includes only:

- A student-selected final submission.
- All 12 months completed.
- A comparable simulation version and seed group.
- No fatal runtime failure.
- Compliance with course submission and deadline rules.

Invalid actions do not automatically disqualify an otherwise completed run.
They reduce its score under the scoring formula.

### 13.5 Ranking metrics

Default display and sorting options:

```text
Revenue
Overall Completion
VIP Admission Rate
VIP Completion after Admission
Unfinished Value
Invalid Action Rate
Warning Count
Utilization Balance
Composite Score
```

The default rank order is Revenue. The page allows users to sort by the other
approved metrics.

### 13.6 VIP metrics

Two metrics will be shown:

```text
VIP Admission Rate
= admitted VIP requests / all VIP arrivals
```

```text
VIP Completion after Admission
= completed VIP requests / admitted VIP requests
```

The raw counts must also remain traceable:

```text
VIP arrivals
VIP admitted
VIP completed
VIP rejected
```

### 13.7 Invalid-action ranking rule

Confirmed rule:

- A fatal runtime error makes the affected stage/run ineligible.
- Nonfatal invalid actions do not automatically remove eligibility.
- Invalid actions are rejected safely by the simulator and recorded.
- Invalid actions reduce the ranking score.
- The leaderboard displays the invalid-action rate.

```text
Invalid Action Rate
= invalid action attempts / total action attempts
```

The exact penalty formula must be frozen with the simulation-scoring owners
before implementation. A proposed starting formula is:

```text
invalid_action_penalty
= invalid_action_rate × penalty_weight
```

The same formula must be used consistently for all students in the course and
for every comparable stage.

## 14. Frontend Pages

```text
/login
/activate
/activate/complete
/password-reset
/dashboard
/profile
/leaderboards/stage/:month
/leaderboards/final
/instructor
/instructor/courses/:courseId
```

Recommended files:

```text
src/pages/LoginPage.tsx
src/pages/ActivationPage.tsx
src/pages/CreateAccountPage.tsx
src/pages/PasswordResetPage.tsx
src/pages/StageLeaderboardPage.tsx
src/pages/FinalLeaderboardPage.tsx
src/pages/InstructorDashboard.tsx
src/auth/AuthProvider.tsx
src/auth/ProtectedRoute.tsx
```

The frontend calls `GET /api/auth/me` during application startup. Unauthenticated
users are redirected to `/login`. Students attempting to access instructor
pages receive a `403` response or an authorized redirect.

## 15. Error Handling

Recommended stable API error codes:

| HTTP | Error code | User-facing behavior |
|---|---|---|
| 400 | `INVALID_INPUT` | Ask the user to check the input format |
| 401 | `INVALID_CREDENTIALS` | Do not reveal which credential was wrong |
| 403 | `ACCOUNT_DISABLED` | Explain that the account is unavailable |
| 403 | `FORBIDDEN` | Do not return protected data |
| 409 | `NICKNAME_TAKEN` | Ask the student to choose another nickname |
| 409 | `DUPLICATE_MONTH` | Prevent accidental double-save |
| 410 | `ACTIVATION_EXPIRED` | Ask the student to contact the instructor |
| 429 | `TOO_MANY_ATTEMPTS` | Temporarily block repeated attempts |

Internal database errors, token details, stack traces, and security-sensitive
information must not be returned to the browser.

## 16. Nonfunctional Requirements

- **Consistency:** A monthly run is saved atomically.
- **Isolation:** Cross-course and cross-student access is blocked.
- **Recovery:** Submitted data survives browser refresh, localStorage clearing,
  and browser changes.
- **Auditability:** Final submission and instructor actions have timestamps and
  actors.
- **Schema management:** All PostgreSQL changes use Alembic migrations.
- **Usability:** Login, activation, roster import, and reset errors are
  actionable.
- **Testability:** Authentication, ownership, ranking eligibility, and metric
  formulas have automated tests.
- **Privacy:** Public course results expose nicknames only.

## 17. Implementation Phases

### Phase 1: PostgreSQL foundation

- PostgreSQL configuration.
- SQLAlchemy models.
- Alembic migrations.
- User, course, and enrollment constraints.
- Development instructor seed account.

**Exit condition:** The database can be created from migrations.

### Phase 2: Roster and authentication

- Course creation.
- CSV roster import.
- Activation-code generation.
- Account activation.
- Login, logout, and `/auth/me`.
- One-time password reset.
- Protected frontend routes.

**Exit condition:** The complete account workflow works.

### Phase 3: Persistent simulation data

- Simulation sessions.
- Monthly results.
- Policy versions.
- Run events.
- Final submissions.
- Replace localStorage as the source of truth.

**Exit condition:** Submitted data can be recovered in another browser.

### Phase 4: Instructor administration

- Course dashboard.
- Enrollment status.
- Reset and disable operations.
- Nickname reset.
- Course export.
- Audit events.

**Exit condition:** The instructor can manage the course without direct
database edits.

### Phase 5: Formal rankings

- Class Progress.
- Same-stage formal leaderboards.
- Final leaderboard.
- Metric definitions and tooltips.
- Invalid-action penalty.
- Sorting and personal-best views.

**Exit condition:** Stage and final rankings are fair, isolated by course, and
reproducible.

### Phase 6: Security and release validation

- Rate limiting.
- Authorization tests.
- End-to-end tests.
- Deployment configuration.
- HTTPS cookie settings.

**Exit condition:** All MVP acceptance tests pass.

## 18. MVP Acceptance Tests

1. The instructor creates `IEOR150-Fall2026`; a duplicate course code is
   rejected.
2. A roster with three usernames produces three different one-time activation
   codes.
3. A student activates only when the course, username, and activation code
   match.
4. Expired, incorrect, and previously used activation codes fail safely.
5. A student creates a password and a course-unique nickname.
6. The student logs in and saves a Month 1 result.
7. The saved result is traceable to the executed policy, parameters, warnings,
   and invalid actions.
8. Another student cannot read or modify that private run, even after changing
   request IDs.
9. Clearing localStorage does not delete submitted records.
10. Logging in from another browser restores submitted records.
11. The instructor can see enrollment status and course progress.
12. The public ranking API returns nicknames but not Berkeley usernames.
13. A Month 4 run is ranked only against Month 4 snapshots.
14. Same-stage ranking is available in the MVP.
15. A four-month run is not compared with a twelve-month run by raw total
    revenue.
16. Only eligible student-selected twelve-month final submissions enter the
    final leaderboard.
17. A nonfatal invalid action reduces score but does not automatically remove
    eligibility.
18. A fatal runtime error makes the affected stage/run ineligible.
19. A disabled enrollment cannot log in, but its authorized historical records
    remain.
20. Instructor export contains data only from the selected course.

## 19. Final Decision Record

| ID | Decision | Selection |
|---|---|---|
| D-01 | Multiple full-year runs | **A:** Practice runs plus one student-selected final submission |
| D-02 | Default leaderboard order | **B:** Revenue by default with sortable metrics |
| D-03 | Same-stage leaderboard timing | **A:** Included in the MVP |
| D-04 | Password reset | **A:** Instructor-generated one-time reset code |
| D-05 | Nickname changes | **B:** Instructor reset only in the MVP |
| D-06 | Activation-code expiration | **B:** 14 days |
| D-07 | Student export | **A:** CSV/JSON plus policy code |
| D-08 | Prototype localStorage migration | **B:** No migration; start with an empty production database |
| D-09 | VIP metric | **C:** Show admission and post-admission completion separately |
| D-10 | Invalid-action eligibility | **C:** Fatal errors disqualify; nonfatal invalid actions produce a score penalty |

## 20. Remaining Formula Confirmation

The product decisions are confirmed. Before coding the ranking score, the team
must still provide or approve:

1. Composite-score metric weights.
2. Invalid-action penalty weight.
3. The definition of a fatal runtime error.
4. Warning categories that are informational versus score-affecting.
5. Seed/configuration rules for comparable runs.

These are simulation and scoring parameters rather than unresolved account
system requirements. They should be stored in course/simulation configuration
instead of hard-coded in the frontend.
