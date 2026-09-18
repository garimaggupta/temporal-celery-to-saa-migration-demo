"""
Fire-and-forget call: enqueue the task and return immediately.

This is the Celery equivalent of:  send_welcome_email.delay(42)

The task runs in the background on the worker. We don't call .get(), so this
script exits right away — watch the worker terminal to see it get processed.

In the Temporal version this becomes client.start_activity(...), which hands
back a handle you can await later with handle.result().
"""

from tasks import send_welcome_email

async_result = send_welcome_email.delay(42)
print(f"Task enqueued (fire-and-forget). Task id: {async_result.id}")
print("Not waiting for the result. Check the worker terminal for output.")
