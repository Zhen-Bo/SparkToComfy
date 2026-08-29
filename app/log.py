"""One log pipeline for everything: structlog builds the event, stdlib carries it, one renderer prints it.

The app logs through structlog; httpx, alembic and uvicorn log through stdlib and get the same
timestamp, level, request_id and renderer via the formatter's foreign_pre_chain.
"""

import logging
import sys

import structlog
from structlog.dev import (
    BLUE,
    BRIGHT,
    CYAN,
    DIM,
    MAGENTA,
    RESET_ALL,
    Column,
    ConsoleRenderer,
    KeyValueColumnFormatter,
    LogLevelColumnFormatter,
)
from structlog.stdlib import ProcessorFormatter

# Fits the longest logger name that shows up (alembic.runtime.migration) plus its brackets.
LOGGER_WIDTH = 27


def _value(val: object) -> str:
    """Bare strings unless they hold whitespace, '=' or quotes; then repr. Same rule as structlog's default."""
    if isinstance(val, str) and not set(val) & {" ", "\t", "=", "\r", "\n", '"', "'"}:
        return val
    return repr(val)


def _console(colors: bool) -> ConsoleRenderer:
    """time, level, [logger], event, key=value: the fixed-width parts first, so the eye finds them in one place."""
    dim, blue, bright, cyan, magenta, reset = (
        (DIM, BLUE, BRIGHT, CYAN, MAGENTA, RESET_ALL) if colors else ("",) * 6
    )

    def plain(key: str, style: str) -> Column:
        return Column(
            key,
            KeyValueColumnFormatter(
                key_style=None, value_style=style, reset_style=reset, value_repr=str
            ),
        )

    return ConsoleRenderer(
        columns=[
            plain("timestamp", dim),
            Column(
                "level",
                LogLevelColumnFormatter(
                    ConsoleRenderer.get_default_level_styles(colors), reset_style=reset
                ),
            ),
            Column(
                "logger",
                lambda key, value: blue + f"[{value}]".ljust(LOGGER_WIDTH) + reset,
            ),
            plain("event", bright),
            Column(
                "",
                KeyValueColumnFormatter(
                    key_style=cyan,
                    value_style=magenta,
                    reset_style=reset,
                    value_repr=_value,
                ),
            ),
        ]
    )


def setup(fmt: str, level: str) -> None:
    if fmt == "json":
        # Machines read this: UTC, ISO 8601.
        stamper = structlog.processors.TimeStamper(fmt="iso")
        renderer = structlog.processors.JSONRenderer()
    else:
        # People read this: the clock of the machine it runs on.
        stamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False)
        renderer = _console(colors=sys.stderr.isatty())
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        stamper,
        structlog.processors.format_exc_info,
    ]
    handler = logging.StreamHandler()
    handler.setFormatter(
        ProcessorFormatter(
            processors=[ProcessorFormatter.remove_processors_meta, renderer],
            foreign_pre_chain=shared,
        )
    )
    logging.basicConfig(handlers=[handler], level=level)
    # httpx prints one INFO line per call to ComfyUI, which is only worth reading while debugging.
    logging.getLogger("httpx").setLevel(
        logging.DEBUG if level == "DEBUG" else logging.WARNING
    )
    # uvicorn installs its own handlers before importing the app; route its lines through ours.
    # --no-access-log leaves uvicorn.access without handlers, and that silence must stay.
    for name in ("uvicorn", "uvicorn.access"):
        uv = logging.getLogger(name)
        if uv.handlers:
            uv.handlers.clear()
            uv.propagate = True
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared,
            ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
