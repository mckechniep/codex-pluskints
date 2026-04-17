from __future__ import annotations

import json
from pathlib import Path

from tomlkit import parse
from tomlkit.exceptions import ParseError

from .models import AppConfig, ManagerState, PluginState, SkillState


def _list_skill_dirs(path: Path) -> dict[str, Path]:
    if not path.exists():
        return {}
    return {entry.name: entry for entry in path.iterdir() if entry.is_dir()}


def _load_skill_lock(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_skills = payload.get("skills", {})
    if not isinstance(raw_skills, dict):
        return {}
    return {name: value for name, value in raw_skills.items() if isinstance(value, dict)}


def discover_skills(config: AppConfig) -> list[SkillState]:
    lock = _load_skill_lock(config.skill_lock_path)
    active_dirs = _list_skill_dirs(config.skills_dir)
    disabled_dirs = _list_skill_dirs(config.disabled_dir)
    names = sorted(set(lock) | set(active_dirs) | set(disabled_dirs))
    skills: list[SkillState] = []
    for name in names:
        metadata = lock.get(name, {})
        active_path = active_dirs.get(name)
        disabled_path = disabled_dirs.get(name)
        skills.append(
            SkillState(
                name=name,
                installed=bool(active_path or disabled_path),
                active=active_path is not None,
                path=active_path,
                disabled_path=disabled_path,
                source=metadata.get("source"),
                source_type=metadata.get("sourceType"),
                plugin_name=metadata.get("pluginName"),
                in_lockfile=name in lock,
            )
        )
    return skills


def discover_plugins(config: AppConfig) -> list[PluginState]:
    if not config.codex_config_path.exists():
        return []
    try:
        document = parse(config.codex_config_path.read_text(encoding="utf-8"))
    except ParseError as exc:
        raise RuntimeError(f"failed to parse Codex config: {exc}") from exc
    plugins_table = document.get("plugins", {})
    plugins: list[PluginState] = []
    for plugin_id, table in plugins_table.items():
        enabled = bool(table.get("enabled", False))
        plugins.append(PluginState(plugin_id=str(plugin_id), enabled=enabled))
    return sorted(plugins, key=lambda plugin: plugin.plugin_id)


def discover_state(config: AppConfig) -> ManagerState:
    return ManagerState(skills=discover_skills(config), plugins=discover_plugins(config))
