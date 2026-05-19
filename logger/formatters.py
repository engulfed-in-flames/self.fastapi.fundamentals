import json
import datetime as dt
import logging
from abc import ABC, abstractmethod
from typing import Any, override


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


class MyJSONFormatter(logging.Formatter):
    """Custom JSON formatter encapsulating Python logging records."""

    def __init__(self, *, fmt_keys: dict[str, str] | None = None):
        super().__init__()
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}

    @override
    def format(self, record: logging.LogRecord) -> str:
        message = self._prepare_message_dict(record)
        return json.dumps(message, default=str)

    def _prepare_message_dict(self, record: logging.LogRecord) -> dict[str, Any]:
        required_fields = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
        }

        if record.exc_info:
            required_fields["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info:
            required_fields["stack_info"] = self.formatStack(record.stack_info)

        message = {
            key: msg_val
            if (msg_val := required_fields.pop(val, None))
            else getattr(record, val, None)
            for key, val in self.fmt_keys.items()
        }
        message.update(required_fields)
        return message


class JsonFormatterConfig(BaseFormatterConfig):
    """Configuration for JSON structured log formats."""

    @override
    def create(self) -> logging.Formatter:
        return MyJSONFormatter(
            fmt_keys={
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
