"""
Blocking invocation — replaces Celery's  send_welcome_email.delay(42).get()

client.execute_activity(...) durably enqueues the Activity, waits for a Worker
to run it, and returns the result — all in one call.

The retry_policy is what replaces Celery's max_retries / self.retry(): retries
are now declarative. Note Celery counts retries AFTER the first attempt, while
Temporal counts total attempts — so maximum_attempts=6 mimics max_retries=5.

Run with:
    python execute_activity.py
"""

import asyncio
from datetime import timedelta

from temporalio.common import RetryPolicy

from my_activity import WelcomeEmailInput, send_welcome_email
from temporal_connection import TASK_QUEUE, connect


async def main():
    client = await connect()
    result = await client.execute_activity(
        send_welcome_email,
        args=[WelcomeEmailInput(42)],
        # A business identifier you choose. Temporal uses it to dedupe, so the
        # same Activity isn't started twice.
        id="welcome-email-42",
        task_queue=TASK_QUEUE,
        # Every Activity requires a timeout. start_to_close caps one attempt,
        # replacing Celery's task_time_limit.
        start_to_close_timeout=timedelta(seconds=30),
        retry_policy=RetryPolicy(
            maximum_attempts=6,               # ~ Celery max_retries=5
            maximum_interval=timedelta(minutes=1),
            non_retryable_error_types=["InvalidUserError"],
        ),
    )
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
