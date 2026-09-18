"""
The Worker — the Temporal equivalent of `celery -A tasks worker`.

A Worker for Standalone Activities is an ordinary Temporal Worker with your
Activities registered and NO Workflows. It polls a Task Queue (the routing key
that ties the Worker to the invocation scripts, like a Celery queue name).

Because send_welcome_email is a synchronous function, we run it in a
ThreadPoolExecutor. max_workers controls concurrency, like Celery's
--concurrency flag.

Run with:
    python worker.py
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from temporalio.worker import Worker

from my_activity import send_welcome_email
from temporal_connection import TASK_QUEUE, connect


async def main():
    client = await connect()
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        activities=[send_welcome_email],
        activity_executor=ThreadPoolExecutor(max_workers=5),
    )
    print("Worker running... (Ctrl-C to stop)")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
