"""Team memory sync — shared knowledge base per-repo with secret scanning."""

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Optional

from .secret_scanner import scan_for_secrets

logger = logging.getLogger(__name__)


class TeamMemorySync:
    """Shared team knowledge, one directory per repository."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else Path.home() / ".agent" / "team_memory"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _repo_hash(self) -> str:
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return hashlib.sha256(result.stdout.strip().encode()).hexdigest()[:12]
        except Exception:
            pass
        return "local"

    def _repo_dir(self) -> Path:
        d = self.base_dir / self._repo_hash()
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, key: str, content: str) -> tuple[bool, str]:
        """Save a team memory entry. Blocks if secrets detected."""
        secrets = scan_for_secrets(content)
        if secrets:
            labels = ", ".join(s.label for s in secrets)
            return False, f"Blocked: content contains potential secrets ({labels})"
        path = self._repo_dir() / f"{key}.md"
        path.write_text(content)
        return True, f"Saved team memory: {key}"

    def load(self, key: str) -> Optional[str]:
        path = self._repo_dir() / f"{key}.md"
        return path.read_text() if path.exists() else None

    def list_entries(self) -> list[str]:
        return sorted(p.stem for p in self._repo_dir().glob("*.md"))

    def delete(self, key: str) -> bool:
        path = self._repo_dir() / f"{key}.md"
        if path.exists():
            path.unlink()
            return True
        return False

    def get_all_context(self) -> str:
        """Get all team knowledge as context string."""
        entries = []
        for key in self.list_entries():
            content = self.load(key)
            if content:
                entries.append(f"## {key}\n{content}")
        return "\n\n".join(entries) if entries else ""
