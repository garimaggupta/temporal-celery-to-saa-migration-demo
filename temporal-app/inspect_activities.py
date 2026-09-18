"""
Inspect Activities — replaces Flower / `celery inspect`.

Temporal gives you visibility directly through the client: list and count
Standalone Activities matching a filter, using the same List Filter syntax as
Workflow visibility. These calls return only Standalone Activities; Activities
running inside Workflows are excluded.

The Temporal CLI offers the same views: `temporal activity list` /
`temporal activity count`. The Web UI at http://localhost:8233 shows them too.

Run with:
    python inspect_activities.py
"""

import asyncio

from temporal_connection import TASK_QUEUE, connect


async def main():
    client = await connect()
    query = f"TaskQueue = '{TASK_QUEUE}'"

    # List: like `celery inspect active`, but durable and queryable. You can
    # filter on attributes, e.g.:
    #   "ActivityType = 'send_welcome_email' AND Status = 'Running'"
    async for info in client.list_activities(query=query):
        print(f"{info.activity_id} | {info.activity_type} | {info.status}")

    # Count: total executions (running, completed, failed) — not queued tasks.
    resp = await client.count_activities(query=query)
    print(f"Total activities: {resp.count}")


if __name__ == "__main__":
    asyncio.run(main())
