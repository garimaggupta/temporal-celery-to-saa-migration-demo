# Celery → Temporal Standalone Activities demo

A hands-on, two-part demo that stands up a real Celery background job from
scratch, then migrates it to a Temporal **Standalone Activity** — an Activity
you run directly from a Client, with no Workflow code.

The same job (send a welcome email, with retries) is built both ways so the two
sit side by side. The mock user-lookup and email-delivery helpers are identical
on both sides, and both support a `FLAKY=1` toggle that fails the first two
attempts so you can watch retries happen.

## Run order

1. **[`celery-app/`](./celery-app/README.md)** — set up Celery from zero
   (Redis broker, worker, blocking + fire-and-forget calls, retries, Flower).
   Written for someone who has never run Celery.
2. **[`temporal-app/`](./temporal-app/README.md)** — rebuild the same job on
   Temporal: convert the task to an Activity, run a Worker, invoke it both
   ways, migrate retries to a `RetryPolicy`, and inspect Activities in place of
   Flower — no Workflow, no broker, no result backend.
3. **[`serverless-app/`](./serverless-app/README.md)** — Deploy Temporal workers
   on AWS Lambda. Instead of a long-running worker.run() poll loop, Temporal's
   Worker Controller invokes your Lambda on demand when tasks arrive on the Task Queue,
   and the worker shuts down when they're drained — no idle compute, no autoscaling to manage.

## The mapping, at a glance

| Celery                          | Temporal Standalone Activity              |
| ------------------------------- | ----------------------------------------- |
| Task (`@app.task`)              | Activity (`@activity.defn`)               |
| Worker (`celery ... worker`)    | Worker (activities only, no Workflows)    |
| Broker + result backend         | The Temporal Service                      |
| `.delay(...)`                   | `client.start_activity(...)`              |
| `.delay(...).get()`             | `client.execute_activity(...)`            |
| `max_retries` / `self.retry()`  | `RetryPolicy`                             |
| Flower / `celery inspect`       | `list_activities` / `count_activities`    |

## What this demo covers
- **Less infrastructure.** Celery needs a broker *and* a result backend
  running (Redis here). Temporal needs only the Temporal Service — it queues
  work and durably stores results itself.
- **Retry code disappears.** The Celery task hand-writes a try/except with
  `self.retry()`. The Temporal Activity has none — retries become a declarative
  `RetryPolicy` at the call site, and each attempt is visible in the Web UI.
- **Durability for free.** Kill the Temporal Worker mid-job and restart it; the
  Activity survives and completes. Its full history is queryable afterward.
- **Same visibility, no extra service.** No Flower to deploy — list and count
  Activities straight from the client, the CLI, or the Web UI.

Based on Temporal's guide:
[Migrate a Celery task queue to a Temporal Standalone Activity](https://docs.temporal.io/guides/celery-to-standalone-activity).
