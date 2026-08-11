# Approved Product Changes — Implementation and Deployment Report

Date: 2026-08-11

Status: implementation and focused local verification complete; Render deployment, production migration, and production smoke testing pending.

## A. Same-Stage logic change

- Same-Stage now means historical performance through Stage N.
- Eligible rows require the same course, active enrollment, active user, nickname, and `simulation_sessions.completed_months >= N`.
- Ranking revenue includes only persisted `monthly_results` whose `month <= N`.
- Students currently beyond N are included, but their later months cannot affect the Stage N score.
- Stage 0 remains unranked.
- Final remains Stage 12 and therefore still includes only 12/12 students using all 12 months.
- SQL `RANK()` tie semantics remain unchanged.
- Student and Instructor tables now distinguish current progress from revenue through the selected historical stage.

## B. Remove Student behavior

Endpoint:

```text
DELETE /api/instructor/courses/{course_id}/enrollments/{enrollment_id}
```

- Uses enrollment UUID, never Berkeley username, as the destructive identifier.
- Requires an authenticated instructor who owns the specified course.
- Explicitly deletes that enrollment's monthly results, simulation session, legacy submission rows required by current RESTRICT constraints, and enrollment.
- Commits once; SQL/database failures roll back the operation.
- Never deletes the global user account or another course's enrollment/session/results.
- Instructor Roster Management provides an inline confirmation explaining permanent course-scoped progress deletion and global-account retention.
- The roster refreshes after success. Progress and leaderboards fetch current server state when opened.

## C. Delete Course behavior

Endpoint:

```text
DELETE /api/instructor/courses/{course_id}
```

- Requires an authenticated instructor who owns the course.
- Explicit deterministic deletion order is monthly results → simulation sessions → legacy submissions → enrollments → course.
- Uses one transaction and one commit; failures roll back.
- Global student users and all other-course data remain intact.
- The Instructor course workspace contains a separated Danger Zone.
- Confirmation names the course, explains the full scope, and requires typing `DELETE` exactly.
- Successful deletion returns the Instructor to My Courses.

## D. AI quota persistence design

New table: `llm_daily_usage`

- One row per global student user and calendar date.
- Unique constraint: `(user_id, usage_date)`.
- Persists call count, input tokens, output tokens, estimated cost, and timestamps.
- Uses authenticated `user_id`, not browser/session/device state.
- Daily boundary: midnight in `America/Los_Angeles`; rows are retained and a new date gets a new row.
- Input tokens are counted with `tiktoken.encoding_for_model()` for the configured Azure deployment; unknown Azure aliases use `o200k_base`.
- The counted prompt includes the actual system prompt, accepted conversation history, and current message.
- Real provider requests pass `max_tokens=500` (from settings) before generation.
- Provider-reported prompt/completion usage is used when present; otherwise the same tokenizer estimates output.
- Mock responses do not reserve or consume paid-model call/token/cost quota.

## E. AI concurrency and accounting behavior

The implementation uses reservation accounting:

1. PostgreSQL inserts the unique user/day row if absent.
2. The row is selected `FOR UPDATE`.
3. Calls, estimated input, and worst-case 500-token output cost are checked inside the lock.
4. One call/input/worst-case cost reservation is committed before the provider call.
5. The transaction and row lock are released before external network latency.
6. A successful response reconciles the reservation to actual provider usage.

Consequences:

- Concurrent requests cannot both observe the same pre-limit state.
- Rejections before provider dispatch do not increment usage and return structured HTTP 429 detail.
- A reserved provider call counts even if the provider later fails, because resources may have been consumed.
- If post-provider reconciliation fails, the already-committed worst-case reservation remains as a conservative safety record.
- Student A and Student B have independent rows and allowances.

## F. Migration added

```text
0005_llm_daily_usage
```

- Revises `0004_simulation_persistence`.
- Creates only the usage table, constraints, FK, and date index.
- Does not delete legacy submissions.
- The previously planned destructive cleanup is explicitly deferred to a future `0006_drop_legacy_submissions` if separately approved.
- Verified single Alembic head: `0005_llm_daily_usage`.
- Local `alembic check`: `No new upgrade operations detected.`

## G. Environment/settings changes

Non-secret settings with documented defaults:

```text
MAX_LLM_CALLS_PER_DAY=50
MAX_LLM_INPUT_TOKENS_PER_DAY=100000
MAX_LLM_OUTPUT_TOKENS_PER_CALL=500
MAX_LLM_ESTIMATED_COST_PER_DAY=0.25
LLM_USAGE_TIMEZONE=America/Los_Angeles
LLM_INPUT_COST_PER_MILLION_TOKENS=0.40
LLM_OUTPUT_COST_PER_MILLION_TOKENS=1.60
```

The two centralized pricing defaults match the repository's documented `gpt-4.1-mini` deployment. OpenAI's current model page lists $0.40 per million input tokens and $1.60 per million output tokens: <https://developers.openai.com/api/docs/models/gpt-4.1-mini>.

If the actual Azure deployment uses a differently priced model, update only the two pricing environment values to the applicable Azure/model rates before enabling paid requests. No secret is stored in these settings.

`render.yaml` and `.env.example` contain the non-secret limits, timezone, and centralized pricing values. `tiktoken` was added to backend requirements.

## H. Focused tests

Focused result:

```text
11 passed in 2.28s
```

Coverage includes:

- Stage 4 peers currently at 4, 8, and 12 months, with scoring truncated to Months 1–4.
- Stage 3, other-course, inactive, and ineligible data excluded.
- Shared SQL rank ties.
- Enrollment deletion scope, retained global user/other-course data, and unauthorized owner rejection.
- Course deletion scope, retained global users/other-course data, unauthorized owner rejection, and route rollback on commit failure.
- Independent per-student usage, exact 50-call boundary, input cap, cost cap, next-day reset, persistent server status, concurrent one-call boundary, structured 429, no provider call after rejection, provider output limit 500, and mock non-metering.

Additional checks:

- Python compile: passed.
- Alembic metadata drift check: passed.
- Local TypeScript compiler: stopped after approximately two minutes with no output, consistent with the previously accepted local toolchain/filesystem condition. Render clean build remains the authoritative frontend compilation gate.
- Full legacy backend suite and exhaustive migration rehearsal were intentionally not rerun.

## I. Commit SHA

Pending.

## J. Render deployment result

Pending.

## K. Production migration result

Pending. No production migration or SQL has been run for this change.

## L. Production smoke results

Pending. Destructive smoke tests must use only a disposable enrollment and disposable course.

## M. Remaining issue

- Confirm the actual Render Azure deployment's model pricing matches the configured centralized price values; keep conservative values if uncertain.
- Wait for Render clean-build status after push before running `alembic upgrade head` in the positively identified production service environment.
