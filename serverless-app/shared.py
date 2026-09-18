"""Constants shared by the Lambda worker and the local trigger."""

# The Task Queue the Worker polls and the trigger submits activities to.
# Both must match.
TASK_QUEUE = "email-tasks"
