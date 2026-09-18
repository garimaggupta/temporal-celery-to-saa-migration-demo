"""
Shared Temporal connection helper.

Loads connection settings from a .env file (see .env.example) and returns a
connected Client. All four scripts (worker, execute, start, inspect) import
connect() and TASK_QUEUE from here so the connection logic lives in one place.

Behavior:
  * If TEMPORAL_API_KEY is set  -> connect to Temporal Cloud with API key auth
                                   (TLS is required and enabled automatically).
  * Otherwise                   -> connect to a local dev server (no auth, no TLS).

This lets the same code run against `temporal server start-dev` locally and
against Temporal Cloud just by populating .env.
"""

import os

from dotenv import load_dotenv
from temporalio.client import Client
from pathlib import Path

# Load variables from a .env file in the current directory (or a parent) into
# the environment. Real environment variables always win over .env values.
#load_dotenv()
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
# The Task Queue every script shares. Kept here so the worker and the clients
# can never drift onto different queues.
TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "email-tasks")


async def connect() -> Client:
    """Connect to Temporal Cloud (API key) or a local dev server."""
    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    api_key = os.environ.get("TEMPORAL_API_KEY")

    #print(f"Connecting to Temporal Cloud with API key: {api_key}")

    if api_key:
        # --- Temporal Cloud, API key authentication ---
        # The endpoint is the gRPC Namespace endpoint:
        #   <namespace>.<account>.tmprl.cloud:7233
        # namespace is the "<namespace_id>.<account_id>" combination.
        # tls=True is required whenever an API key is used.
        return await Client.connect(
            address,
            namespace=namespace,
            api_key=api_key,
            tls=True,
        )

    # --- Local dev server (temporal server start-dev) ---
    return await Client.connect(address, namespace=namespace)
