import sys
import logging
from queue import SimpleQueue
from abc import ABC, abstractmethod
from typing import List, override
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener
from logger.formatters import SimpleFormatterConfig, JsonFormatterConfig
from logger.filters import StdoutFilterConfig, CorrelationFilterConfig


class BaseHandlerConfig(ABC):
    """Abstract base class for handler configurations."""

    @abstractmethod
    def create(self) -> logging.Handler:
        """Creates and returns a configured logging.Handler instance."""
        pass


class StdoutHandlerConfig(BaseHandlerConfig):
    @override
    def create(self) -> logging.Handler:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(SimpleFormatterConfig().create())
        handler.addFilter(StdoutFilterConfig().create())
        return handler


class StderrHandlerConfig(BaseHandlerConfig):
    @override
    def create(self) -> logging.Handler:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.WARNING)
        handler.setFormatter(SimpleFormatterConfig().create())
        return handler


class FileHandlerConfig(BaseHandlerConfig):
    @override
    def create(self) -> logging.Handler:
        handler = RotatingFileHandler(
            filename="logs/my_app.log.jsonl", maxBytes=10000, backupCount=3
        )
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(JsonFormatterConfig().create())
        return handler


class AsyncQueueHandlerConfig(BaseHandlerConfig):
    def __init__(self, target_handlers: List[logging.Handler]):
        self._target_handlers = target_handlers

    @override
    def create(self) -> logging.Handler:
        queue = SimpleQueue()
        handler = QueueHandler(queue)

        # Attach listener directly to easily manage its lifecycle
        handler.listener = QueueListener(
            queue, *self._target_handlers, respect_handler_level=True
        )
        handler.addFilter(CorrelationFilterConfig().create())
        return handler
