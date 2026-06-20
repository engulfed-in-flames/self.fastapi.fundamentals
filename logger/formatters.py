import json
import datetime as dt
import logging
from abc import ABC, abstractmethod
from typing import override


class BaseFormatterConfig(ABC):
    """Abstract base class for formatter configurations."""

    @abstractmethod
    def create(self) -> logging.Formatter:
        """Creates and returns a configured logging.Formatter instance."""
        pass


class SimpleFormatterConfig(BaseFormatterConfig):
    """Configuration for simple log formats."""

    @override
    def create(self) -> logging.Formatter:
        return logging.Formatter(fmt="[%(correlation_id)s] %(levelname)s: %(message)s")


class DetailedFormatterConfig(BaseFormatterConfig):
    """Configuration for detailed log formats."""

    @override
    def create(self) -> logging.Formatter:
        return logging.Formatter(
            fmt="[%(correlation_id)s] [%(levelname)s|%(module)s|L%(lineno)d] %(asctime)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )


class JsonFormatter(logging.Formatter):
    """JSON structured log formatter."""

    def __init__(self, fmt_keys: dict[str, str] | None = None):
        super().__init__()
        self.fmt_keys = (
            fmt_keys
            if fmt_keys is not None
            else {
                "level": "levelname",
                "message": "message",
                "timestamp": "timestamp",
                "correlation_id": "correlation_id",
                "logger": "name",
                "module": "module",
                "function": "funcName",
                "line": "lineno",
                "thread_name": "threadName",
            }
        )

    @override
    def format(self, record: logging.LogRecord) -> str:
        fields_to_update = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
        }

        record.processName
        if record.exc_info:
            fields_to_update["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info:
            fields_to_update["stack_info"] = self.formatStack(record.stack_info)

        message = {
            key: msg_val
            if (msg_val := fields_to_update.pop(val, None))
            else getattr(record, val, None)
            for key, val in self.fmt_keys.items()
        }
        message.update(fields_to_update)

        return json.dumps(message, default=str)
