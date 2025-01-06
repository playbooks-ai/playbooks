"""Runtime session management."""

import base64
import pickle
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import reconstructor

from .base_model import BaseModel


@dataclass
class RuntimeSession(BaseModel):
    """Manages a runtime session with playbooks runtime."""

    __tablename__ = "runtime_sessions"

    id: int = Column(Integer, primary_key=True)
    created_at: datetime = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )
    updated_at: datetime = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )
    runtime_pickle: Optional[str] = Column(String)
    _runtime: Any = None

    def __init__(self, runtime: Any = None):
        """Initialize the RuntimeSession.

        Args:
            runtime: Optional PlaybooksRuntime instance to associate with this session
        """
        super().__init__()
        if runtime is not None:
            self.set_runtime(runtime)

    def __post_init__(self):
        """Initialize after dataclass initialization."""
        if not hasattr(self, "_runtime"):
            self._runtime = None

    @reconstructor
    def init_on_load(self):
        """Initialize when loaded from database."""
        if not hasattr(self, "_runtime"):
            self._runtime = None

    @property
    def runtime(self) -> Any:
        """Get the runtime object."""
        if self._runtime is None and self.runtime_pickle is not None:
            self._runtime = pickle.loads(base64.b64decode(self.runtime_pickle.encode()))
        return self._runtime

    def set_runtime(self, runtime: Any) -> None:
        """Set the runtime object."""
        self._runtime = runtime
        if runtime is not None:
            self.runtime_pickle = base64.b64encode(pickle.dumps(runtime)).decode()
        else:
            self.runtime_pickle = None
