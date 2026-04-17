from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import AppConfig
from .discovery import discover_state


def _estimate_tokens(text: str) -> int:
    # Coarse heuristic for English markdown/instructions.
    return max(1, round(len(text) / 4))


def _find_skill_markdown(skill_dir: Path) -> Path | None:
    direct = skill_dir / "SKILL.md"
    if direct.exists():
        return direct
    matches = sorted(skill_dir.rglob("SKILL.md"))
    return matches[0] if matches else None


def _latest_child_dir(path: Path) -> Path | None:
    if not path.exists():
        return None
    dirs = sorted([entry for entry in path.iterdir() if entry.is_dir()], key=lambda p: p.name)
    return dirs[-1] if dirs else None


@dataclass(slots=True)
class FileFootprint:
    label: str
    path: Path
    bytes: int
    chars: int
    lines: int
    estimated_tokens: int


@dataclass(slots=True)
class GroupFootprint:
    label: str
    files: list[FileFootprint]
    status: str = ""

    @property
    def bytes(self) -> int:
        return sum(item.bytes for item in self.files)

    @property
    def chars(self) -> int:
        return sum(item.chars for item in self.files)

    @property
    def lines(self) -> int:
        return sum(item.lines for item in self.files)

    @property
    def estimated_tokens(self) -> int:
        return sum(item.estimated_tokens for item in self.files)


@dataclass(slots=True)
class FootprintReport:
    skills: list[GroupFootprint]
    plugins: list[GroupFootprint]
    warnings: list[str]

    @property
    def skill_totals(self) -> GroupFootprint:
        files: list[FileFootprint] = []
        for skill in self.skills:
            files.extend(skill.files)
        return GroupFootprint(label="All skills total", files=files)

    @property
    def plugin_totals(self) -> GroupFootprint:
        files: list[FileFootprint] = []
        for plugin in self.plugins:
            files.extend(plugin.files)
        return GroupFootprint(label="All plugins total", files=files)

    @property
    def overall(self) -> GroupFootprint:
        files: list[FileFootprint] = []
        for skill in self.skills:
            files.extend(skill.files)
        for plugin in self.plugins:
            files.extend(plugin.files)
        return GroupFootprint(label="Overall total", files=files)


def _measure_file(label: str, path: Path) -> FileFootprint:
    text = path.read_text(encoding="utf-8")
    byte_count = len(text.encode("utf-8"))
    return FileFootprint(
        label=label,
        path=path,
        bytes=byte_count,
        chars=len(text),
        lines=text.count("\n") + (0 if text.endswith("\n") or not text else 1),
        estimated_tokens=_estimate_tokens(text),
    )


def _plugin_skill_files(config: AppConfig, plugin_id: str) -> tuple[list[FileFootprint], list[str]]:
    warnings: list[str] = []
    plugin_name, _, marketplace = plugin_id.partition("@")
    if not marketplace:
        warnings.append(f"plugin id has no marketplace suffix: {plugin_id}")
        return [], warnings
    cache_root = config.codex_config_path.parent / "plugins" / "cache" / marketplace / plugin_name
    version_dir = _latest_child_dir(cache_root)
    if version_dir is None:
        warnings.append(f"plugin cache missing for {plugin_id}: {cache_root}")
        return [], warnings
    skill_files = sorted(version_dir.glob("skills/*/SKILL.md"))
    if not skill_files:
        warnings.append(f"no plugin skills found for {plugin_id}: {version_dir}")
        return [], warnings
    measured = [
        _measure_file(label=f"{plugin_id}:{path.parent.name}", path=path) for path in skill_files
    ]
    return measured, warnings


def build_footprint_report(config: AppConfig) -> FootprintReport:
    state = discover_state(config)
    warnings: list[str] = []

    skill_groups: list[GroupFootprint] = []
    for skill in state.skills:
        skill_dir = skill.path or skill.disabled_path
        if skill.active:
            status = "active"
        elif skill.installed:
            status = "inactive"
        else:
            status = "missing"
        if skill_dir is None:
            warnings.append(f"skill missing on disk: {skill.name}")
            skill_groups.append(GroupFootprint(label=skill.name, files=[], status=status))
            continue
        skill_md = _find_skill_markdown(skill_dir)
        if skill_md is None:
            warnings.append(f"skill has no SKILL.md: {skill.name}")
            skill_groups.append(GroupFootprint(label=skill.name, files=[], status=status))
            continue
        skill_groups.append(
            GroupFootprint(
                label=skill.name,
                files=[_measure_file(label=skill.name, path=skill_md)],
                status=status,
            )
        )

    plugin_groups: list[GroupFootprint] = []
    for plugin in state.plugins:
        files, plugin_warnings = _plugin_skill_files(config, plugin.plugin_id)
        warnings.extend(plugin_warnings)
        plugin_groups.append(
            GroupFootprint(
                label=plugin.plugin_id,
                files=files,
                status="enabled" if plugin.enabled else "disabled",
            )
        )

    return FootprintReport(
        skills=skill_groups,
        plugins=plugin_groups,
        warnings=warnings,
    )
