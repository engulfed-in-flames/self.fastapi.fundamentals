from pathlib import Path
from typing import Any, override
import contextvars
import datetime as dt
import json
import logging
import logging.config


LOG_RECORD_BUILTIN_ATTRS = {...}

# Context variable to store correlation ID per request context safely
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="SYSTEM"
)


class MyJSONFormatter(logging.Formatter):
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


class MaxLevelFilter(logging.Filter):
    def __init__(self, name: str = "", max_level: str = "INFO"):
        super().__init__(name)
        # Extract logging integer value or fallback to INFO
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


class LoggingManager:
    """OOP-based Logging Manager for configuration and lifecycle management."""

    def __init__(self, config_path: str | Path = "logger/config.json"):
        self.config_path = Path(config_path)
        self._listener = None

    def setup(self):
        Path("logs").mkdir(parents=True, exist_ok=True)
        with open(self.config_path) as f_in:
            config = json.load(f_in)
            logging.config.dictConfig(config)

        queue_handler = logging.getHandlerByName("queue_handler")
        if queue_handler and hasattr(queue_handler, "listener"):
            self._listener = queue_handler.listener
            self._listener.start()

    def shutdown(self):
        if self._listener:
            self._listener.stop()
