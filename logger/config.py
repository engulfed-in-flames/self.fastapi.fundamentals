import logging
from abc import ABC, abstractmethod
from typing import override
from logger.handlers import (
    StdoutHandlerConfig,
    StderrHandlerConfig,
    FileHandlerConfig,
    AsyncQueueHandlerConfig,
)


class BaseLoggerConfig(ABC):
    """Abstract base class for logger configurations."""

    @abstractmethod
    def configure(self) -> None:
        """Applies the configuration to the logging system."""
        pass


class RootLoggerConfig(BaseLoggerConfig):
    """Handles configuration of the root logger."""

    @override
    def configure(self) -> None:
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers.clear()

        stdout_h = StdoutHandlerConfig().create()
        stderr_h = StderrHandlerConfig().create()
        file_h = FileHandlerConfig().create()

        queue_h = AsyncQueueHandlerConfig([stdout_h, stderr_h, file_h]).create()
        root_logger.addHandler(queue_h)
