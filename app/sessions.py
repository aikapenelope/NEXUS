"""Session management for persistent deep agent conversations.

Each session gets:
  - A unique ID
  - A persistent LocalBackend (files survive across runs)
  - A FileCheckpointStore (save/rewind/fork conversations)
  - Message history (persisted to disk)
  - Agent config (which agent is running)

Sessions are stored on disk at /opt/nexus/data/sessions/{session_id}/
and survive container restarts.

Adapted from vstorm full_app SessionManager pattern.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai.messages import ModelMessage
from pydantic_deep import DeepAgentDeps

from app.agents.factory import AgentConfig

logger = logging.getLogger(__name__)

# Base directory for all session data (mounted as Docker volume)
SESSIONS_DIR = Path("/opt/nexus/data/sessions")


@dataclass
class Session:
    """Persistent session state for a deep agent conversation."""

    session_id: str
    config: AgentConfig
    deps: DeepAgentDeps
    message_history: list[ModelMessage] = field(default_factory=list)
    pending_approval: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    @property
    def session_dir(self) -> Path:
        """Directory for this session's persistent data."""
        return SESSIONS_DIR / self.session_id

    def touch(self) -> None:
        """Update last_active timestamp."""
        self.last_active = time.time()

    def save_history(self) -> None:
        """Persist message history to disk.

        Uses pydantic-ai's message serialization. Best-effort:
        failures are logged but don't block execution.
        """
        try:
            history_path = self.session_dir / "messages.json"
            history_path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize messages using their model_dump if available
            serialized = []
            for msg in self.message_history:
                if hasattr(msg, "model_dump"):
                    serialized.append(msg.model_dump(mode="json"))  # type: ignore[union-attr]
                else:
                    serialized.append(str(msg))

            history_path.write_text(json.dumps(serialized, default=str))
        except Exception:
            logger.debug("Failed to save message history", exc_info=True)


class SessionManager:
    """Manages persistent sessions for deep agent conversations.

    Each session gets an isolated LocalBackend with its own filesystem,
    message history, and checkpoint store. Sessions persist on disk
    and can be resumed after disconnects or restarts.
    """

    def __init__(self, sessions_dir: Path = SESSIONS_DIR) -> None:
        self._sessions: dict[str, Session] = {}
        self._sessions_dir = sessions_dir
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def get(self, session_id: str) -> Session | None:
        """Get an existing session by ID."""
        return self._sessions.get(session_id)

    def create(self, session_id: str, config: AgentConfig) -> Session:
        """Create a new persistent session.

        Creates a LocalBackend rooted at the session's directory,
        giving the agent a persistent filesystem that survives
        across runs and restarts.
        """
        from pydantic_ai_backends import LocalBackend

        session_dir = self._sessions_dir / session_id
        workspace_dir = session_dir / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # LocalBackend gives the agent a real filesystem
        backend = LocalBackend(
            root_dir=workspace_dir,
            enable_execute=config.use_sandbox,
        )

        deps = DeepAgentDeps(backend=backend)

        session = Session(
            session_id=session_id,
            config=config,
            deps=deps,
        )

        self._sessions[session_id] = session
        logger.info(f"Session created: {session_id} (agent: {config.name})")
        return session

    def get_or_create(self, session_id: str, config: AgentConfig) -> Session:
        """Get existing session or create a new one."""
        existing = self.get(session_id)
        if existing is not None:
            existing.touch()
            return existing
        return self.create(session_id, config)

    def remove(self, session_id: str) -> bool:
        """Remove a session from memory (data stays on disk)."""
        session = self._sessions.pop(session_id, None)
        if session is not None:
            session.save_history()
            logger.info(f"Session removed: {session_id}")
            return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions."""
        return [
            {
                "session_id": s.session_id,
                "agent": s.config.name,
                "messages": len(s.message_history),
                "created_at": s.created_at,
                "last_active": s.last_active,
            }
            for s in self._sessions.values()
        ]

    def cleanup_idle(self, max_idle_seconds: int = 3600) -> int:
        """Remove sessions idle for more than max_idle_seconds.

        Returns the number of sessions cleaned up.
        """
        now = time.time()
        to_remove = [
            sid
            for sid, session in self._sessions.items()
            if now - session.last_active > max_idle_seconds
        ]
        for sid in to_remove:
            self.remove(sid)
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} idle sessions")
        return len(to_remove)


# Global session manager instance
session_manager = SessionManager()
