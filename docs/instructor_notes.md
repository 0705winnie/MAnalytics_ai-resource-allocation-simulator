# Instructor Notes

## 1. Purpose

These notes describe the intended instructor-facing setup for a persistent
multi-user version of the resource allocation simulator. The focus is course
administration: creating course instances, authorizing students, protecting
student identity on the leaderboard, and exporting course-level results.

These notes are not a student tutorial and are not meant to duplicate dashboard
navigation instructions.

## 2. Course Instance Model

The dashboard should support multiple course offerings over time. Each offering
should be treated as a separate course instance.

Example course instance ids:

```text
IEOR150-Fall2026
IEOR150-Spring2027
```

Each course instance should have its own:

- roster;
- student accounts;
- policy submissions;
- simulation records;
- monthly results;
- leaderboard;
- course-level exports.

This separation is important because the same student may participate in
different offerings, and results from one semester should not mix with results
from another semester.

## 3. Roster-Based Student Access

The first persistent version should use a course-specific login system rather
than Berkeley CalNet or another full single sign-on integration.

The intended access model is roster-based:

1. The instructor creates a course instance.
2. The instructor uploads a roster CSV containing Berkeley usernames for
   enrolled students.
3. The system creates one authorized student record for each username.
4. The system generates an individual temporary activation code for each
   student.

This design avoids using one shared course password. A shared credential would
allow one student to impersonate another student by entering a different
Berkeley username. Individual activation codes or temporary passwords are safer
while still avoiding the complexity of CalNet integration.

## 4. Student First Login Workflow

On first login, a student should provide:

1. course code;
2. Berkeley username;
3. individual activation code.

After successful activation, the student should:

1. create a password;
2. choose a nickname for the leaderboard.

After this first login, the student should use the course code, Berkeley
username, and password to access the dashboard.

## 5. Identity And Leaderboard Privacy

The Berkeley username should be used only for authentication and backend record
linkage. It should not be displayed publicly on the leaderboard.

The nickname is the public identity used in leaderboard views. This allows
students to compare performance while keeping official identities private from
classmates.

The system should maintain a backend mapping between:

```text
course_id
student account
Berkeley username
leaderboard nickname
```

Only the nickname should appear in public leaderboard displays.

## 6. Instructor Dashboard Capabilities

The instructor interface should support:

- creating a new course or semester instance;
- uploading a roster CSV;
- updating the roster if enrollment changes;
- viewing active and inactive students;
- resetting a student's activation code;
- resetting a student's password;
- disabling a student account;
- downloading course-level results.

These functions are administrative. They should be separate from the
student-facing simulation workflow.

## 7. Data Storage Requirements

The backend should be the source of truth for identity and submission history.
Browser local storage may be used for temporary UI state, but it should not be
used as the authoritative record of login status, policy submissions, simulation
history, or leaderboard results.

Every persistent record should be associated with both a course instance and a
student account. This includes:

- simulation sessions;
- policy submissions;
- monthly simulation results;
- benchmark comparisons;
- leaderboard entries;
- timestamps for activity and submissions.

At minimum, each persistent student activity record should include:

```text
course_id
student_id
timestamp
record_type
record_payload
```

The exact database schema can be finalized during backend implementation, but
the course and student linkage should be treated as required.

## 8. Security Requirements

Passwords should never be stored in plaintext. Student passwords should be
stored only as secure password hashes.

Activation codes or temporary passwords should also be stored only as secure
hashes. If raw activation codes are generated for distribution, they should be
shown or exported only at generation time and should not be recoverable later
from the database.

The system should support reset workflows. If a student loses an activation
code or password, the instructor should be able to generate a new activation
code or reset credential without learning the student's current password.

The system should avoid shared course credentials. Shared credentials make it
difficult to prevent impersonation and make it harder to audit submissions.

## 9. Course Results Export

The instructor should be able to download course-level results for review,
grading, or discussion.

Useful export contents include:

- course id;
- student identifier used internally by the system;
- leaderboard nickname;
- month reached;
- latest submission timestamp;
- cumulative revenue or payoff;
- admissions;
- rejections;
- unfinished requests;
- VIP completion rate or priority-service metric;
- benchmark comparison fields;
- final policy submission or policy version reference.

Exact export columns can be finalized with the backend and dashboard
implementation, but exports should preserve the link between course instance,
student account, submissions, and results.

## 10. Open Implementation Details

The following details should be finalized during backend and dashboard
implementation:

- exact roster CSV schema;
- activation-code distribution format;
- password reset workflow;
- instructor authentication method;
- instructor permission model;
- exact database schema;
- exact export file format;
- policy-version storage format;
- retention policy for old course instances.
