import pytest
from domain.enums import JobStatus
from core.state_machine import validate_transition, is_terminal, get_allowed_transitions


# ── Valid transitions ─────────────────────────────────────────────────────────

def test_queued_to_running():
    validate_transition(JobStatus.QUEUED, JobStatus.RUNNING)  # should not raise


def test_running_to_success():
    validate_transition(JobStatus.RUNNING, JobStatus.SUCCESS)


def test_running_to_failed():
    validate_transition(JobStatus.RUNNING, JobStatus.FAILED)


def test_failed_to_retryable():
    validate_transition(JobStatus.FAILED, JobStatus.RETRYABLE)


def test_retryable_to_queued():
    validate_transition(JobStatus.RETRYABLE, JobStatus.QUEUED)


# ── Invalid transitions ───────────────────────────────────────────────────────

@pytest.mark.parametrize("from_status, to_status", [
    (JobStatus.QUEUED,    JobStatus.SUCCESS),
    (JobStatus.QUEUED,    JobStatus.FAILED),
    (JobStatus.QUEUED,    JobStatus.RETRYABLE),
    (JobStatus.SUCCESS,   JobStatus.RUNNING),
    (JobStatus.SUCCESS,   JobStatus.FAILED),
    (JobStatus.RETRYABLE, JobStatus.SUCCESS),
    (JobStatus.RETRYABLE, JobStatus.FAILED),
    (JobStatus.FAILED,    JobStatus.RUNNING),
    (JobStatus.FAILED,    JobStatus.SUCCESS),
])
def test_invalid_transition_raises(from_status, to_status):
    with pytest.raises(ValueError, match="Invalid transition"):
        validate_transition(from_status, to_status)


# ── Terminal states ───────────────────────────────────────────────────────────

def test_success_is_terminal():
    assert is_terminal(JobStatus.SUCCESS) is True


def test_queued_is_not_terminal():
    assert is_terminal(JobStatus.QUEUED) is False


def test_running_is_not_terminal():
    assert is_terminal(JobStatus.RUNNING) is False


def test_failed_is_not_terminal():
    assert is_terminal(JobStatus.FAILED) is False


def test_retryable_is_not_terminal():
    assert is_terminal(JobStatus.RETRYABLE) is False


# ── Allowed transitions ───────────────────────────────────────────────────────

def test_allowed_transitions_from_queued():
    assert get_allowed_transitions(JobStatus.QUEUED) == [JobStatus.RUNNING]


def test_allowed_transitions_from_running():
    result = get_allowed_transitions(JobStatus.RUNNING)
    assert JobStatus.SUCCESS in result
    assert JobStatus.FAILED in result


def test_allowed_transitions_from_success_is_empty():
    assert get_allowed_transitions(JobStatus.SUCCESS) == []