"""Log management for conversations and improvements."""

from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional
from dataclasses import dataclass, asdict, field
import json
import aiofiles
import asyncio

from ..config import config


@dataclass
class TurnLog:
    """A single turn in a conversation."""
    timestamp: str
    session_id: str
    turn_id: int
    type: str = "turn"
    user_message: str = ""
    assistant_response: str = ""
    prompt_version: int = 0
    model: str = ""
    tokens: dict = field(default_factory=dict)
    latency_ms: int = 0
    feedback: Optional[dict] = None


class LogManager:
    """
    Manages conversation and improvement logs in JSONL format.

    Structure:
    data/logs/conversations/2024-01-30.jsonl
    data/logs/improvements/2024-01-30.jsonl
    """

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or config.paths.logs
        self.conversations_path = self.base_path / "conversations"
        self.improvements_path = self.base_path / "improvements"
        self._turn_counters: dict[str, int] = {}

        # Ensure directories exist
        self.conversations_path.mkdir(parents=True, exist_ok=True)
        self.improvements_path.mkdir(parents=True, exist_ok=True)

    def _get_turn_id(self, session_id: str) -> int:
        """Get and increment turn counter for a session."""
        if session_id not in self._turn_counters:
            self._turn_counters[session_id] = 0
        self._turn_counters[session_id] += 1
        return self._turn_counters[session_id]

    async def log_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        prompt_version: int,
        feedback: Optional["Feedback"] = None,
        model: str = "",
        tokens: Optional[dict] = None,
        latency_ms: int = 0,
    ):
        """Log a single conversation turn."""
        log_entry = TurnLog(
            timestamp=datetime.utcnow().isoformat() + "Z",
            session_id=session_id,
            turn_id=self._get_turn_id(session_id),
            user_message=user_message,
            assistant_response=assistant_response,
            prompt_version=prompt_version,
            model=model,
            tokens=tokens or {},
            latency_ms=latency_ms,
            feedback=asdict(feedback) if feedback else None,
        )

        await self._append_log(
            self.conversations_path / f"{date.today().isoformat()}.jsonl",
            asdict(log_entry),
        )

    async def log_improvement_event(self, event_type: str, data: dict):
        """Log an improvement-related event."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": event_type,
            **data,
        }

        await self._append_log(
            self.improvements_path / f"{date.today().isoformat()}.jsonl",
            log_entry,
        )

    async def _append_log(self, path: Path, entry: dict):
        """Append a log entry to a file."""
        async with aiofiles.open(path, "a", encoding="utf-8") as f:
            await f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _get_log_files(self, date_range: str) -> list[Path]:
        """Get log files for a date range."""
        today = date.today()

        if date_range == "last_day":
            start_date = today - timedelta(days=1)
        elif date_range == "last_week":
            start_date = today - timedelta(days=7)
        elif date_range == "last_month":
            start_date = today - timedelta(days=30)
        else:  # "all"
            start_date = date(2020, 1, 1)

        files = []
        for file_path in sorted(self.conversations_path.glob("*.jsonl"), reverse=True):
            try:
                file_date = date.fromisoformat(file_path.stem)
                if file_date >= start_date:
                    files.append(file_path)
            except ValueError:
                continue

        return files

    async def get_recent(
        self,
        limit: int = 50,
        feedback_type: Optional[str] = None,
        date_range: str = "last_week",
    ) -> list[dict]:
        """
        Get recent conversation logs with optional filtering.

        Args:
            limit: Maximum number of entries to return
            feedback_type: Filter by feedback type ("positive", "negative", None for all)
            date_range: Date range ("last_day", "last_week", "last_month", "all")

        Returns:
            List of log entries
        """
        logs = []
        files = self._get_log_files(date_range)

        for file_path in files:
            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    async for line in f:
                        if not line.strip():
                            continue

                        entry = json.loads(line)

                        # Filter by feedback type if specified
                        if feedback_type:
                            if not entry.get("feedback"):
                                continue
                            if entry["feedback"].get("type") != feedback_type:
                                continue

                        logs.append(entry)

                        if len(logs) >= limit:
                            return logs
            except FileNotFoundError:
                continue

        return logs

    async def search(
        self,
        query: str,
        date_range: str = "all",
        limit: int = 100,
    ) -> list[dict]:
        """
        Search logs by text query.

        Args:
            query: Search string (case-insensitive)
            date_range: Date range to search
            limit: Maximum results

        Returns:
            List of matching log entries
        """
        results = []
        files = self._get_log_files(date_range)
        query_lower = query.lower()

        for file_path in files:
            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    async for line in f:
                        if query_lower in line.lower():
                            results.append(json.loads(line))
                            if len(results) >= limit:
                                return results
            except FileNotFoundError:
                continue

        return results

    async def get_session(self, session_id: str) -> list[dict]:
        """Get all turns from a specific session."""
        logs = []
        files = self._get_log_files("all")

        for file_path in files:
            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    async for line in f:
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        if entry.get("session_id") == session_id:
                            logs.append(entry)
            except FileNotFoundError:
                continue

        return sorted(logs, key=lambda x: x.get("turn_id", 0))

    def get_recent_sync(
        self,
        limit: int = 50,
        feedback_type: Optional[str] = None,
        date_range: str = "last_week",
    ) -> list[dict]:
        """Synchronous version of get_recent for non-async contexts."""
        return asyncio.get_event_loop().run_until_complete(
            self.get_recent(limit, feedback_type, date_range)
        )

    async def get_feedback_stats(self, date_range: str = "last_week") -> dict:
        """Get statistics about feedback."""
        logs = await self.get_recent(limit=1000, date_range=date_range)

        total = len(logs)
        with_feedback = [l for l in logs if l.get("feedback")]
        positive = [l for l in with_feedback if l["feedback"].get("type") == "positive"]
        negative = [l for l in with_feedback if l["feedback"].get("type") == "negative"]

        return {
            "total_turns": total,
            "turns_with_feedback": len(with_feedback),
            "positive_count": len(positive),
            "negative_count": len(negative),
            "feedback_rate": len(with_feedback) / total if total > 0 else 0,
            "positive_rate": len(positive) / len(with_feedback) if with_feedback else 0,
        }
