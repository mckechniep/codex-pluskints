from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class SkillState:
    name: str
    installed: bool
    active: bool
    path: Path | None = None
    disabled_path: Path | None = None
    source: str | None = None
    source_type: str | None = None
    plugin_name: str | None = None
    in_lockfile: bool = False


@dataclass(slots=True)
class PluginState:
    plugin_id: str
    enabled: bool

    @property
    def display_name(self) -> str:
        return self.plugin_id.split("@", 1)[0]


@dataclass(slots=True)
class Profile:
    name: str
    enabled_skills: list[str] = field(default_factory=list)
    enabled_plugins: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AppConfig:
    skills_dir: Path
    disabled_dir: Path
    skill_lock_path: Path
    codex_config_path: Path
    profiles: dict[str, Profile] = field(default_factory=dict)


@dataclass(slots=True)
class ManagerState:
    skills: list[SkillState]
    plugins: list[PluginState]

    @property
    def active_skill_names(self) -> set[str]:
        return {skill.name for skill in self.skills if skill.active}

    @property
    def disabled_skill_names(self) -> set[str]:
        return {skill.name for skill in self.skills if skill.installed and not skill.active}

    @property
    def enabled_plugin_ids(self) -> set[str]:
        return {plugin.plugin_id for plugin in self.plugins if plugin.enabled}

    @property
    def skill_map(self) -> dict[str, SkillState]:
        return {skill.name: skill for skill in self.skills}

    @property
    def plugin_map(self) -> dict[str, PluginState]:
        return {plugin.plugin_id: plugin for plugin in self.plugins}


@dataclass(slots=True)
class SkillChange:
    action: str
    name: str
    source: Path
    target: Path


@dataclass(slots=True)
class PluginChange:
    plugin_id: str
    enabled: bool


@dataclass(slots=True)
class ChangePlan:
    desired_skills: set[str]
    desired_plugins: set[str]
    skill_changes: list[SkillChange] = field(default_factory=list)
    plugin_changes: list[PluginChange] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_noop(self) -> bool:
        return not self.skill_changes and not self.plugin_changes


@dataclass(slots=True)
class Snapshot:
    active_skills: list[str]
    disabled_skills: list[str]
    enabled_plugins: list[str]
    disabled_plugins: list[str]
    created_at: str
