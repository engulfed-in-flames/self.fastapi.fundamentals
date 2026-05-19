import logging
import contextvars
from abc import ABC, abstractmethod
from typing import override


# Context variable to store correlation ID per request context safely
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="SYSTEM"
)


class BaseFilterConfig(ABC):
    """Abstract base class for filter configurations."""

    @abstractmethod
    def create(self) -> logging.Filter:
        """Creates and returns a configured logging.Filter instance."""
        pass


class MaxLevelFilter(logging.Filter):
    """Filters out log records above a specific log level."""

    def __init__(self, name: str = "", max_level: str = "INFO"):
        super().__init__(name)
        self.max_level = logging.getLevelNamesMapping().get(
            max_level.upper(), logging.INFO
        )

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.max_level


class CorrelationIdFilter(logging.Filter):
    """Injects the request correlation ID into the log record."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx.get()
        return True


class StdoutFilterConfig(BaseFilterConfig):
    @override
    def create(self) -> logging.Filter:
        return MaxLevelFilter(max_level="INFO")


class CorrelationFilterConfig(BaseFilterConfig):
    @override
    def create(self) -> logging.Filter:
        return CorrelationIdFilter()
