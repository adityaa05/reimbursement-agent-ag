import logging
import json
import time
from contextvars import ContextVar
from typing import Optional

# Thread-safe correlation ID context
correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)


class StructuredLogger:
    """JSON structured logging with correlation IDs."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)

    def _build_log_entry(self, level: str, message: str, **kwargs):
        """Build structured log entry."""
        entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "correlation_id": correlation_id_var.get(),
            **kwargs,
        }
        return json.dumps(entry)

    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self.logger.debug(self._build_log_entry("DEBUG", message, **kwargs))

    def info(self, message: str, **kwargs):
        self.logger.info(self._build_log_entry("INFO", message, **kwargs))

    def warning(self, message: str, **kwargs):
        self.logger.warning(self._build_log_entry("WARNING", message, **kwargs))

    def error(self, message: str, **kwargs):
        self.logger.error(self._build_log_entry("ERROR", message, **kwargs))


logger = StructuredLogger("expense_api")


def set_correlation_id(expense_sheet_id: int):
    """Set correlation ID for request tracking."""
    correlation_id_var.set(f"EXP-{expense_sheet_id}")


def log_endpoint_call(endpoint: str, inputs: dict, outputs: dict, duration_ms: float):
    """Log endpoint execution."""
    logger.info(
        f"Endpoint executed: {endpoint}",
        endpoint=endpoint,
        inputs=inputs,
        outputs=outputs,
        duration_ms=duration_ms,
    )
