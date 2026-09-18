"""
AWS Lambda handler for a Temporal Serverless Worker (Standalone Activities).

Instead of a long-running `worker.run()` poll loop, this module exposes a
`lambda_handler` that Temporal's Worker Controller invokes on demand: when an
activity task lands on the Task Queue and can't be sync-matched to an active
poller, Temporal invokes this Lambda. It starts a Worker, polls, processes, and
gracefully shuts down before the invocation deadline.

No Workflow is involved — the same Standalone Activity from the local demo runs
here unchanged. Worker Versioning is required for Serverless Workers, so a
WorkerDeploymentVersion is passed and a worker-level default versioning behavior
(PINNED) is provided via deployment_config.

The Temporal connection is loaded automatically from environment variables
(TEMPORAL_ADDRESS / TEMPORAL_NAMESPACE / TEMPORAL_API_KEY) set on the Lambda
function — no client construction here.
"""

from concurrent.futures import ThreadPoolExecutor

from temporalio.common import VersioningBehavior, WorkerDeploymentVersion
from temporalio.contrib.aws.lambda_worker import LambdaWorkerConfig, run_worker
from temporalio.worker import WorkerDeploymentConfig

from my_activity import send_welcome_email
from shared import TASK_QUEUE

# The deployment version. deployment_name and build_id MUST match the Worker
# Deployment Version you register in Temporal (see DEPLOY.md). Shared between
# run_worker and deployment_config so they can't drift.
DEPLOYMENT_VERSION = WorkerDeploymentVersion(
    deployment_name="celery-migration-demo",
    build_id="build-1",
)


def configure(config: LambdaWorkerConfig) -> None:
    # worker_config accepts the same keyword arguments as the standard Worker.
    config.worker_config["task_queue"] = TASK_QUEUE
    config.worker_config["activities"] = [send_welcome_email]

    # Worker-level default versioning behavior.
    #
    # `default_versioning_behavior` is NOT a plain worker_config key — setting it
    # that way raises a TypeError. It lives inside WorkerDeploymentConfig, which
    # the lambda_worker docs say to provide via the `deployment_config` key here.
    # run_worker already enables use_worker_versioning=True; we set the full
    # deployment_config so we can supply the default behavior too.
    #
    # This demo registers only Standalone Activities (no Workflow), so the default
    # is currently inert — it applies to Workflows that don't declare their own
    # behavior, of which there are none. It's set correctly for when a Workflow is
    # added, and matches the version passed to run_worker below.
    config.worker_config["deployment_config"] = WorkerDeploymentConfig(
        version=DEPLOYMENT_VERSION,
        use_worker_versioning=True,
        default_versioning_behavior=VersioningBehavior.PINNED,
    )

    # send_welcome_email is a synchronous activity, so it needs an executor.
    # (Lambda's tuned default is max_concurrent_activities=2.)
    config.worker_config["activity_executor"] = ThreadPoolExecutor(max_workers=2)


# run_worker returns the Lambda handler.
lambda_handler = run_worker(DEPLOYMENT_VERSION, configure)