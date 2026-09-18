# Part 1 — Stand up a Celery job from scratch

This half of the demo gets a working Celery background job running on your
machine, assuming you have **never run Celery before**. Once it works, move on
to `../temporal-app` to migrate the same job to a Temporal Standalone Activity.

## What Celery needs to run

Celery is a distributed task queue. Three pieces have to be running for a job
to execute:

1. **A broker** — a message queue that delivers tasks to workers. We use
   **Redis** (the simplest option).
2. **A worker** — a process that pulls tasks off the broker and runs your code.
3. **A client** — any Python code that enqueues a task (here, a small script).

For this demo Redis also acts as the **result backend**, which stores return
values so a blocking `.get()` call can retrieve them.

## Prerequisites

- **Python 3.9+**
- **Docker** (easiest way to run Redis), *or* a local Redis install

---

## Step 1 — Create a virtual environment and install Celery

From this `celery-app/` directory:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

This installs `celery`, `redis` (the Python client), and `flower` (a web
dashboard we use in Step 6).

## Step 2 — Start the Redis broker

The quickest way is Docker — one command, nothing to configure:

```bash
docker run --rm -p 6379:6379 redis
```

Leave this running in its own terminal. (Prefer a native install? On macOS:
`brew install redis && redis-server`. On Debian/Ubuntu:
`sudo apt-get install redis-server && redis-server`.)

Redis now listens on `localhost:6379`, which is the address `tasks.py` points
its broker and backend at.

## Step 3 — Look at the task

Open `tasks.py`. The important parts:

- `app = Celery("myapp", broker=..., backend=...)` wires Celery to Redis.
- `@app.task(bind=True, max_retries=5, default_retry_delay=3)` marks
  `send_welcome_email` as a background task and declares its retry behavior.
- Inside the task, transient failures are caught and re-raised with
  `self.retry(...)` — with Celery, **retry logic is code you write yourself.**

Keep note of that retry block. Erasing it is one of the clearest wins when you
migrate to Temporal.

## Step 4 — Start the Celery worker

In a new terminal (with the venv activated):

```bash
celery -A tasks worker --loglevel=info
```

`-A tasks` tells Celery to load the app from `tasks.py`. You'll see the worker
boot, connect to Redis, and list `tasks.send_welcome_email` under `[tasks]`.
Leave it running.

## Step 5 — Enqueue work

Open a **third** terminal (venv activated) for the client scripts.

**Blocking call** — enqueue and wait for the result:

```bash
python run_blocking.py
```

You'll see the task id printed, then `Result: sent to user42@example.com`. Over
in the worker terminal you'll see the job received and succeed. This is
`.delay(42).get()`.

**Fire-and-forget** — enqueue and return immediately:

```bash
python run_fire_and_forget.py
```

The script exits at once; the worker terminal shows the job running in the
background. This is a bare `.delay(42)`.

## Step 6 — Watch retries happen

Stop the worker (Ctrl-C) and restart it with the flaky email provider enabled:

```bash
FLAKY=1 celery -A tasks worker --loglevel=info
```

Now `deliver_email` throws a `TransientError` on the first two attempts for
each user. Run `python run_blocking.py` again and watch the worker log: the
task fails, waits `default_retry_delay` seconds, retries, and finally succeeds
on the third attempt. This is Celery's `max_retries` / `self.retry()` at work.

## Step 7 — Monitor with Flower (optional)

Flower is Celery's web dashboard. In another terminal:

```bash
celery -A tasks flower
```

Open <http://localhost:5555> to watch tasks, workers, and retries live. Fire a
few more jobs and refresh. Remember Flower — the Temporal side replaces it with
client-side `list_activities` / `count_activities` calls and the Temporal Web UI.

---

## What you just built (and what Temporal replaces)

| Celery piece                    | Where you saw it                    | Temporal replacement |
| ------------------------------- | ----------------------------------- | -------------------- |
| Task (`@app.task`)              | `send_welcome_email` in `tasks.py`  | Activity (`@activity.defn`) |
| Worker (`celery ... worker`)    | Step 4                              | Temporal Worker (activities only) |
| Broker + result backend (Redis) | Step 2                              | The Temporal Service |
| `.delay(...)`                   | `run_fire_and_forget.py`            | `client.start_activity(...)` |
| `.delay(...).get()`             | `run_blocking.py`                   | `client.execute_activity(...)` |
| `max_retries` / `self.retry()`  | Step 3 / Step 6                     | `RetryPolicy` |
| Flower                          | Step 7                              | `list_activities` / `count_activities` + Web UI |

Now head to **`../temporal-app`** to rebuild this exact job on Temporal — with
no broker to run, no result backend to configure, and no hand-written retry code.
