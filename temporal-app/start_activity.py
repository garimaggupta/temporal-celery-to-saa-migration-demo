"""
Fire-and-forget invocation — replaces Celery's  send_welcome_email.delay(42)

client.start_activity(...) durably enqueues the Activity and hands back a
handle immediately, the way Celery's .delay() returns an AsyncResult. Call
handle.result() later when you actually need the value — the equivalent of
AsyncResult.get().

(The Activity id differs from execute_activity.py's so the two don't dedupe
against each other.)

Run with:
    python start_activity.py
"""

import asyncio
from datetime import timedelta

from my_activity import WelcomeEmailInput, send_welcome_email
from temporal_connection import TASK_QUEUE, connect


async def main():
    client = await connect()
    handle = await client.start_activity(
        send_welcome_email,
        args=[WelcomeEmailInput(42)],
        id="welcome-email-delay",
        task_queue=TASK_QUEUE,
        start_to_close_timeout=timedelta(seconds=30),
    )
    print(f"Activity started (id={handle.id}, run_id={handle.run_id})")

    # Later, from this or another process, block on the result when you need it.
    # From a different process, rebuild the handle instead:
    #     handle = client.get_activity_handle(
    #         activity_id="welcome-email-delay", run_id="the-run-id"
    #     )
    result = await handle.result()
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
