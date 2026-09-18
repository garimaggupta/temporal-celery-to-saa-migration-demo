"""
Trigger the demo. Run this from your laptop (NOT on Lambda).

Submitting a Standalone Activity is what causes Temporal to invoke your Lambda
Worker: the activity task lands on the Task Queue, can't be sync-matched to an
active poller, and Temporal invokes the configured Lambda to process it.

Reads TEMPORAL_ADDRESS / TEMPORAL_NAMESPACE / TEMPORAL_API_KEY from the
environment (the same Cloud connection you configured earlier).

    python trigger.py
"""

import asyncio
import os
from datetime import timedelta

from temporalio.client import Client
from temporalio.common import RetryPolicy

from my_activity import WelcomeEmailInput, send_welcome_email
from shared import TASK_QUEUE


async def main():
    client = await Client.connect(
        os.environ["TEMPORAL_ADDRESS"],
        namespace=os.environ["TEMPORAL_NAMESPACE"],
        api_key=os.environ.get("TEMPORAL_API_KEY"),
        tls=True,
    )

    result = await client.execute_activity(
        send_welcome_email,
        args=[WelcomeEmailInput(42)],
        id="welcome-email-42",
        task_queue=TASK_QUEUE,
        start_to_close_timeout=timedelta(seconds=30),
        retry_policy=RetryPolicy(
            maximum_attempts=6,
            non_retryable_error_types=["InvalidUserError"],
        ),
    )
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
