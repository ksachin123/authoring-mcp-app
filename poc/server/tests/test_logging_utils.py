import logging

import pytest

from research_authoring.logging_utils import trace_tool_call


def test_trace_tool_call_passes_through_args_and_return_value():
    @trace_tool_call
    def add(a, b):
        return a + b

    assert add(2, 3) == 5


def test_trace_tool_call_logs_start_and_success(caplog):
    @trace_tool_call
    def greet(name):
        return f"hello {name}"

    with caplog.at_level(logging.INFO, logger="research_authoring.tools"):
        greet(name="world")

    messages = [r.message for r in caplog.records]
    assert any("greet: start" in m and "name='world'" in m for m in messages)
    assert any("greet: success" in m and "hello world" in m for m in messages)


def test_trace_tool_call_logs_failure_and_reraises(caplog):
    @trace_tool_call
    def boom():
        raise ValueError("kaboom")

    with caplog.at_level(logging.INFO, logger="research_authoring.tools"):
        with pytest.raises(ValueError, match="kaboom"):
            boom()

    messages = [r.message for r in caplog.records]
    assert any("boom: FAILED" in m for m in messages)


def test_trace_tool_call_truncates_long_values(caplog):
    @trace_tool_call
    def echo(payload):
        return payload

    long_value = "x" * 1000
    with caplog.at_level(logging.INFO, logger="research_authoring.tools"):
        echo(payload=long_value)

    messages = [r.message for r in caplog.records]
    start_message = next(m for m in messages if "echo: start" in m)
    assert len(start_message) < len(long_value)
    assert "more chars" in start_message
