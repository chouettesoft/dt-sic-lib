"""Pytest configuration, including lightweight per-test timing."""

import time

import pytest


_TIMINGS = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    start = time.perf_counter_ns()
    outcome = yield
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
    _TIMINGS.append((item.nodeid, elapsed_ms, outcome.excinfo is None))


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not _TIMINGS:
        return

    terminalreporter.write_sep("-", "test timing")
    for nodeid, elapsed_ms, passed in sorted(_TIMINGS, key=lambda row: row[1], reverse=True):
        status = "PASS" if passed else "FAIL"
        terminalreporter.write_line(f"{elapsed_ms:9.3f} ms  {status:4}  {nodeid}")

    total_ms = sum(row[1] for row in _TIMINGS)
    terminalreporter.write_line(f"Total measured test time: {total_ms:.3f} ms")
    terminalreporter.write_line(f"Slowest test: {max(_TIMINGS, key=lambda row: row[1])[1]:.3f} ms")
