"""
Submit a burst of welcome-email jobs concurrently — a serverless load test.

Run from your laptop, same as trigger.py. It fires NUM_JOBS Standalone Activities
(send_welcome_email) at once with asyncio.gather. Because serverless workers have
no persistent pollers, the sudden Task Queue backlog drives Temporal's Worker
Controller to invoke many Lambda workers in parallel to drain it — this is the
serverless autoscaling story in action. Watch concurrent invocations in
CloudWatch (the function's "ConcurrentExecutions" metric) and in the Temporal
Cloud UI.

    export TEMPORAL_ADDRESS=<namespace>.<account>.tmprl.cloud:7233
    export TEMPORAL_NAMESPACE=<namespace>.<account>
    export TEMPORAL_API_KEY=<api-key>
    python submit_load.py
"""

import asyncio
import os
import time
from datetime import timedelta

from temporalio.client import Client
from temporalio.common import RetryPolicy

from my_activity import WelcomeEmailInput, send_welcome_email
from shared import TASK_QUEUE

# --- knobs ---------------------------------------------------------------
NUM_JOBS = 200                 # how many jobs to submit at once
WAIT_FOR_RESULTS = True        # False = submit and exit (watch CloudWatch)
# -------------------------------------------------------------------------


async def connect() -> Client:
    # Same Cloud connection as trigger.py.
    return await Client.connect(
        os.environ["TEMPORAL_ADDRESS"],
        namespace=os.environ["TEMPORAL_NAMESPACE"],
        api_key=os.environ.get("TEMPORAL_API_KEY"),
        tls=True,
    )


async def main():
    client = await connect()

    # A per-run tag so Activity IDs are unique across repeated runs (Activity IDs
    # dedupe, so reusing them would collide with a prior run's jobs).
    run_id = time.strftime("%Y%m%d-%H%M%S")

    async def start_one(i: int):
        return await client.start_activity(
            send_welcome_email,
            WelcomeEmailInput(i),
            id=f"welcome-email-{run_id}-{i:03d}",
            task_queue=TASK_QUEUE,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=6,
                non_retryable_error_types=["InvalidUserError"],
            ),
        )

    print(f"Submitting {NUM_JOBS} welcome-email jobs concurrently...")
    t0 = time.monotonic()

    # Fire all starts at once.
    handles = await asyncio.gather(*(start_one(i) for i in range(NUM_JOBS)))
    print(f"All {len(handles)} jobs submitted in {time.monotonic() - t0:.1f}s.")

    if not WAIT_FOR_RESULTS:
        print("Not waiting for results — watch CloudWatch / the Temporal UI.")
        return

    print("Waiting for completion...")
    results = await asyncio.gather(
        *(h.result() for h in handles), return_exceptions=True
    )
    ok = sum(1 for r in results if not isinstance(r, BaseException))
    failed = len(results) - ok
    print(f"Done in {time.monotonic() - t0:.1f}s — {ok} succeeded, {failed} failed.")
    for r in results:  # show one failure reason, if any
        if isinstance(r, BaseException):
            print(f"  example failure: {type(r).__name__}: {r}")
            break


if __name__ == "__main__":
    asyncio.run(main())