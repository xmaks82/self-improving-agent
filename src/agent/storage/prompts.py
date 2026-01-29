"""Prompt version management with YAML storage and symlinks."""

from pathlib import Path
from datetime import datetime
from typing import Optional
import yaml
import os

from ..config import config


class PromptManager:
    """
    Manages versioned system prompts for agents.

    Structure:
    data/prompts/{agent_name}/
        v001_2024-01-29T10-30-00.yaml
        v002_2024-01-30T14-22-15.yaml
        current.yaml -> symlink to active version
    """

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or config.paths.prompts
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure all agent prompt directories exist."""
        for agent in ["main_agent", "analyzer", "versioner"]:
            (self.base_path / agent).mkdir(parents=True, exist_ok=True)

    def get_current(self, agent_name: str) -> str:
        """Get the current active prompt for an agent."""
        current_path = self.base_path / agent_name / "current.yaml"

        if not current_path.exists():
            raise FileNotFoundError(
                f"No prompt found for agent '{agent_name}'. "
                f"Expected at: {current_path}"
            )

        with open(current_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return data["system_prompt"]

    def current_version(self, agent_name: str) -> int:
        """Get the current version number for an agent."""
        current_path = self.base_path / agent_name / "current.yaml"

        if not current_path.exists():
            return 0

        with open(current_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return data.get("version", 1)

    def get_version_data(self, agent_name: str, version: Optional[int] = None) -> dict:
        """Get full version data including metadata."""
        if version is None:
            current_path = self.base_path / agent_name / "current.yaml"
        else:
            # Find version file
            agent_path = self.base_path / agent_name
            version_files = list(agent_path.glob(f"v{version:03d}_*.yaml"))
            if not version_files:
                raise FileNotFoundError(f"Version {version} not found for {agent_name}")
            current_path = version_files[0]

        with open(current_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def create_version(
        self,
        agent_name: str,
        new_prompt: str,
        changes: list[dict],
        improvement_info: dict,
        author: str = "versioner_agent",
    ) -> int:
        """
        Create a new version of the prompt.

        Args:
            agent_name: Name of the agent
            new_prompt: The new system prompt content
            changes: List of changes with descriptions
            improvement_info: Info about what triggered the improvement
            author: Who/what created this version

        Returns:
            The new version number
        """
        agent_path = self.base_path / agent_name
        current_version = self.current_version(agent_name)
        new_version = current_version + 1

        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
        filename = f"v{new_version:03d}_{timestamp}.yaml"

        version_data = {
            "version": new_version,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "parent_version": current_version if current_version > 0 else None,
            "improvement": improvement_info,
            "changes": changes,
            "system_prompt": new_prompt,
            "metrics": {
                "sessions_count": 0,
                "positive_feedback_rate": None,
                "negative_feedback_rate": None,
            },
            "metadata": {
                "author": author,
                "approved": author == "human",
            },
        }

        # Save new version
        new_path = agent_path / filename
        with open(new_path, "w", encoding="utf-8") as f:
            yaml.dump(
                version_data,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

        # Update current.yaml symlink
        self._update_current_link(agent_name, filename)

        return new_version

    def _update_current_link(self, agent_name: str, target_filename: str):
        """Update the current.yaml symlink to point to a version file."""
        agent_path = self.base_path / agent_name
        current_link = agent_path / "current.yaml"

        # Remove existing link/file
        if current_link.is_symlink() or current_link.exists():
            current_link.unlink()

        # Create new symlink
        current_link.symlink_to(target_filename)

    def rollback(self, agent_name: str, target_version: int, reason: str) -> bool:
        """
        Rollback to a specific version.

        Args:
            agent_name: Name of the agent
            target_version: Version number to rollback to
            reason: Reason for rollback

        Returns:
            True if successful, False if version not found
        """
        agent_path = self.base_path / agent_name

        # Find target version file
        version_files = list(agent_path.glob(f"v{target_version:03d}_*.yaml"))
        if not version_files:
            return False

        target_file = version_files[0]
        self._update_current_link(agent_name, target_file.name)

        # Log rollback (could be enhanced)
        print(f"Rolled back {agent_name} to v{target_version}: {reason}")

        return True

    def get_history(self, agent_name: str, limit: int = 10) -> list[dict]:
        """Get version history for an agent."""
        agent_path = self.base_path / agent_name
        versions = []

        # Get all version files, sorted by version number (descending)
        version_files = sorted(
            agent_path.glob("v*.yaml"),
            key=lambda p: p.name,
            reverse=True,
        )

        for file_path in version_files[:limit]:
            if file_path.name == "current.yaml":
                continue

            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            versions.append({
                "version": data["version"],
                "created_at": data["created_at"],
                "parent_version": data.get("parent_version"),
                "changes_summary": [c.get("description", "") for c in data.get("changes", [])],
                "author": data.get("metadata", {}).get("author", "unknown"),
                "metrics": data.get("metrics", {}),
            })

        return versions

    def get_diff(
        self, agent_name: str, version_a: int, version_b: int
    ) -> dict:
        """Compare two versions of a prompt."""
        data_a = self.get_version_data(agent_name, version_a)
        data_b = self.get_version_data(agent_name, version_b)

        prompt_a = data_a["system_prompt"]
        prompt_b = data_b["system_prompt"]

        # Simple line-by-line diff
        lines_a = prompt_a.splitlines(keepends=True)
        lines_b = prompt_b.splitlines(keepends=True)

        import difflib
        diff = list(difflib.unified_diff(
            lines_a, lines_b,
            fromfile=f"v{version_a}",
            tofile=f"v{version_b}",
        ))

        return {
            "version_a": version_a,
            "version_b": version_b,
            "diff": "".join(diff),
            "added_lines": sum(1 for line in diff if line.startswith("+")),
            "removed_lines": sum(1 for line in diff if line.startswith("-")),
        }
