# Running the worker on AWS Lambda (Temporal Serverless Workers)

This packages the demo's worker as a **Temporal Serverless Worker** on AWS
Lambda. Instead of a long-running `worker.run()` poll loop, Temporal's Worker
Controller **invokes your Lambda on demand** when tasks arrive on the Task
Queue, and the worker shuts down when they're drained — no idle compute, no
autoscaling to manage.


## How this differs from the local worker

| Local worker (`../worker.py`)            | Serverless Worker (this folder)                     |
| ---------------------------------------- | --------------------------------------------------- |
| Long-lived process, `await worker.run()` | Lambda handler from `run_worker(...)`, invoked on demand |
| You run and scale it                     | Temporal invokes it per task backlog; scales 0→N    |
| Connects in code (`temporal_connection.py`) | Connection auto-loaded from Lambda env vars       |
| Pure Standalone Activities, no Workflow  | Same — Standalone Activities, no Workflow           |

### No wrapper Workflow needed

Serverless Worker invocation triggers on **task backlog**, not specifically on
Workflows. When an activity task lands on the Task Queue and can't be
sync-matched to an active poller, the Matching Service signals the Worker
Controller, which invokes the Lambda. Standalone Activities dispatch work
through Task Queues, so a standalone-activity backlog triggers invocation the
same way a workflow backlog would. The activity runs on Lambda unchanged.

Worker Versioning is still required for Serverless Workers, so `lambda_function.py`
passes a `WorkerDeploymentVersion`. It does **not** set
`default_versioning_behavior` — that's a Workflow concept, this worker has no
Workflow, and as a `worker_config` key it raises a `TypeError` in the published
`temporalio`. See `DEPLOY.md` ("Versioning behavior") for the contingency if a
first deploy turns out to require one.

## Files

- `my_activity.py` — the demo activity, unchanged (copied here so the zip is self-contained).
- `shared.py` — the shared `TASK_QUEUE` constant.
- `lambda_function.py` — the Lambda handler (`lambda_handler` from `run_worker`).
- `trigger.py` — run locally to submit the Standalone Activity and trigger the Lambda.
- `requirements.txt` — `temporalio` (the `lambda_worker` package is inside it).

## Deploying

Use this guide - [Deploy a Serverless Worker on AWS Lambda](https://docs.temporal.io/production-deployment/worker-deployments/serverless-workers/aws-lambda) to deploy serverless worker in AWS Lambda.

## Tuning notes

The `lambda_worker` package applies Lambda-friendly defaults
(`max_concurrent_activities=2`, `graceful_shutdown_timeout=5s`,
`disable_eager_activity_execution=True`, etc.). For long-running activities,
raise `graceful_shutdown_timeout`, `shutdown_deadline_buffer`, and the Lambda
`--timeout` **together** so the worker can finish and shut down cleanly before
AWS terminates the invocation.

## References

- [Serverless Workers on AWS Lambda — Python SDK](https://docs.temporal.io/develop/python/workers/serverless-workers/aws-lambda)
- [Deploy a Serverless Worker on AWS Lambda](https://docs.temporal.io/production-deployment/worker-deployments/serverless-workers/aws-lambda)
- [Python Lambda Worker sample](https://github.com/temporalio/samples-python/tree/main/lambda_worker)
- [Troubleshoot Serverless Workers on AWS Lambda](https://docs.temporal.io/troubleshooting/serverless-workers/aws-lambda)
