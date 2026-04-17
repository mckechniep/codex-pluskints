from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from tomlkit import dumps, parse

from .config import load_config, save_config
from .discovery import discover_state
from .models import AppConfig, ChangePlan, PluginChange, SkillChange, Snapshot
from .profiles import (
    create_profile,
    delete_profile,
    expand_profile_plugins,
    expand_profile_skills,
    get_profile,
    save_profile,
    update_profile_items,
)


class ManagerError(RuntimeError):
    pass


class ProfileManager:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config, self.config_path = load_config(config_path)

    def refresh(self):
        return discover_state(self.config)

    def save_config(self) -> Path:
        return save_config(self.config, self.config_path)

    def build_plan(self, desired_skills: set[str], desired_plugins: set[str]) -> ChangePlan:
        state = self.refresh()
        plan = ChangePlan(
            desired_skills=set(desired_skills),
            desired_plugins=set(desired_plugins),
        )
        known_skills = state.skill_map
        known_plugins = state.plugin_map

        for name in sorted(desired_skills - set(known_skills)):
            plan.errors.append(f"unknown skill: {name}")
        for plugin_id in sorted(desired_plugins - set(known_plugins)):
            plan.errors.append(f"unknown plugin: {plugin_id}")

        for skill in state.skills:
            if skill.name in desired_skills and not skill.active:
                if skill.disabled_path is None:
                    plan.errors.append(f"cannot enable skill missing from disk: {skill.name}")
                    continue
                target = self.config.skills_dir / skill.name
                plan.skill_changes.append(
                    SkillChange("enable", skill.name, skill.disabled_path, target)
                )
            elif skill.name not in desired_skills and skill.active:
                source = skill.path or (self.config.skills_dir / skill.name)
                target = self.config.disabled_dir / skill.name
                plan.skill_changes.append(SkillChange("disable", skill.name, source, target))

        for plugin in state.plugins:
            should_enable = plugin.plugin_id in desired_plugins
            if plugin.enabled != should_enable:
                plan.plugin_changes.append(
                    PluginChange(plugin_id=plugin.plugin_id, enabled=should_enable)
                )

        if not self.config.disabled_dir.exists():
            plan.warnings.append(
                f"disabled skill directory will be created: {self.config.disabled_dir}"
            )
        return plan

    def build_profile_plan(self, profile_name: str) -> ChangePlan:
        state = self.refresh()
        profile = get_profile(self.config, profile_name)
        desired_skills = expand_profile_skills(profile, set(state.skill_map))
        desired_plugins = expand_profile_plugins(profile, set(state.plugin_map))
        return self.build_plan(desired_skills, desired_plugins)

    def apply_plan(self, plan: ChangePlan, dry_run: bool = False) -> ChangePlan:
        if plan.errors:
            raise ManagerError("\n".join(plan.errors))
        if dry_run:
            return plan

        self.config.disabled_dir.mkdir(parents=True, exist_ok=True)
        for change in plan.skill_changes:
            if not change.source.exists():
                raise ManagerError(f"source path missing for skill change: {change.source}")
            if change.target.exists():
                raise ManagerError(f"target path already exists for skill change: {change.target}")
            shutil.move(str(change.source), str(change.target))

        if plan.plugin_changes:
            self._apply_plugin_changes(plan.plugin_changes)

        return plan

    def enable(self, name: str, kind: str = "auto", dry_run: bool = False) -> ChangePlan:
        state = self.refresh()
        desired_skills = set(state.active_skill_names)
        desired_plugins = set(state.enabled_plugin_ids)
        resolved_kind = self._resolve_kind(name, kind, state.skill_map, state.plugin_map)
        if resolved_kind == "skill":
            desired_skills.add(name)
        else:
            desired_plugins.add(name)
        plan = self.build_plan(desired_skills, desired_plugins)
        return self.apply_plan(plan, dry_run=dry_run)

    def disable(self, name: str, kind: str = "auto", dry_run: bool = False) -> ChangePlan:
        state = self.refresh()
        desired_skills = set(state.active_skill_names)
        desired_plugins = set(state.enabled_plugin_ids)
        resolved_kind = self._resolve_kind(name, kind, state.skill_map, state.plugin_map)
        if resolved_kind == "skill":
            desired_skills.discard(name)
        else:
            desired_plugins.discard(name)
        plan = self.build_plan(desired_skills, desired_plugins)
        return self.apply_plan(plan, dry_run=dry_run)

    def save_profile(self, name: str, skills: set[str] | None = None, plugins: set[str] | None = None):
        state = self.refresh()
        save_profile(
            self.config,
            name,
            enabled_skills=set(state.active_skill_names) if skills is None else skills,
            enabled_plugins=set(state.enabled_plugin_ids) if plugins is None else plugins,
        )
        self.save_config()
        return self.config.profiles[name]

    def create_profile(self, name: str, from_current: bool = False, overwrite: bool = False):
        state = self.refresh()
        profile = create_profile(
            self.config,
            name,
            enabled_skills=set(state.active_skill_names) if from_current else set(),
            enabled_plugins=set(state.enabled_plugin_ids) if from_current else set(),
            overwrite=overwrite,
        )
        self.save_config()
        return profile

    def add_to_profile(self, profile_name: str, item_name: str, kind: str = "auto"):
        state = self.refresh()
        profile = get_profile(self.config, profile_name)
        resolved_kind = self._resolve_kind(item_name, kind, state.skill_map, state.plugin_map)
        skills = expand_profile_skills(profile, set(state.skill_map))
        plugins = expand_profile_plugins(profile, set(state.plugin_map))
        if resolved_kind == "skill":
            skills.add(item_name)
            update_profile_items(profile, skills=skills)
        else:
            plugins.add(item_name)
            update_profile_items(profile, plugins=plugins)
        self.save_config()
        return profile

    def remove_from_profile(self, profile_name: str, item_name: str, kind: str = "auto"):
        state = self.refresh()
        profile = get_profile(self.config, profile_name)
        resolved_kind = self._resolve_kind(item_name, kind, state.skill_map, state.plugin_map)
        skills = expand_profile_skills(profile, set(state.skill_map))
        plugins = expand_profile_plugins(profile, set(state.plugin_map))
        if resolved_kind == "skill":
            skills.discard(item_name)
            update_profile_items(profile, skills=skills)
        else:
            plugins.discard(item_name)
            update_profile_items(profile, plugins=plugins)
        self.save_config()
        return profile

    def delete_profile(self, name: str):
        profile = delete_profile(self.config, name)
        self.save_config()
        return profile

    def backup(self, output_path: Path) -> Path:
        state = self.refresh()
        snapshot = Snapshot(
            active_skills=sorted(state.active_skill_names),
            disabled_skills=sorted(state.disabled_skill_names),
            enabled_plugins=sorted(state.enabled_plugin_ids),
            disabled_plugins=sorted(set(state.plugin_map) - state.enabled_plugin_ids),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        payload = {
            "created_at": snapshot.created_at,
            "active_skills": snapshot.active_skills,
            "disabled_skills": snapshot.disabled_skills,
            "enabled_plugins": snapshot.enabled_plugins,
            "disabled_plugins": snapshot.disabled_plugins,
        }
        self._atomic_write(output_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return output_path

    def restore(self, snapshot_path: Path, dry_run: bool = False) -> ChangePlan:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        desired_skills = set(payload.get("active_skills", []))
        desired_plugins = set(payload.get("enabled_plugins", []))
        plan = self.build_plan(desired_skills, desired_plugins)
        return self.apply_plan(plan, dry_run=dry_run)

    def doctor(self) -> list[str]:
        issues: list[str] = []
        state = self.refresh()

        if not self.config.skills_dir.exists():
            issues.append(f"skills dir missing: {self.config.skills_dir}")
        if not self.config.skill_lock_path.exists():
            issues.append(f"skill lock missing: {self.config.skill_lock_path}")
        if not self.config.codex_config_path.exists():
            issues.append(f"Codex config missing: {self.config.codex_config_path}")
        if not self.config.disabled_dir.exists():
            issues.append(f"disabled skills dir missing: {self.config.disabled_dir}")

        for skill in state.skills:
            if skill.in_lockfile and not skill.installed:
                issues.append(f"lockfile entry missing on disk: {skill.name}")
            if skill.installed and not skill.in_lockfile:
                issues.append(f"skill exists on disk but not in lockfile: {skill.name}")
        return issues

    @staticmethod
    def render_plan(plan: ChangePlan) -> str:
        lines: list[str] = []
        if plan.errors:
            lines.extend(f"ERROR: {error}" for error in plan.errors)
        if plan.skill_changes:
            lines.append("Skill changes:")
            lines.extend(
                f"  - {change.action} {change.name}: {change.source} -> {change.target}"
                for change in plan.skill_changes
            )
        if plan.plugin_changes:
            lines.append("Plugin changes:")
            lines.extend(
                f"  - {'enable' if change.enabled else 'disable'} {change.plugin_id}"
                for change in plan.plugin_changes
            )
        if plan.warnings:
            lines.append("Warnings:")
            lines.extend(f"  - {warning}" for warning in plan.warnings)
        if not lines:
            lines.append("No changes.")
        return "\n".join(lines)

    def _apply_plugin_changes(self, changes: list[PluginChange]) -> None:
        path = self.config.codex_config_path
        if not path.exists():
            raise ManagerError(f"Codex config does not exist: {path}")
        document = parse(path.read_text(encoding="utf-8"))
        plugins_table = document.get("plugins")
        if plugins_table is None:
            raise ManagerError("Codex config has no [plugins] section")
        for change in changes:
            plugin_table = plugins_table.get(change.plugin_id)
            if plugin_table is None:
                raise ManagerError(f"plugin not found in Codex config: {change.plugin_id}")
            plugin_table["enabled"] = change.enabled
        self._atomic_write(path, dumps(document))

    @staticmethod
    def _resolve_kind(
        name: str,
        kind: str,
        skill_map: dict[str, object],
        plugin_map: dict[str, object],
    ) -> str:
        if kind in {"skill", "plugin"}:
            return kind
        in_skills = name in skill_map
        in_plugins = name in plugin_map
        if in_skills and in_plugins:
            raise ManagerError(f"ambiguous target, specify --kind explicitly: {name}")
        if in_skills:
            return "skill"
        if in_plugins:
            return "plugin"
        raise ManagerError(f"unknown skill or plugin: {name}")

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)
