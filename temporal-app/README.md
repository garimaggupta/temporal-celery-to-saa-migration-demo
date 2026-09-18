# Part 2 — Migrate the job to a Temporal Standalone Activity

You have a working Celery job from Part 1. Now rebuild it on Temporal with **no
Workflow code** — a Standalone Activity is an Activity you start directly from a
Client. You get durability, retries, timeouts, and visibility for a single unit
of work, which maps almost one-to-one onto a Celery task.


## How the two sides line up

| Celery                          | Temporal Standalone Activity        | Where it lives here |
| ------------------------------- | ----------------------------------- | ------------------- |
| Task (`@app.task`)              | Activity (`@activity.defn`)         | `my_activity.py` |
| Worker (`celery ... worker`)    | Worker (activities only)            | `worker.py` |
| Broker + result backend (Redis) | The Temporal Service                | `temporal server start-dev` |
| `.delay(...).get()`             | `client.execute_activity(...)`      | `execute_activity.py` |
| `.delay(...)`                   | `client.start_activity(...)`        | `start_activity.py` |
| `max_retries` / `self.retry()`  | `RetryPolicy`                       | `execute_activity.py` |
| Flower / `celery inspect`       | `list_activities` / `count_activities` | `inspect_activities.py` |

## Prerequisites

- **Python 3.9+**
- **Temporal Python SDK ≥ 1.23.0** (installed below)
- **Temporal CLI ≥ 1.7.0** (the dev server includes Standalone Activity support)
- For production: Temporal Server ≥ 1.31.0, or Temporal Cloud

Notice what's **not** here: no broker to run, no result backend to configure.
The Temporal Service handles queueing and durable result storage itself.

---

## Step 1 — Install the SDK and CLI

From this `temporal-app/` directory:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` includes `python-dotenv`, used to read connection settings
from a `.env` file (see the next section).

Install the CLI (macOS/Linux with Homebrew):

```bash
brew install temporal
temporal --version               # confirm >= 1.7.0
```

No Homebrew? Grab the binary from the
[CLI install guide](https://docs.temporal.io/cli/setup-cli) and add it to your PATH.

## Connecting: local dev server or Temporal Cloud

All four scripts get their client from one place — `temporal_connection.py` —
which loads settings from a `.env` file. Create one from the template:

```bash
cp .env.example .env
```

**Local dev server (default).** Leave `TEMPORAL_API_KEY` empty (or set
`TEMPORAL_ADDRESS=localhost:7233`). The helper connects with no auth or TLS.
Continue with Step 2 to start `temporal server start-dev`.

**Temporal Cloud with an API key.** Fill in `.env`:

```bash
TEMPORAL_ADDRESS=your-namespace.your-account.tmprl.cloud:7233
TEMPORAL_NAMESPACE=your-namespace.your-account
TEMPORAL_API_KEY=tmprl_...
```

When `TEMPORAL_API_KEY` is set, the helper connects with API key auth and TLS
enabled (required for API keys). Under the hood that's:

```python
await Client.connect(
    address,                    # <namespace>.<account>.tmprl.cloud:7233
    namespace=namespace,        # <namespace_id>.<account_id>
    api_key=api_key,
    tls=True,
)
```

Get the endpoint, namespace, and account ID from the **Namespaces** tab in the
Temporal Cloud UI (the namespace must have API key authentication enabled).
Create a key in the UI or with `tcld apikey create`. **Never commit `.env`** —
the included `.gitignore` already excludes it.

When connected to Cloud, skip Step 2 (there's no local server to run) and use
the Temporal Cloud UI in place of `http://localhost:8233`. Steps 4–8 are
otherwise identical.

## Step 2 — Start the Temporal dev server

This is what Redis was in Part 1 — except it also durably stores each
Activity's state and result, so there's no separate backend.

```bash
temporal server start-dev
```

You'll see:

```
Server:  localhost:7233
UI:      http://localhost:8233
```

Your code connects to `localhost:7233`; the Web UI is at
<http://localhost:8233> (Standalone Activities get their own nav item). Leave it
running.

## Step 3 — Read the Activity

Open `my_activity.py` and compare it to `../celery-app/tasks.py`. Same user
lookup, same email delivery. Two differences:

- **The retry try/except is gone.** No catching `TransientError`, no
  `self.retry()`. Temporal retries a failed Activity automatically.
- **One dataclass argument** (`WelcomeEmailInput`) instead of a positional
  `user_id`, so you can add fields later without breaking callers.

## Step 4 — Start the Worker

In a new terminal (venv activated):

```bash
python worker.py
```

It polls the `email-tasks` Task Queue — the analog of a Celery queue name.
Leave it running.

## Step 5 — Run the Activity (blocking) — replaces `.delay().get()`

Third terminal (venv activated):

```bash
python execute_activity.py
```

You'll see `Result: sent to user42@example.com`. One `execute_activity(...)`
call durably enqueues the Activity, waits for the Worker, and returns the
value. It also carries a `RetryPolicy` (`maximum_attempts=6` ≈ Celery's
`max_retries=5` — Temporal counts total attempts, Celery counts retries after
the first) and a required `start_to_close_timeout`.

## Step 6 — Start the Activity (fire-and-forget) — replaces `.delay()`

```bash
python start_activity.py
```

`start_activity(...)` returns a handle immediately, like Celery's
`AsyncResult`; `handle.result()` later is like `.get()`. If a different process
needs to reconnect, rebuild the handle with
`client.get_activity_handle(activity_id=..., run_id=...)`.

## Step 7 — Watch retries happen — replaces `max_retries` / `self.retry()`

Stop the Worker and restart it with the flaky provider enabled:

```bash
FLAKY=1 python worker.py
```

Re-run `python execute_activity.py`. The first two attempts fail; Temporal
retries automatically per the policy and the Activity succeeds on the third —
no retry code anywhere in `my_activity.py`. Open the Activity in the Web UI to
see its attempts and history. (An `InvalidUserError` would be non-retryable and
fail fast, the equivalent of *not* calling `self.retry()` for a permanent
failure.)

## Step 8 — Inspect Activities — replaces Flower

```bash
python inspect_activities.py
```

You'll see one line per Activity execution plus a total count — the durable,
queryable version of `celery inspect active`. Same List Filter syntax as
Workflow visibility, so you can filter by `ActivityType`, `Status`, etc. The
CLI equivalents are `temporal activity list` and `temporal activity count`, and
everything is visible in the Web UI.

---

## When you'd reach for a Workflow instead

Standalone Activities cover the common case: a task that does one independent
thing. They have no orchestration, so the one case they don't cover is
**multi-step pipelines**. If your Celery app uses Canvas primitives — `chain`
(one result feeds the next), `group` (fan out in parallel), or `chord`
(callback after a group) — that coordination needs to live durably somewhere,
and a Standalone Activity can't call another Activity. Wrap those Activities in
a Temporal **Workflow**, where sequencing is ordinary `await` and parallelism
is `asyncio.gather`.

Rule of thumb: **Standalone Activity when the task stands on its own, Workflow
when it coordinates other tasks.** Most Celery tasks are the former.

## Reference

- [Migrate a Celery task queue to a Temporal Standalone Activity](https://docs.temporal.io/guides/celery-to-standalone-activity)
- [Standalone Activities feature guide (Python)](https://docs.temporal.io/develop/python/activities/standalone-activities)
- [Standalone Activities Quickstart](https://docs.temporal.io/develop/python/activities/standalone-activities-quickstart)
- [Activity timeouts](https://docs.temporal.io/develop/python/activities/timeouts)
