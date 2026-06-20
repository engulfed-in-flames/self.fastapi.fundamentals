import logging
from pathlib import Path
from logger.config import RootLoggerConfig


class LoggingManager:
    """OOP-based Logging Manager for configuration and lifecycle management."""

    def __init__(self):
        self._listener = None

    def setup(self):
        Path("logs").mkdir(parents=True, exist_ok=True)

        RootLoggerConfig().configure()

        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.handlers.QueueHandler) and hasattr(
                handler, "listener"
            ):
                self._listener = handler.listener
                self._listener.start()
                break

    def shutdown(self):
        if self._listener:
            self._listener.stop()
