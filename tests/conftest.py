"""Shared pytest configuration.

Until the first test exists, pytest exits with code 5 ("no tests collected").
The hook below maps that to 0 so the empty scaffold passes (TASK-001, see
DECISION-004). Remove it once the suite contains real tests.
"""

import pytest


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Treat an empty test suite as success.

    Args:
        session: The pytest session.
        exitstatus: The exit status pytest is about to return.

    Returns:
        None. Mutates ``session.exitstatus`` in place.
    """
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
