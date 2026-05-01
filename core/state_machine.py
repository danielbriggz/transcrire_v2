from domain.enums import JobStatus

VALID_TRANSITIONS: dict[JobStatus, list[JobStatus]] = {
    JobStatus.QUEUED:    [JobStatus.RUNNING],
    JobStatus.RUNNING:   [JobStatus.SUCCESS, JobStatus.FAILED],
    JobStatus.FAILED:    [JobStatus.RETRYABLE],
    JobStatus.RETRYABLE: [JobStatus.QUEUED],
    JobStatus.SUCCESS:   [],   # Terminal — no valid transitions out
}


def validate_transition(current: JobStatus, next_status: JobStatus) -> None:
    """
    Assert that a status transition is legal.
    Raises ValueError with a clear message if not.

    Usage:
        validate_transition(JobStatus.QUEUED, JobStatus.RUNNING)   # OK
        validate_transition(JobStatus.SUCCESS, JobStatus.RUNNING)  # raises ValueError
    """
    allowed = VALID_TRANSITIONS.get(current, [])
    if next_status not in allowed:
        raise ValueError(
            f"Invalid transition: {current.value} → {next_status.value}. "
            f"Allowed from {current.value}: "
            f"{[s.value for s in allowed] or 'none (terminal state)'}"
        )


def is_terminal(status: JobStatus) -> bool:
    """Return True if the status has no valid outgoing transitions."""
    return len(VALID_TRANSITIONS.get(status, [])) == 0


def get_allowed_transitions(status: JobStatus) -> list[JobStatus]:
    """Return the list of valid next statuses from the given status."""
    return VALID_TRANSITIONS.get(status, [])