"""Plugin loader — discovers and loads plugins from disk."""

import importlib.util
import json
import logging
from pathlib import Path
from typing import Optional

from .types import PluginManifest

logger = logging.getLogger(__name__)

DEFAULT_PLUGIN_DIR = Path.home() / ".agent" / "plugins"


class PluginLoader:
    """Discovers and loads plugins from a directory."""

    def __init__(self, plugin_dir: Optional[Path] = None):
        self.plugin_dir = plugin_dir or DEFAULT_PLUGIN_DIR
        self._loaded: dict[str, PluginManifest] = {}

    def discover(self) -> list[Path]:
        """Find plugin directories with manifest.json."""
        if not self.plugin_dir.exists():
            return []
        return [
            p for p in self.plugin_dir.iterdir()
            if p.is_dir() and (p / "manifest.json").exists()
        ]

    def load_all(self, tool_registry=None, skill_registry=None) -> int:
        """Load all discovered plugins. Returns count loaded."""
        count = 0
        for plugin_dir in self.discover():
            try:
                self._load_one(plugin_dir, tool_registry, skill_registry)
                count += 1
            except Exception as e:
                logger.warning("Failed to load plugin %s: %s", plugin_dir.name, e)
        return count

    def _load_one(self, plugin_dir: Path, tool_registry=None, skill_registry=None):
        """Load a single plugin."""
        manifest = json.loads((plugin_dir / "manifest.json").read_text())
        pm = PluginManifest(**{k: v for k, v in manifest.items()
                               if k in PluginManifest.__dataclass_fields__})

        # Load tools module
        if tool_registry and (plugin_dir / "tools.py").exists():
            mod = self._import_module(f"plugin_{pm.name}_tools", plugin_dir / "tools.py")
            if hasattr(mod, "register_tools"):
                mod.register_tools(tool_registry)

        # Load skills module
        if skill_registry and (plugin_dir / "skills.py").exists():
            mod = self._import_module(f"plugin_{pm.name}_skills", plugin_dir / "skills.py")
            if hasattr(mod, "register_skills"):
                mod.register_skills(skill_registry)

        self._loaded[pm.name] = pm
        logger.info("Loaded plugin: %s v%s", pm.name, pm.version)

    def _import_module(self, name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def list_plugins(self) -> list[PluginManifest]:
        return list(self._loaded.values())
