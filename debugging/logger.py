# Structured Logger (logger.py)
import os
import structlog


def get_logger(name: str):
    """
    Return a structlog bound logger for the given module name.
    Output format is controlled by LOG_FORMAT env var:
        LOG_FORMAT=json     -> JSON output (production)
        LOG_FORMAT=console  -> Coloured key-value output (development)
    """
    log_format = os.getenv("LOG_FORMAT", "console")

    if log_format == "json":
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(
                _log_level()
            ),
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
        )
    else:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(
                _log_level()
            ),
            processors=[
                structlog.processors.TimeStamper(fmt="%H:%M:%S"),
                structlog.processors.add_log_level,
                structlog.dev.ConsoleRenderer(),
            ],
        )

    return structlog.get_logger(name)


def _log_level():
    import logging
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def bind_context(**kwargs):
    """Bind key-value pairs to all subsequent log calls in this context."""
    return structlog.contextvars.bind_contextvars(**kwargs)
