from __future__ import annotations

import functools
import logging
import time
import uuid
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger("research_authoring.tools")

_MAX_LOGGED_VALUE_LEN = 300


def configure_logging() -> None:
    import os

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _truncate(value: Any) -> str:
    text = repr(value)
    if len(text) > _MAX_LOGGED_VALUE_LEN:
        return f"{text[:_MAX_LOGGED_VALUE_LEN]}...(+{len(text) - _MAX_LOGGED_VALUE_LEN} more chars)"
    return text


def _format_kwargs(kwargs: dict[str, Any]) -> str:
    return ", ".join(f"{k}={_truncate(v)}" for k, v in kwargs.items())


def trace_tool_call(fn: F) -> F:
    """Log every MCP tool invocation: start (with args), success (with a
    truncated view of the output), or failure (with the exception) -- plus
    elapsed time and a short call id to correlate the three lines. This is
    what makes tool activity traceable from the server's own logs, since
    ChatGPT's client-side tool-call UI doesn't reliably show what actually
    ran or what it returned.
    """
    tool_name = fn.__name__

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        call_id = uuid.uuid4().hex[:8]
        logger.info("tool[%s] %s: start args=(%s)", call_id, tool_name, _format_kwargs(kwargs))
        start = time.monotonic()
        try:
            result = fn(*args, **kwargs)
        except Exception:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.exception("tool[%s] %s: FAILED after %.1fms", call_id, tool_name, elapsed_ms)
            raise
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            "tool[%s] %s: success after %.1fms output=%s",
            call_id,
            tool_name,
            elapsed_ms,
            _truncate(result),
        )
        return result

    return wrapper  # type: ignore[return-value]
