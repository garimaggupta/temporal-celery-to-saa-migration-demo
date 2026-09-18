"""
Celery version of the demo.

A single self-contained background job: send a "welcome" email to a user.
This is the kind of task that maps almost one-to-one onto a Temporal
Standalone Activity, which is what we migrate to in ../temporal-app.

Run the worker with:
    celery -A tasks worker --loglevel=info

Then, from another terminal, enqueue work with run_blocking.py or
run_fire_and_forget.py.
"""

import os

from celery import Celery

# The Celery app. Redis is both the BROKER (delivers tasks to workers) and
# the RESULT BACKEND (stores return values so .get() can retrieve them).
app = Celery(
    "myapp",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)


# --- Mock helpers ---------------------------------------------------------
# Stand-ins for a real user lookup and email provider. Swap these for your
# database query and email SDK when adapting the demo. The Temporal version
# uses the exact same helpers so the two sides stay comparable.

class TransientError(Exception):
    """A temporary failure worth retrying (e.g. provider timeout)."""


# Tracks attempts per user_id so the "flaky" demo fails the first two tries
# and then succeeds. Set FLAKY=1 in the worker's environment to enable it.
_attempts: dict[int, int] = {}


def get_user(user_id: int) -> dict:
    return {"user_id": user_id, "email": f"user{user_id}@example.com"}


def deliver_email(address: str, subject: str, user_id: int) -> None:
    if os.environ.get("FLAKY") == "1":
        n = _attempts.get(user_id, 0) + 1
        _attempts[user_id] = n
        if n <= 2:
            raise TransientError(f"provider timeout (attempt {n})")
    print(f"Delivering '{subject}' to {address}")
# --------------------------------------------------------------------------


@app.task(bind=True, max_retries=5, default_retry_delay=3)
def send_welcome_email(self, user_id: int) -> str:
    """Send a welcome email. Retries on transient provider failures.

    With Celery, the retry logic is your responsibility: you set max_retries
    on the task and explicitly call self.retry() when a transient error
    occurs. In the Temporal version this whole try/except disappears — retries
    become a declarative RetryPolicy.
    """
    user = get_user(user_id)
    try:
        deliver_email(user["email"], "Welcome!", user_id)
    except TransientError as exc:
        print(f"Transient failure, retrying: {exc}")
        raise self.retry(exc=exc)
    return f"sent to {user['email']}"
