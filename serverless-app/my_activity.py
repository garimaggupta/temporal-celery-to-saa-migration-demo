"""
The Activity — this is the former Celery task from ../celery-app/tasks.py.

The work inside (user lookup, email delivery) is identical. Two things changed:

  1. The retry try/except is GONE. Temporal retries a failed Activity
     automatically according to a RetryPolicy set at invocation time.
  2. The function takes ONE dataclass argument instead of a positional
     user_id. Passing a single structured input is the recommended Temporal
     pattern — you can add fields later without breaking callers.

Nothing here marks the Activity as "standalone." What makes it standalone is
how it's invoked (see execute_activity.py / start_activity.py) — directly from
a Client, with no Workflow.
"""

import os
from dataclasses import dataclass

from temporalio import activity
from temporalio.exceptions import ApplicationError


@dataclass
class User:
    user_id: int
    email: str


@dataclass
class WelcomeEmailInput:
    user_id: int


# --- Mock helpers (same behavior as the Celery version) -------------------
_attempts: dict[int, int] = {}


def get_user(user_id: int) -> User:
    return User(user_id=user_id, email=f"user{user_id}@example.com")


def deliver_email(address: str, subject: str, user_id: int) -> None:
    # Set FLAKY=1 in the Worker's environment to fail the first two attempts
    # and watch Temporal retry the Activity automatically.
    if os.environ.get("FLAKY") == "1":
        n = _attempts.get(user_id, 0) + 1
        _attempts[user_id] = n
        if n <= 2:
            raise RuntimeError(f"provider timeout (attempt {n})")
    print(f"Delivering '{subject}' to {address}")
# --------------------------------------------------------------------------


@activity.defn
def send_welcome_email(input: WelcomeEmailInput) -> str:
    user = get_user(input.user_id)
    if user is None:
        # A permanent failure: mark it non-retryable so Temporal fails fast
        # instead of retrying. This is the equivalent of NOT calling
        # self.retry() for an unrecoverable error in Celery.
        raise ApplicationError(
            "No such user", type="InvalidUserError", non_retryable=True
        )
    deliver_email(user.email, "Welcome!", input.user_id)
    return f"sent to {user.email}"
