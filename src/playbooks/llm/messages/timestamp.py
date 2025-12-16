"""Timestamp management for LLM messages with relative timing and configurable granularity."""

import time

from playbooks.config import config


class TimestampManager:
    """Manages relative timestamps for LLM messages.

    Timestamps are relative to program start time and use configurable granularity:
    - 3 = milliseconds (0.001s)
    - 2 = centiseconds (0.01s)
    - 1 = deciseconds (0.1s)
    - 0 = seconds (default)
    - -1 = decaseconds (10s)
    - -2 = hectoseconds (100s)

    Attributes:
        start_time: Unix epoch time when the manager was initialized
        granularity: Power of 10 for timestamp precision
    """

    # Class-level singleton for consistent start time across the application
    _instance = None
    _initialized = False

    def __new__(cls):
        """Singleton pattern to ensure consistent start time."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the timestamp manager (only once)."""
        if not TimestampManager._initialized:
            self.start_time = time.time()
            self.granularity = config.timestamp_granularity
            TimestampManager._initialized = True

    def get_timestamp(self) -> int:
        """Get current relative timestamp as an integer.

        Returns:
            Integer timestamp relative to program start, scaled by granularity
        """
        elapsed = time.time() - self.start_time
        # Scale by 10^granularity and convert to int
        scaled = elapsed * (10**self.granularity)
        return int(scaled)

    def reset(
        self, start_time: float | None = None, granularity: int | None = None
    ) -> None:
        """Reset the timestamp manager (mainly for testing).

        Args:
            start_time: New start time (defaults to current time)
            granularity: New granularity (defaults to current setting)
        """
        self.start_time = start_time if start_time is not None else time.time()
        if granularity is not None:
            self.granularity = granularity


# Global instance
_timestamp_manager = TimestampManager()


def get_timestamp() -> int:
    """Get current relative timestamp.

    Returns:
        Integer timestamp relative to program start
    """
    return _timestamp_manager.get_timestamp()


def get_start_time() -> float:
    """Get the program start time (unix epoch).

    Returns:
        Unix epoch timestamp when the program started
    """
    return _timestamp_manager.start_time


def get_granularity() -> int:
    """Get the current timestamp granularity.

    Returns:
        Granularity as power of 10
    """
    return _timestamp_manager.granularity


def reset_timestamp_manager(
    start_time: float | None = None, granularity: int | None = None
) -> None:
    """Reset the timestamp manager (mainly for testing).

    Args:
        start_time: New start time (defaults to current time)
        granularity: New granularity (defaults to 0)
    """
    _timestamp_manager.reset(start_time, granularity)
