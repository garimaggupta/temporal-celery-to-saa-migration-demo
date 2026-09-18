"""
Blocking call: enqueue the task and wait for its result.

This is the Celery equivalent of:  send_welcome_email.delay(42).get()

  .delay(42)   -> enqueues the task, returns an AsyncResult immediately
  .get()       -> blocks until the worker finishes and returns the value

In the Temporal version this becomes a single client.execute_activity(...) call.
"""

from tasks import send_welcome_email

async_result = send_welcome_email.delay(42)
print(f"Task enqueued (id={async_result.id}). Waiting for result...")

result = async_result.get(timeout=30)  # blocks until the worker completes it
print(f"Result: {result}")
